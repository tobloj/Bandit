import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import time
import gspread.exceptions as gexc

st.title("Google Sheets Connection Test")

# --- Put YOUR Sheet ID here (between the quotes) ---
SHEET_ID = "17WqxzbP-KuFpXE9a3kqt_yGCrm2SJ8mk1f75HpqO_Lw"
# ---------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

try:
    # Auth from secrets (service account JSON ONLY)
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    gc = gspread.authorize(creds)

    # Open spreadsheet by literal ID (NOT via st.secrets)
    sh = gc.open_by_key(SHEET_ID)

    # Use or create "logs" tab
    try:
        ws = sh.worksheet("logs")
    except gexc.WorksheetNotFound:
        ws = sh.add_worksheet(title="logs", rows=1, cols=10)
        ws.append_row(["timestamp", "note"])

    if st.button("Write test row"):
        now = int(time.time())
        ws.append_row([now, "Hello from Streamlit"], value_input_option="RAW")
        st.success(f"✅ Row written at {now}")

except gexc.APIError as e:
    st.error("Google API Error")
    st.exception(e)
except KeyError as e:
    st.error("Missing key in st.secrets (likely gcp_service_account).")
    st.write("Top-level secret keys:", list(st.secrets.keys()))
    st.exception(e)
except Exception as e:
    st.error("Unexpected error")
    st.exception(e)
