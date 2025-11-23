import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

st.set_page_config(page_title="Driver Portal - DEBUG MODE", layout="centered", page_icon="🛠️")

# --- CONFIGURATION ---
FILE_ID = "1dwAT9fkfQY-SIOt4KmQ9gE7J4MnVSfP4" # Your CSV File ID

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'driver_data' not in st.session_state: st.session_state['driver_data'] = None
if 'driver_name' not in st.session_state: st.session_state['driver_name'] = ""

@st.cache_data(ttl=600)
def load_all_data():
    creds_dict = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    service = build('drive', 'v3', credentials=creds)
    
    try:
        request = service.files().get_media(fileId=FILE_ID)
        file_obj = io.BytesIO()
        downloader = MediaIoBaseDownload(file_obj, request)
        done = False
        while not done: status, done = downloader.next_chunk()
        file_obj.seek(0)
        
        # FORCE EVERYTHING TO STRING to avoid type mismatches
        df = pd.read_csv(file_obj, dtype=str, low_memory=False)
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def login_screen():
    st.title("🛠️ Debug Login")
    st.warning("This is a diagnostic mode to fix login issues.")
    
    with st.form("login_form"):
        driver_id_input = st.text_input("Driver ID")
        bank_pin_input = st.text_input("Last 4 Bank", type="password")
        submitted = st.form_submit_button("Test Login")
        
        if submitted:
            df = load_all_data()
            
            # 1. Clean Inputs
            u_id = str(driver_id_input).strip()
            u_bank = str(bank_pin_input).strip()
            
            st.write("--- DIAGNOSTIC RESULTS ---")
            st.write(f"**You Entered ID:** `{u_id}`")
            st.write(f"**You Entered Bank:** `{u_bank}`")
            
            # 2. Search for ID
            # We normalize the dataframe column to string and strip spaces
            if 'driver_num' in df.columns:
                # Find partial matches to see if it exists at all
                mask = df['driver_num'].astype(str).str.strip() == u_id
                user_rows = df[mask]
                
                if user_rows.empty:
                    st.error(f"❌ Driver ID `{u_id}` NOT FOUND in database.")
                    st.write("First 5 IDs in database for reference:", df['driver_num'].head().tolist())
                else:
                    st.success(f"✅ Found {len(user_rows)} records for Driver ID `{u_id}`")
                    
                    # 3. Check Bank
                    # Show what bank numbers are actually in the system for this driver
                    if 'bank' in user_rows.columns:
                        actual_banks = user_rows['bank'].astype(str).str.strip().unique().tolist()
                        st.write(f"**Bank Digits stored for this ID:** {actual_banks}")
                        
                        if u_bank in actual_banks:
                            st.success("✅ Password Match! Login successful.")
                            st.session_state['logged_in'] = True
                            st.rerun()
                        else:
                            st.error(f"❌ Password Mismatch. Database expects one of: {actual_banks}")
                            
                            # Check for "float" error (e.g. 123.0 vs 123)
                            if any('.' in x for x in actual_banks):
                                st.warning("⚠️ Formatting Warning: The database has decimals in the bank column. We need to fix the SQL export.")
                    else:
                        st.error("❌ Column 'bank' is MISSING from the CSV file.")
                        st.write("Available columns:", df.columns.tolist())

            else:
                st.error("❌ Column 'driver_num' is missing from the CSV.")

def dashboard():
    st.success("Login Logic is Fixed!")
    if st.button("Log Out / Retry"):
        st.session_state['logged_in'] = False
        st.rerun()

if st.session_state['logged_in']: dashboard()
else: login_screen()
