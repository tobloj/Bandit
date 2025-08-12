import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import time

st.title("Google Sheets Connection Test")

# Required Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    # Authenticate using the JSON from Streamlit secrets
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    gc = gspread.authorize(creds)

    # Open the spreadsheet by ID (stored in secrets)
    sh = gc.open_by_key(st.secrets["SHEET_ID"])

    # Use (or create) a worksheet called "logs"
    try:
        ws = sh.worksheet("logs")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="logs", rows=1, cols=10)
        ws.append_row(["timestamp", "note"])

    # Button to write a test row
    if st.button("Write test row"):
        now = int(time.time())
        ws.append_row([now, "Hello from Streamlit"], value_input_option="RAW")
        st.success(f"✅ Row written at timestamp {now}")

except Exception as e:
    st.error("Something went wrong")
    st.exception(e)
