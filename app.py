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

SHEET_ID = "17WqxzbP-KuFpXE9a3kqt_yGCrm2SJ8mk1f75HpqO_Lw"   # <-- your working Sheet ID
RESPONSES_TAB = "responses"                                 # tab must exist with header
SAVE_MODE_AUTO = False                                      # False = manual "Save" button (recommended)
MAX_RETRIES = 8
BASE_SLEEP = 0.8  # seconds

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
    st.session_state.choices: List[str] = []
if "participant_id" not in st.session_state:
    st.session_state.participant_id = f"user_{int(time.time())}"
if "final_logged" not in st.session_state:
    st.session_state.final_logged = False
if "last_save_error" not in st.session_state:
    st.session_state.last_save_error = ""

# =========================
# HELPERS
# =========================
def handle_click(arm: str):
    reward = random.uniform(REWARD_MIN, REWARD_MAX)
    st.session_state.arm_rewards[arm].append(reward)
    st.session_state.total_reward += reward
    st.session_state.choices.append(arm)
    st.session_state.last_arm_clicked = arm
    st.session_state.round += 1

def count_switches(seq: List[str], start_round: int, end_round: int) -> int:
    # Count transitions within [start_round, end_round]
    start_i = max(start_round, 2) - 1   # transitions start at round 2 -> index 1
    end_i = min(end_round, len(seq)) - 1
    if end_i <= 0 or start_i > end_i:
        return 0
    return sum(1 for i in range(start_i, end_i + 1) if seq[i] != seq[i - 1])

def compute_final_stats():
    total = count_switches(st.session_state.choices, 1, NUM_ROUNDS)
    first10 = count_switches(st.session_state.choices, 1, min(10, NUM_ROUNDS))
    last10 = count_switches(st.session_state.choices, max(1, NUM_ROUNDS - 9), NUM_ROUNDS)
    return {
        "total_reward": float(st.session_state.total_reward),
        "switches_total": int(total),
        "switches_first10": int(first10),
        "switches_last10": int(last10),
    }

def save_to_sheet(stats) -> bool:
    """Append one row to Google Sheets with retries. No calls until invoked."""
    if st.session_state.final_logged:
        return True

    # Auth lazily at save-time (reduces API load during gameplay)
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # Prepare row
    row = [
        int(time.time()),
        st.session_state.participant_id,
        stats["total_reward"],
        stats["switches_total"],
        stats["switches_first10"],
        stats["switches_last10"],
    ]
    rng = f"{RESPONSES_TAB}!A:F"

    for attempt in range(MAX_RETRIES):
        try:
            # jitter spreads simultaneous completions
            time.sleep(random.uniform(0.0, 0.7) + attempt * 0.15)
            sh.values_append(
                rng,
                params={"valueInputOption": "RAW"},
                body={"values": [row]},
            )
            st.session_state.final_logged = True
            st.session_state.last_save_error = ""
            return True
        except gexc.APIError as e:
            st.session_state.last_save_error = str(e)
            time.sleep(BASE_SLEEP * (2 ** attempt) + random.random() * 0.4)

    return False

# =========================
# UI
# =========================
st.title("3-Arm Bandit Experiment")

if st.session_state.round <= NUM_ROUNDS:
    st.subheader(f"Round {st.session_state.round} of {NUM_ROUNDS}")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("A", use_container_width=True):
            handle_click("A")
    with c2:
        if st.button("B", use_container_width=True):
            handle_click("B")
    with c3:
        if st.button("C", use_container_width=True):
            handle_click("C")

    st.write(f"**Total Reward:** {st.session_state.total_reward:.2f}")
    for arm in ["A", "B", "C"]:
        vals = st.session_state.arm_rewards[arm]
        avg = sum(vals) / len(vals) if vals else 0.0
        st.write(f"**Arm {arm} Avg Reward:** {avg:.2f}")

else:
    stats = compute_final_stats()
    st.success("Experiment complete!")

    st.write(f"**Total Reward:** {stats['total_reward']:.2f}")
    st.write(f"**Switches — Total:** {stats['switches_total']}")
    st.write(f"**Switches — First 10:** {stats['switches_first10']}")
    st.write(f"**Switches — Last 10:** {stats['switches_last10']}")

    # ---- SAVE SECTION ----
    if not st.session_state.final_logged:
        if SAVE_MODE_AUTO:
            ok = save_to_sheet(stats)
            if ok:
                st.info("✅ Final summary saved to the spreadsheet.")
            else:
                st.warning("Could not save automatically. Please click the button to try again.")
        if not SAVE_MODE_AUTO:
            if st.button("Save final summary to Google Sheet", type="primary"):
                ok = save_to_sheet(stats)
                if ok:
                    st.info("✅ Final summary saved to the spreadsheet.")
                else:
                    st.error("Failed to save. Please click again in a few seconds.")
                    if st.session_state.last_save_error:
                        with st.expander("Show error details"):
                            st.code(st.session_state.last_save_error)
    else:
        st.info("✅ Final summary already saved.")

    # Always provide a local backup download
    import csv, io
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["timestamp","participant_id","total_reward",
                "switches_total","switches_first10","switches_last10"])
    w.writerow([int(time.time()), st.session_state.participant_id,
                stats["total_reward"], stats["switches_total"],
                stats["switches_first10"], stats["switches_last10"]])
    st.download_button("Download your summary as CSV (backup)",
                       data=output.getvalue(), file_name="bandit_summary.csv", mime="text/csv")
