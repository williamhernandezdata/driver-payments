import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="Payment Search", layout="wide", page_icon="🚕")
st.title("🚕 Driver Trip Payments Portal")

# --- CONFIGURATION ---
SPREADSHEET_NAME = "Coop trip payments table"
WORKSHEET_NAME = "data"

# --- LOAD DATA ---
@st.cache_data(ttl=600) 
def load_data():
    # Load credentials
    secrets = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets, scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Could not find tab named '{WORKSHEET_NAME}'")
        st.stop()
        
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # --- CLEAN DATA TYPES ---
    # 1. Fix Dates
    if 'job_date' in df.columns:
        df['job_date'] = pd.to_datetime(df['job_date'], errors='coerce')
    
    # 2. Fix Money Columns (Remove $ and , and make numeric)
    money_cols = [
        'total_paid', 'total_fare', 'coop_commission', 'tips', 'tolls', 
        'base_fare', 'wait_time_pay', 'stops_amount', 'cash_collected', 'darter'
    ]
    
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    return df

# --- MAIN APP LOGIC ---
with st.spinner('Fetching latest data from Google Cloud...'):
    try:
        df = load_data()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        st.stop()

if df.empty:
    st.warning("No data found.")
    st.stop()

# ==========================================
# 🔍 FILTER DASHBOARD
# ==========================================
st.markdown("### 🔍 Search Filters")

with st.expander("Open Search Options", expanded=True):
    
    # Row 1
    col1, col2, col3 = st.columns(3)
    with col1:
        search_name = st.text_input("👤 Driver Name", placeholder="e.g. Freddy")
    with col2:
        search_driver_id = st.text_input("🆔 Driver ID", placeholder="e.g. 5800905")
    with col3:
        search_trip_id = st.text_input("🚕 Trip ID", placeholder="e.g. 512345")

    # Row 2
    col4, col5, col6 = st.columns(3)
    with col4:
        nacha_options = ["All"] + sorted(list(df['nacha_title'].astype(str).unique()))
        search_nacha = st.selectbox("📄 NACHA File", nacha_options)
    with col5:
        if 'account' in df.columns:
            acc_options = ["All"] + sorted(list(df['account'].astype(str).unique()))
            search_account = st.selectbox("🏢 Account", acc_options)
        else:
            search_account = "All"
    with col6:
        if 'status' in df.columns:
            status_options = ["All"] + sorted(list(df['status'].astype(str).unique()))
            search_status = st.selectbox("✅ Payment Status", status_options)
        else:
            search_status = "All"
            
    # Row 3 (Date)
    min_date = df['job_date'].min()
    max_date = df['job_date'].max()
    date_range = st.date_input(
        "📅 Date Range", 
        value=[], # Starts empty
        min_value=min_date, 
        max_value=max_date
    )

# ==========================================
# 🔄 FILTERING LOGIC
# ==========================================
filtered_df = df.copy()

if search_name:
    # Check if first/last name cols exist, otherwise search global
    if 'first_name' in filtered_df.columns and 'last_name' in filtered_df.columns:
        filtered_df['full_name'] = filtered_df['first_name'].astype(str) + " " + filtered_df['last_name'].astype(str)
        filtered_df = filtered_df[filtered_df['full_name'].str.contains(search_name, case=False, na=False)]
    else:
        mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_name, case=False)).any(axis=1)
        filtered_df = filtered_df[mask]

if search_driver_id:
    filtered_df = filtered_df[filtered_df['driver_num'].astype(str).str.contains(search_driver_id, na=False)]

if search_trip_id:
    filtered_df = filtered_df[filtered_df['trip_id'].astype(str).str.contains(search_trip_id, na=False)]

if search_nacha != "All":
    filtered_df = filtered_df[filtered_df['nacha_title'].astype(str) == search_nacha]

if search_account != "All" and 'account' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['account'].astype(str) == search_account]

if search_status != "All":
    filtered_df = filtered_df[filtered_df['status'].astype(str) == search_status]

# Only filter by date if user picked BOTH start and end
if len(date_range) == 2:
    start_date, end_date = date_range
    mask = (filtered_df['job_date'].dt.date >= start_date) & (filtered_df['job_date'].dt.date <= end_date)
    filtered_df = filtered_df[mask]

