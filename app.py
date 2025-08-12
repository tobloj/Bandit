import streamlit as st
import random
import time
import math
import pandas as pd
import gspread
import gspread.exceptions as gexc
from google.oauth2.service_account import Credentials

# =========================
# CONFIG
# =========================
NUM_ROUNDS = 50
REWARD_MIN = 80
REWARD_MAX = 120
SHEET_ID = "17WqxzbP-KuFpXE9a3kqt_yGCrm2SJ8mk1f75HpqO_Lw"  # <-- your sheet
LOG_SHEET_TITLE = "logs"
BUFFER_FLUSH_EVERY = 15            # batch size
MAX_RETRIES = 5                   # API retry attempts
BASE_SLEEP = 1.25                 # base backoff seconds

# =========================
# GOOGLE AUTH (once)
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

# Ensure log worksheet exists and has header
try:
    ws = sh.worksheet(LOG_SHEET_TITLE)
except gexc.WorksheetNotFound:
    ws = sh.add_worksheet(title=LOG_SHEET_TITLE, rows=1, cols=20)
    ws.append_row(["timestamp", "participant_id", "round", "arm", "reward", "switch_count"], value_input_option="RAW")

LOG_RANGE = f"{LOG_SHEET_TITLE}!A:Z"  # append target

# =========================
# STATE INIT
# =========================
if "round" not in st.session_state:
    st.session_state.round = 1
if "total_reward" not in st.session_state:
    st.session_state.total_reward = 0.0
if "last_arm_clicked" not in st.session_state:
    st.session_state.last_arm_clicked = None
if "switch_count" not in st.session_state:
    st.session_state.switch_count = 0
if "arm_rewards" not in st.session_state:
    st.session_state.arm_rewards = {"A": [], "B": [], "C": []}
if "participant_id" not in st.session_state:
    st.session_state.participant_id = f"user_{int(time.time())}"
if "log_buffer" not in st.session_state:
    st.session_state.log_buffer = []

# =========================
# LOGGING (batched with retries)
# =========================
def flush_buffer():
    """Append all buffered rows in one API call, with retries."""
    rows = st.session_state.log_buffer
    if not rows:
        return
    for attempt in range(MAX_RETRIES):
        try:
            # Use spreadsheet-level values_append for true batch append
            sh.values_append(
                LOG_RANGE,
                params={"valueInputOption": "RAW"},
                body={"values": rows},
            )
            st.session_state.log_buffer.clear()
            return
        except gexc.APIError as e:
            # Exponential backoff with jitter
            sleep_for = BASE_SLEEP * (2 ** attempt) + (0.2 * random.random())
            time.sleep(sleep_for)
    # If we get here, all retries failed
    st.error("⚠️ Could not write to Google Sheet after multiple retries. Your data is still buffered locally for this session.")
    # (Buffer remains; you can try flushing again later)

def enqueue_log(arm, reward):
    st.session_state.log_buffer.append([
        int(time.time()),
        st.session_state.participant_id,
        st.session_state.round,
        arm,
        float(reward),
        st.session_state.switch_count,
    ])
    # Flush when buffer reaches threshold
    if len(st.session_state.log_buffer) >= BUFFER_FLUSH_EVERY:
        flush_buffer()

# =========================
# GAME LOGIC
# =========================
def handle_click(arm):
    reward = random.uniform(REWARD_MIN, REWARD_MAX)
    st.session_state.arm_rewards[arm].append(reward)
    st.session_state.total_reward += reward

    if st.session_state.last_arm_clicked and st.session_state.last_arm_clicked != arm:
        st.session_state.switch_count += 1
    st.session_state.last_arm_clicked = arm

    enqueue_log(arm, reward)
    st.session_state.round += 1

# =========================
# UI
# =========================
st.title("3-Arm Bandit Experiment")

if st.session_state.round <= NUM_ROUNDS:
    st.subheader(f"Round {st.session_state.round} of {NUM_ROUNDS}")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("A", use_container_width=True):
            handle_click("A")
    with col2:
        if st.button("B", use_container_width=True):
            handle_click("B")
    with col3:
        if st.button("C", use_container_width=True):
            handle_click("C")

    st.write(f"**Total Reward:** {st.session_state.total_reward:.2f}")
    st.write(f"**Switch Count:** {st.session_state.switch_count}")

    for arm in ["A", "B", "C"]:
        rewards = st.session_state.arm_rewards[arm]
        avg = sum(rewards) / len(rewards) if rewards else 0.0
        st.write(f"**Arm {arm} Avg Reward:** {avg:.2f}")

else:
    flush_buffer()
    st.success("Experiment complete!")

    # Long format: one row per click
    rows = []
    for arm, vals in st.session_state.arm_rewards.items():
        for i, r in enumerate(vals, start=1):
            rows.append({"arm": arm, "click_index_for_that_arm": i, "reward": r})
    df = pd.DataFrame(rows).sort_values(["arm", "click_index_for_that_arm"])
    st.write("All Clicks (long format):")
    st.dataframe(df, use_container_width=True)

    # Summary
    summary = df.groupby("arm")["reward"].agg(["count","mean","std"]).reset_index()
    st.write("Summary:")
    st.dataframe(summary, use_container_width=True)

    st.write(f"**Total Reward:** {st.session_state.total_reward:.2f}")
    st.write(f"**Total Switches:** {st.session_state.switch_count}")
