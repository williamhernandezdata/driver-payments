import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="My Driver Portal", layout="centered", page_icon="🚕")

# --- CONFIGURATION ---
SPREADSHEET_NAME = "Coop trip payments table"
WORKSHEET_NAME = "data"

# --- SESSION STATE SETUP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'driver_data' not in st.session_state:
    st.session_state['driver_data'] = None
if 'driver_name' not in st.session_state:
    st.session_state['driver_name'] = ""

# --- DATA LOADER ---
@st.cache_data(ttl=600)
def load_all_data():
    secrets = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets, scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)
    except Exception as e:
        st.error("System Maintenance: Could not connect to database.")
        return pd.DataFrame()

    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # --- CLEAN DATA TYPES ---
    if 'job_date' in df.columns:
        df['job_date'] = pd.to_datetime(df['job_date'], errors='coerce')

    money_cols = ['total_paid', 'total_fare', 'coop_commission', 'tips', 'tolls', 
                  'base_fare', 'wait_time_pay', 'stops_amount', 'cash_collected', 'darter']
    
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- SCREEN 1: LOGIN ---
def login_screen():
    st.title("🚕 Driver Login")
    st.markdown("Enter your details to view your payment history.")
    
    with st.form("login_form"):
        driver_id_input = st.text_input("Driver ID", placeholder="e.g. 5800905")
        bank_pin_input = st.text_input("Last 4 Digits of Bank Account", type="password", placeholder="e.g. 1234")
        
        submitted = st.form_submit_button("Log In", use_container_width=True)
        
        if submitted:
            with st.spinner("Verifying credentials..."):
                df = load_all_data()
                
                if df.empty:
                    st.error("No data found. Please try again later.")
                    return

                # Verify ID
                user_df = df[df['driver_num'].astype(str).str.strip() == driver_id_input.strip()]
                
                if user_df.empty:
                    st.error("Driver ID not found.")
                else:
                    # Verify PIN
                    valid_bank = user_df[user_df['bank'].astype(str).str.strip() == bank_pin_input.strip()]
                    
                    if not valid_bank.empty:
                        st.session_state['logged_in'] = True
                        st.session_state['driver_data'] = user_df 
                        
                        first = user_df.iloc[0]['first_name'] if 'first_name' in user_df.columns else "Driver"
                        last = user_df.iloc[0]['last_name'] if 'last_name' in user_df.columns else ""
                        st.session_state['driver_name'] = f"{first} {last}"
                        st.rerun()
                    else:
                        st.error("Incorrect Bank Account digits.")