# ==========================================
# 💰 FINANCIAL SUB-TOTALS
# ==========================================
st.markdown("---")
st.markdown("### 💰 Financial Summary")

total_paid_sum = filtered_df['total_paid'].sum() if 'total_paid' in filtered_df.columns else 0
total_comm_sum = filtered_df['coop_commission'].sum() if 'coop_commission' in filtered_df.columns else 0
total_tips_sum = filtered_df['tips'].sum() if 'tips' in filtered_df.columns else 0
total_tolls_sum = filtered_df['tolls'].sum() if 'tolls' in filtered_df.columns else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Payout", f"${total_paid_sum:,.2f}")
m2.metric("Total Commission", f"${total_comm_sum:,.2f}")
m3.metric("Total Tips", f"${total_tips_sum:,.2f}")
m4.metric("Total Tolls", f"${total_tolls_sum:,.2f}")

# ==========================================
# 🎨 COLOR STYLING & LEGEND
# ==========================================
st.markdown("---")
st.markdown("### 📋 Trip List")

# Only show legend if we are going to show colors (Safe Mode < 2000 rows)
if len(filtered_df) < 2000:
    st.markdown("""
        <style>
            .badge-green {background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 4px; font-weight: bold;}
            .badge-yellow {background-color: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-weight: bold;}
        </style>
        <p>
            <span class="badge-green">Processed</span> = Green &nbsp;&nbsp;&nbsp;
            <span class="badge-yellow">Pending</span> = Yellow
        </p>
    """, unsafe_allow_html=True)

# Highlighting function
def highlight_trip_id(row):
    styles = [''] * len(row)
    # Check for the Renamed Column "Payment Status"
    if 'Payment Status' in row and 'trip_id' in row.index:
        status = str(row['Payment Status'])
        if status == 'Processed':
            color = 'background-color: #d4edda; color: black'
        elif status == 'Pending':
            color = 'background-color: #fff3cd; color: black'
        else:
            return styles
        try:
            trip_idx = row.index.get_loc('trip_id')
            styles[trip_idx] = color
        except:
            pass
    return styles

st.markdown(f"**Showing {len(filtered_df)} trip records**")

# --- PREPARE DATA FOR DISPLAY ---

# 1. Fix Date Format
if 'job_date' in filtered_df.columns:
    filtered_df['job_date'] = filtered_df['job_date'].dt.strftime('%Y-%m-%d')

# 2. Rename Status Column
if 'status' in filtered_df.columns:
    filtered_df = filtered_df.rename(columns={'status': 'Payment Status'})

# 3. Reset Index (CRITICAL FIX for StreamlitAPIException)
filtered_df = filtered_df.reset_index(drop=True)

# 4. DECIDE: TO STYLE OR NOT TO STYLE?
if len(filtered_df) < 2000:
    final_df = filtered_df.style.apply(highlight_trip_id, axis=1)
else:
    st.info("⚠️ **Note:** Colors (Green/Yellow) are disabled because the list is too long. Use search filters to narrow down results and see status colors.")
    final_df = filtered_df

# 5. Display Table with Currency Formatting
# We added config for ALL financial columns here
st.dataframe(
    final_df, 
    use_container_width=True, 
    hide_index=True,
    height=800,
    column_config={
        "total_paid": st.column_config.NumberColumn("Total Paid", format="$%.2f"),
        "total_fare": st.column_config.NumberColumn("Total Fare", format="$%.2f"),
        "coop_commission": st.column_config.NumberColumn("Commission", format="$%.2f"),
        "tips": st.column_config.NumberColumn("Tips", format="$%.2f"),
        "tolls": st.column_config.NumberColumn("Tolls", format="$%.2f"),
        "base_fare": st.column_config.NumberColumn("Base Fare", format="$%.2f"),
        "wait_time_pay": st.column_config.NumberColumn("Wait Time", format="$%.2f"),
        "stops_amount": st.column_config.NumberColumn("Stops Amt", format="$%.2f"),
        "cash_collected": st.column_config.NumberColumn("Cash Coll.", format="$%.2f"),
        "darter": st.column_config.NumberColumn("Darter", format="$%.2f"),
    }
)
