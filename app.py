import streamlit as st
import random
import time
from typing import List
import gspread
import gspread.exceptions as gexc
from google.oauth2.service_account import Credentials

# =========================
# CONFIG
# =========================
NUM_ROUNDS = 50
REWARD_MIN = 80
REWARD_MAX = 120

# Hard-code your working Sheet ID here
SHEET_ID = "17WqxzbP-KuFpXE9a3kqt_yGCrm2SJ8mk1f75HpqO_Lw"
RESPONSES_SHEET_TITLE = "responses"  # tab where 1-row-per-respondent is stored

# Retry/backoff for the single final write
MAX_RETRIES = 5
BASE_SLEEP = 1.0  # seconds

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

# Ensure responses worksheet exists (create once if missing, add header if empty)
def ensure_responses_sheet():
    try:
        ws = sh.worksheet(RESPONSES_SHEET_TITLE)
    except gexc.WorksheetNotFound:
        ws = sh.add_worksheet(title=RESPONSES_SHEET_TITLE, rows=1, cols=20)
    # Add header if the sheet is empty
    try:
        if ws.row_count == 0 or ws.get_all_values() == []:
            ws.append_row(
                ["timestamp", "participant_id", "total_reward",
                 "switches_total", "switches_first10", "switches_last10"],
                value_input_option="RAW"
            )
    except Exception:
        # If get_all_values throttles or header already there, it's safe to ignore
        pass
    return ws

# =========================
# STATE INIT
# =========================
if "round" not in st.session_state:
    st.session_state.round = 1
if "total_reward" not in st.session_state:
    st.session_state.total_reward = 0.0
if "last_arm_clicked" not in st.session_state:
    st.session_state.last_arm_clicked = None
if "arm_rewards" not in st.session_state:
    st.session_state.arm_rewards = {"A": [], "B": [], "C": []}
if "choices" not in st.session_state:
    st.session_state.choices: List[str] = []  # one entry per round: "A"/"B"/"C"
if "participant_id" not in st.session_state:
    st.session_state.participant_id = f"user_{int(time.time())}"
if "final_logged" not in st.session_state:
    st.session_state.final_logged = False  # prevent duplicate writes

# =========================
# HELPERS
# =========================
def handle_click(arm: str):
    """Process a click on an arm and advance the round."""
    reward = random.uniform(REWARD_MIN, REWARD_MAX)
    st.session_state.arm_rewards[arm].append(reward)
    st.session_state.total_reward += reward
    st.session_state.choices.append(arm)
    st.session_state.last_arm_clicked = arm
    st.session_state.round += 1

def count_switches(seq: List[str], start_round: int, end_round: int) -> int:
    """
    Count switches between consecutive rounds within [start_round, end_round] inclusive.
    Rounds are 1-indexed. A switch is when choice_t != choice_{t-1}.
    """
    # Convert to 0-based indices for choices list
    # choices[i] corresponds to round i+1
    start_i = max(start_round, 2) - 1  # earliest transition is from round 1->2 (i=1)
    end_i = min(end_round, len(seq)) - 1
    if end_i <= 0 or start_i > end_i:
        return 0
    switches = 0
    for i in range(start_i, end_i + 1):
        if seq[i] != seq[i - 1]:
            switches += 1
    return switches

def compute_final_stats():
    choices = st.session_state.choices
    total = count_switches(choices, 1, NUM_ROUNDS)
    first10 = count_switches(choices, 1, min(10, NUM_ROUNDS))
    last10 = count_switches(choices, max(1, NUM_ROUNDS - 9), NUM_ROUNDS)
    return {
        "total_reward": float(st.session_state.total_reward),
        "switches_total": int(total),
        "switches_first10": int(first10),
        "switches_last10": int(last10),
    }

def append_final_row():
    """Append one final row with summary stats. Retries on transient errors."""
    if st.session_state.final_logged:
        return  # already written

    # Make sure responses sheet exists & has header
    ensure_responses_sheet()

    stats = compute_final_stats()
    row = [
        int(time.time()),
        st.session_state.participant_id,
        stats["total_reward"],
        stats["switches_total"],
        stats["switches_first10"],
        stats["switches_last10"],
    ]

    # Use spreadsheet-level values_append for append semantics (atomic-ish)
    rng = f"{RESPONSES_SHEET_TITLE}!A:Z"
    for attempt in range(MAX_RETRIES):
        try:
            # Small jitter to avoid many users appending at exactly same time
            time.sleep(random.uniform(0, 0.4))
            sh.values_append(
                rng,
                params={"valueInputOption": "RAW"},
                body={"values": [row]},
            )
            st.session_state.final_logged = True
            return
        except gexc.APIError:
            time.sleep(BASE_SLEEP * (2 ** attempt) + random.random() * 0.3)

    st.error("⚠️ Could not write final summary to Google Sheet after multiple retries.")

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

    # Live stats (optional)
    st.write(f"**Total Reward:** {st.session_state.total_reward:.2f}")
    # Show per-arm averages
    for arm in ["A", "B", "C"]:
        vals = st.session_state.arm_rewards[arm]
        avg = sum(vals) / len(vals) if vals else 0.0
        st.write(f"**Arm {arm} Avg Reward:** {avg:.2f}")

else:
    # Compute & show final stats
    stats = compute_final_stats()
    st.success("Experiment complete!")
    st.write(f"**Total Reward:** {stats['total_reward']:.2f}")
    st.write(f"**Switches — Total:** {stats['switches_total']}")
    st.write(f"**Switches — First 10 rounds:** {stats['switches_first10']}")
    st.write(f"**Switches — Last 10 rounds:** {stats['switches_last10']}")

    # Append exactly one final row to the sheet
    append_final_row()

    if st.session_state.final_logged:
        st.info("✅ Final summary saved to the spreadsheet.")
    else:
        st.warning("Final summary not yet saved. You can refresh and it will try again.")
