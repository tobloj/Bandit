import streamlit as st
import random
import gspread
from google.oauth2.service_account import Credentials
import gspread.exceptions as gexc
import time
import pandas as pd

# --- CONFIG ---
NUM_ROUNDS = 50
REWARD_MIN = 80
REWARD_MAX = 120
SHEET_ID = "17WqxzbP-KuFpXE9a3kqt_yGCrm2SJ8mk1f75HpqO_Lw"  # <-- Your working Sheet ID
# --------------

# Authenticate Google Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=SCOPES
)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

# Get or create logs worksheet
try:
    ws = sh.worksheet("logs")
except gexc.WorksheetNotFound:
    ws = sh.add_worksheet(title="logs", rows=1, cols=20)
    ws.append_row(
        ["timestamp", "participant_id", "round", "arm", "reward", "switch_count"]
    )

# Initialize session state
if "round" not in st.session_state:
    st.session_state.round = 1
if "total_reward" not in st.session_state:
    st.session_state.total_reward = 0
if "last_arm_clicked" not in st.session_state:
    st.session_state.last_arm_clicked = None
if "switch_count" not in st.session_state:
    st.session_state.switch_count = 0
if "arm_rewards" not in st.session_state:
    st.session_state.arm_rewards = {"A": [], "B": [], "C": []}
if "participant_id" not in st.session_state:
    st.session_state.participant_id = f"user_{int(time.time())}"

# Function to log to Google Sheets
def log_click(arm, reward):
    ws.append_row(
        [
            int(time.time()),
            st.session_state.participant_id,
            st.session_state.round,
            arm,
            reward,
            st.session_state.switch_count,
        ],
        value_input_option="RAW",
    )

# Function to handle clicks
def handle_click(arm):
    reward = random.uniform(REWARD_MIN, REWARD_MAX)
    st.session_state.arm_rewards[arm].append(reward)
    st.session_state.total_reward += reward

    # Count switches
    if st.session_state.last_arm_clicked and st.session_state.last_arm_clicked != arm:
        st.session_state.switch_count += 1
    st.session_state.last_arm_clicked = arm

    # Log to Google Sheets
    log_click(arm, reward)

    # Increment round
    st.session_state.round += 1


# UI
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

    # Show per-arm averages
    for arm in ["A", "B", "C"]:
        rewards = st.session_state.arm_rewards[arm]
        avg = sum(rewards) / len(rewards) if rewards else 0
        st.write(f"**Arm {arm} Avg Reward:** {avg:.2f}")

else:
    st.success("Experiment complete!")
    df = pd.DataFrame(st.session_state.arm_rewards)
    st.write("Final Rewards per Arm:")
    st.dataframe(df)
    st.write(f"Total Reward: {st.session_state.total_reward:.2f}")
    st.write(f"Total Switches: {st.session_state.switch_count}")
