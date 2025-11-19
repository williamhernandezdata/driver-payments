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
@st.cache_data(ttl=600) # Cache data for 10 minutes
def load_data():
    # Load credentials from Streamlit Cloud Secrets
    # We will set this up in Step 4
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
    return pd.DataFrame(data)

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

# --- SIDEBAR FILTERS ---
st.sidebar.header("🔍 Search Filters")
search_term = st.sidebar.text_input("Global Search (Name, ID, Amount, etc.)")

# --- FILTER LOGIC ---
filtered_df = df.copy()

if search_term:
    # Convert all columns to string and search for the term (case-insensitive)
    mask = filtered_df.astype(str).apply(
        lambda x: x.str.contains(search_term, case=False)
    ).any(axis=1)
    filtered_df = filtered_df[mask]

# --- DISPLAY ---
st.metric("Total Records Found", len(filtered_df))
st.dataframe(filtered_df, use_container_width=True, hide_index=True)