# --- SCREEN 2: DASHBOARD ---
def dashboard():
    st.success(f"Welcome, {st.session_state['driver_name']}")
    st.info("ℹ️ **Note:** This portal shows automated payments starting from **March/April 2025**. For older history, please contact support.")
    
    if st.button("Log Out"):
        st.session_state['logged_in'] = False
        st.session_state['driver_data'] = None
        st.rerun()

    df = st.session_state['driver_data']
    
    # --- FILTERS ---
    st.markdown("### 🔍 Filter Trips")
    
    col_date, col_search = st.columns(2)
    
    with col_date:
        min_date = df['job_date'].min()
        max_date = df['job_date'].max()
        date_range = st.date_input(
            "📅 Date Range", 
            value=[], 
            min_value=min_date, 
            max_value=max_date
        )

    with col_search:
        # NEW TRIP ID SEARCH
        trip_search = st.text_input("🚕 Search Trip ID")
    
    # Apply Date Filter
    if len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df['job_date'].dt.date >= start_date) & (df['job_date'].dt.date <= end_date)
        df = df[mask]
        
    # Apply Trip ID Search
    if trip_search:
        df = df[df['trip_id'].astype(str).str.contains(trip_search, na=False)]

    # --- FINANCIAL SUMMARIES ---
    st.markdown("### 💰 Financial Summary")
    
    # Calculate Sums based on current filter
    sum_paid = df['total_paid'].sum() if 'total_paid' in df.columns else 0
    sum_tips = df['tips'].sum() if 'tips' in df.columns else 0
    sum_fare = df['total_fare'].sum() if 'total_fare' in df.columns else 0
    sum_comm = df['coop_commission'].sum() if 'coop_commission' in df.columns else 0
    sum_tolls = df['tolls'].sum() if 'tolls' in df.columns else 0
    sum_base = df['base_fare'].sum() if 'base_fare' in df.columns else 0
    sum_wait = df['wait_time_pay'].sum() if 'wait_time_pay' in df.columns else 0
    sum_stops = df['stops_amount'].sum() if 'stops_amount' in df.columns else 0
    sum_cash = df['cash_collected'].sum() if 'cash_collected' in df.columns else 0

    # Row 1: The Big Numbers
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Paid", f"${sum_paid:,.2f}")
    m2.metric("Tips", f"${sum_tips:,.2f}")
    m3.metric("Trips", len(df))

    # Row 2: The Breakdown
    with st.expander("View Full Breakdown"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Fare", f"${sum_fare:,.2f}")
        c2.metric("Commission", f"${sum_comm:,.2f}")
        c3.metric("Tolls", f"${sum_tolls:,.2f}")
        c4.metric("Base Fare", f"${sum_base:,.2f}")
        
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Wait Time", f"${sum_wait:,.2f}")
        c6.metric("Stops", f"${sum_stops:,.2f}")
        c7.metric("Cash Coll.", f"${sum_cash:,.2f}")

    # --- TABLE ---
    st.markdown("---")
    st.markdown("### 📋 Trip List")

    # Legend
    st.markdown("""
        <style>
            .badge-green {background-color: #d4edda; color: #155724; padding: 2px 6px; border-radius: 4px; font-size: 12px;}
            .badge-yellow {background-color: #fff3cd; color: #856404; padding: 2px 6px; border-radius: 4px; font-size: 12px;}
            .badge-red {background-color: #f8d7da; color: #721c24; padding: 2px 6px; border-radius: 4px; font-size: 12px;}
        </style>
        <p style='font-size: 14px;'>
            <span class="badge-green">Processed</span> = Paid &nbsp;&nbsp;
            <span class="badge-yellow">Pending</span> = Processing &nbsp;&nbsp;
            <span class="badge-red">Failed</span> = Returned
        </p>
    """, unsafe_allow_html=True)
    
    # Prepare Data
    display_df = df.copy()
    
    if 'job_date' in display_df.columns:
        display_df['job_date'] = display_df['job_date'].dt.strftime('%Y-%m-%d')
    
    # Hide internal columns
    hide_cols = ['nacha_title', 'bank', 'routing', 'account', 'driver_num', 'first_name', 'last_name', 'full_name']
    display_df = display_df.drop(columns=[c for c in hide_cols if c in display_df.columns])

    # Rename Status
    if 'status' in display_df.columns:
        display_df = display_df.rename(columns={'status': 'Payment Status'})

    display_df = display_df.reset_index(drop=True)

    # STYLE FUNCTION (Highlight Trip ID)
    def highlight_trip(row):
        styles = [''] * len(row)
        if 'Payment Status' in row and 'trip_id' in row.index:
            status = str(row['Payment Status'])
            if status == 'Processed':
                color = 'background-color: #d4edda; color: black' 
            elif status == 'Pending':
                color = 'background-color: #fff3cd; color: black'
            elif status == 'Failed':
                color = 'background-color: #f8d7da; color: black'
            else:
                return styles
            
            try:
                # Apply color to TRIP ID column
                idx = row.index.get_loc('trip_id')
                styles[idx] = color
            except:
                pass
        return styles

    # Apply Style
    styled_df = display_df.style.apply(highlight_trip, axis=1)

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=600,
        column_config={
            "total_paid": st.column_config.NumberColumn("Paid", format="$%.2f"),
            "total_fare": st.column_config.NumberColumn("Fare", format="$%.2f"),
            "coop_commission": st.column_config.NumberColumn("Comm.", format="$%.2f"),
            "tips": st.column_config.NumberColumn("Tips", format="$%.2f"),
            "tolls": st.column_config.NumberColumn("Tolls", format="$%.2f"),
            "base_fare": st.column_config.NumberColumn("Base Fare", format="$%.2f"),
            "wait_time_pay": st.column_config.NumberColumn("Wait", format="$%.2f"),
            "stops_amount": st.column_config.NumberColumn("Stops", format="$%.2f"),
            "cash_collected": st.column_config.NumberColumn("Cash", format="$%.2f"),
            "darter": st.column_config.NumberColumn("Darter", format="$%.2f"),
        }
    )

# --- ROUTER ---
if st.session_state['logged_in']:
    dashboard()
else:
    login_screen()
