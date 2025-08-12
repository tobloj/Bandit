def log_event(event: str, details: dict):
    import gspread
    from google.oauth2.service_account import Credentials
    import time

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["SHEET_ID"])
    try:
        ws = sh.worksheet("logs")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="logs", rows=1, cols=20)
        ws.append_row(["timestamp", "participant_id", "round", "arm", "reward", "event"])
    ws.append_row([
        int(time.time()),
        st.session_state.get("participant_id", ""),
        st.session_state.get("round", ""),
        st.session_state.get("last_arm_clicked", ""),
        st.session_state.get("last_reward", ""),
        event,
    ], value_input_option="RAW")
