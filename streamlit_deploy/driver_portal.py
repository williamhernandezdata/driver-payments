import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="My Driver Portal", layout="centered", page_icon="🚕")

# --- CONFIGURATION ---
FILE_ID = "1dwAT9fkfQY-SIOt4KmQ9gE7J4MnVSfP4"

# --- SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'driver_data' not in st.session_state: st.session_state['driver_data'] = None
if 'driver_name' not in st.session_state: st.session_state['driver_name'] = ""

# --- DATA LOADER ---
@st.cache_data(ttl=3600)
def load_all_data():
    # Load from Secrets
    creds_dict = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    
    # Connect to Drive
    service = build('drive', 'v3', credentials=creds)
    
    try:
        # Download CSV
        request = service.files().get_media(fileId=FILE_ID)
        file_obj = io.BytesIO()
        downloader = MediaIoBaseDownload(file_obj, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_obj.seek(0)
        df = pd.read_csv(file_obj, low_memory=False)
        
    except Exception as e:
        st.error("System Maintenance. Please try again later.")
        return pd.DataFrame()

    # --- CLEANING ---
    if 'job_date' in df.columns:
        df['job_date'] = pd.to_datetime(df['job_date'], errors='coerce')

    money_cols = ['total_paid', 'total_fare', 'coop_commission', 'tips', 'tolls', 
                  'base_fare', 'wait_time_pay', 'stops_amount', 'cash_collected', 'darter']
    
    for col in money_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- HELPER: FORMAT MONEY ---
def fmt_money(val, is_negative=False):
    if is_negative: return f"(${abs(val):,.2f})"
    return f"${val:,.2f}"

# --- HELPER: STATEMENT ROW ---
def statement_row(label, value, is_bold=False, is_negative=False, color=None):
    c1, c2 = st.columns([3, 1])
    with c1:
        if is_bold: st.markdown(f"**{label}**")
        else: st.markdown(f"{label}")
    with c2:
        val_str = fmt_money(value, is_negative)
        if is_bold:
            if color: st.markdown(f":{color}[**{val_str}**]")
            else: st.markdown(f"**{val_str}**")
        else: st.markdown(f"{val_str}")

# --- LOGIN SCREEN ---
def login_screen():
    st.title("🚕 Driver Login")
    st.markdown("Enter your details to view your payment history.")
    
    with st.form("login_form"):
        driver_id_input = st.text_input("Driver ID")
        bank_pin_input = st.text_input("Last 4 Digits of Bank Account", type="password")
        submitted = st.form_submit_button("Log In", use_container_width=True)
        
        if submitted:
            with st.spinner("Verifying credentials..."):
                df = load_all_data()
                if df.empty:
                    st.error("System offline.")
                    return

                user_df = df[df['driver_num'].astype(str).str.strip() == driver_id_input.strip()]
                
                if user_df.empty:
                    st.error("Driver ID not found.")
                else:
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

# --- DASHBOARD ---
def dashboard():
    st.success(f"Welcome, {st.session_state['driver_name']}")
    st.info("ℹ️ **Note:** This portal shows automated payments starting from **March/April 2025**. For older history, please contact support.")
    
    if st.button("Log Out"):
        st.session_state['logged_in'] = False
        st.session_state['driver_data'] = None
        st.rerun()

    df = st.session_state['driver_data']
    
    # Filters
    st.markdown("### 🔍 Filter Trips")
    col_date, col_search = st.columns(2)
    with col_date:
        min_date = df['job_date'].min()
        max_date = df['job_date'].max()
        date_range = st.date_input("📅 Date Range", value=[], min_value=min_date, max_value=max_date)
    with col_search:
        trip_search = st.text_input("🚕 Search Trip ID")
    
    if len(date_range) == 2:
        s, e = date_range
        df = df[(df['job_date'].dt.date >= s) & (df['job_date'].dt.date <= e)]
        
    if trip_search:
        df = df[df['trip_id'].astype(str).str.contains(trip_search, na=False)]

    # Financial Statement
    st.markdown("### 🧾 Payment Statement")
    
    sum_base = df['base_fare'].sum()
    sum_wait = df['wait_time_pay'].sum()
    sum_stops = df['stops_amount'].sum()
    sum_tolls = df['tolls'].sum()
    sum_tips = df['tips'].sum()
    sum_comm = df['coop_commission'].sum()
    sum_cash = df['cash_collected'].sum()
    
    gross_fare = sum_base + sum_wait + sum_stops + sum_tolls + sum_tips
    net_deposit = df['total_paid'].sum()

    with st.container(border=True):
        st.markdown("##### PAYMENT SUMMARY")
        statement_row("Base Fare:", sum_base)
        statement_row("Wait Time Paid:", sum_wait)
        statement_row("Stops Paid:", sum_stops)
        statement_row("Tolls Paid:", sum_tolls)
        statement_row("Tips Paid:", sum_tips)
        st.divider()
        statement_row("Total Gross Fare:", gross_fare, is_bold=True)
        st.write("")
        statement_row("Coop Commission:", sum_comm, is_negative=True)
        statement_row("Cash Collected:", sum_cash, is_negative=True)
        st.divider()
        statement_row("NET AMOUNT DEPOSITED:", net_deposit, is_bold=True, color="green")
        st.caption(f"Total Trips: {len(df)}")

    # Table
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

    display_df = df.copy()
    if 'job_date' in display_df.columns: display_df['job_date'] = display_df['job_date'].dt.strftime('%Y-%m-%d')
    
    hide = ['nacha_title', 'bank', 'routing', 'account', 'driver_num', 'first_name', 'last_name', 'full_name']
    display_df = display_df.drop(columns=[c for c in hide if c in display_df.columns])
    
    if 'status' in display_df.columns: display_df = display_df.rename(columns={'status': 'Payment Status'})
    display_df = display_df.reset_index(drop=True)

    def highlight_trip(row):
        styles = [''] * len(row)
        if 'Payment Status' in row and 'trip_id' in row.index:
            status = str(row['Payment Status'])
            if status == 'Processed': color = 'background-color: #d4edda; color: black' 
            elif status == 'Pending': color = 'background-color: #fff3cd; color: black'
            elif status == 'Failed': color = 'background-color: #f8d7da; color: black'
            else: return styles
            try: styles[row.index.get_loc('trip_id')] = color
            except: pass
        return styles

    st.dataframe(display_df.style.apply(highlight_trip, axis=1), use_container_width=True, hide_index=True,
                 column_config={"total_paid": st.column_config.NumberColumn("Paid", format="$%.2f")})

if st.session_state['logged_in']: dashboard()
else: login_screen()
