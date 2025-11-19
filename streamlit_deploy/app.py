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
    # Ensure dates are actual dates for the date picker to work
    if 'job_date' in df.columns:
        df['job_date'] = pd.to_datetime(df['job_date'], errors='coerce')
    
    # Ensure numeric columns are treated as numbers
    if 'total_paid' in df.columns:
        df['total_paid'] = pd.to_numeric(df['total_paid'], errors='coerce').fillna(0)
        
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
# 🔍 FILTER DASHBOARD SECTION
# ==========================================
st.markdown("### 🔍 Search Filters")

# We use an "Expander" so the filters don't clutter the screen forever. 
# Users can click to hide/show them.
with st.expander("Open Search Options", expanded=True):
    
    # Row 1: Key Identifiers
    col1, col2, col3 = st.columns(3)
    with col1:
        search_name = st.text_input("👤 Driver Name (First or Last)", placeholder="e.g. Freddy")
    with col2:
        search_driver_id = st.text_input("🆔 Driver ID", placeholder="e.g. 5800905")
    with col3:
        search_trip_id = st.text_input("🚕 Trip ID", placeholder="e.g. 512345")

    # Row 2: Status & Banking
    col4, col5, col6 = st.columns(3)
    with col4:
        # Get unique NACHA titles for a dropdown (easier than typing)
        nacha_options = ["All"] + sorted(list(df['nacha_title'].astype(str).unique()))
        search_nacha = st.selectbox("xBaa NACHA File", nacha_options)
    with col5:
        # Get unique Statuses for a dropdown
        if 'status' in df.columns:
            status_options = ["All"] + sorted(list(df['status'].astype(str).unique()))
            search_status = st.selectbox("✅ Status", status_options)
        else:
            search_status = "All"
    with col6:
        # Date Range Picker
        min_date = df['job_date'].min()
        max_date = df['job_date'].max()
        date_range = st.date_input("jv Date Range", [min_date, max_date])

# ==========================================
# 🔄 FILTERING LOGIC
# ==========================================
filtered_df = df.copy()

# 1. Driver Name Filter
if search_name:
    # Combine First and Last name columns for search if they exist
    if 'first_name' in filtered_df.columns and 'last_name' in filtered_df.columns:
        filtered_df['full_name'] = filtered_df['first_name'].astype(str) + " " + filtered_df['last_name'].astype(str)
        filtered_df = filtered_df[filtered_df['full_name'].str.contains(search_name, case=False, na=False)]
    else:
        # Fallback global search if columns are named differently
        mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_name, case=False)).any(axis=1)
        filtered_df = filtered_df[mask]

# 2. Driver ID Filter
if search_driver_id:
    # Convert to string to avoid "text vs number" errors
    filtered_df = filtered_df[filtered_df['driver_num'].astype(str).str.contains(search_driver_id, na=False)]

# 3. Trip ID Filter
if search_trip_id:
    filtered_df = filtered_df[filtered_df['trip_id'].astype(str).str.contains(search_trip_id, na=False)]

# 4. NACHA Filter
if search_nacha != "All":
    filtered_df = filtered_df[filtered_df['nacha_title'].astype(str) == search_nacha]

# 5. Status Filter
if search_status != "All":
    filtered_df = filtered_df[filtered_df['status'].astype(str) == search_status]

# 6. Date Filter
if len(date_range) == 2:
    start_date, end_date = date_range
    # Filter rows where job_date is within range
    mask = (filtered_df['job_date'].dt.date >= start_date) & (filtered_df['job_date'].dt.date <= end_date)
    filtered_df = filtered_df[mask]

# ==========================================
# 📊 DISPLAY RESULTS
# ==========================================
st.markdown("---")
st.metric("Total Records Found", len(filtered_df))

# Format the date columns nicely for display (removes the "00:00:00" time part)
if 'job_date' in filtered_df.columns:
    filtered_df['job_date'] = filtered_df['job_date'].dt.strftime('%Y-%m-%d')

st.dataframe(
    filtered_df, 
    use_container_width=True, 
    hide_index=True
)
