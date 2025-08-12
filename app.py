import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="3-Arm Bandit Game", page_icon="🎰", layout="centered")

# --------- CONFIG ---------
N_ROUNDS = 50
ARMS = ["A", "B", "C"]
LOW, HIGH = 80, 120  # rewards ~ Uniform[80,120]

# --------- INIT STATE ---------
if "round" not in st.session_state:
    st.session_state.round = 0  # completed rounds
if "log" not in st.session_state:
    st.session_state.log = pd.DataFrame(
        columns=["round", "arm", "reward", "cumulative", "switched", "timestamp"]
    )
if "last_arm" not in st.session_state:
    st.session_state.last_arm = None
if "cumulative" not in st.session_state:
    st.session_state.cumulative = 0.0
if "switch_count" not in st.session_state:
    st.session_state.switch_count = 0

def reset_game():
    st.session_state.round = 0
    st.session_state.log = pd.DataFrame(
        columns=["round", "arm", "reward", "cumulative", "switched", "timestamp"]
    )
    st.session_state.last_arm = None
    st.session_state.cumulative = 0.0
    st.session_state.switch_count = 0

# --------- HEADER ---------
col_title, col_reset = st.columns([1, 0.2])
with col_title:
    st.title("🎰 3-Arm Bandit")
with col_reset:
    st.button("Reset game", on_click=reset_game, type="secondary")

# Progress / round info
current_round = st.session_state.round + 1 if st.session_state.round < N_ROUNDS else N_ROUNDS
st.progress(st.session_state.round / N_ROUNDS)
st.caption(f"Round {current_round} of {N_ROUNDS}")

# --------- ACTION HANDLER ---------
def play(arm: str):
    if st.session_state.round >= N_ROUNDS:
        return
    reward = float(np.random.uniform(LOW, HIGH))
    switched = False if st.session_state.last_arm is None else (arm != st.session_state.last_arm)
    if switched and st.session_state.last_arm is not None:
        st.session_state.switch_count += 1

    st.session_state.cumulative += reward
    st.session_state.round += 1
    st.session_state.last_arm = arm

    st.session_state.log = pd.concat(
        [
            st.session_state.log,
            pd.DataFrame(
                [{
                    "round": st.session_state.round,
                    "arm": arm,
                    "reward": reward,
                    "cumulative": st.session_state.cumulative,
                    "switched": switched,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            )
        ],
        ignore_index=True
    )

# --------- SUPER-SIZED, COLOR-CODED BUTTONS (reliable selectors) ---------
st.subheader("Choose a box")

# This CSS targets the real Streamlit DOM for columns & buttons
st.markdown(
    """
    <style>
    /* Make the three main buttons huge with full width */
    div[data-testid="stHorizontalBlock"] div[data-testid="column"] .stButton > button {
        height: 220px !important;
        width: 100% !important;
        font-size: 44px !important;
        font-weight: 800 !important;
        border-radius: 20px !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    /* A = first column: Blue */
    div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(1) .stButton > button {
        background: #2563eb !important;  /* blue-600 */
        color: #ffffff !important;
    }
    div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(1) .stButton > button:hover {
        background: #1d4ed8 !important;  /* blue-700 */
    }
    /* B = second column: Green */
    div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(2) .stButton > button {
        background: #16a34a !important;  /* green-600 */
        color: #ffffff !important;
    }
    div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(2) .stButton > button:hover {
        background: #15803d !important;  /* green-700 */
    }
    /* C = third column: Orange */
    div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(3) .stButton > button {
        background: #f97316 !important;  /* orange-500 */
        color: #ffffff !important;
    }
    div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(3) .stButton > button:hover {
        background: #ea580c !important;  /* orange-600 */
    }
    </style>
    """,
    unsafe_allow_html=True
)

colA, colB, colC = st.columns(3)
with colA:
    st.button("Box A", key="btn_A",
              disabled=st.session_state.round >= N_ROUNDS,
              on_click=play, args=("A",), use_container_width=True)
with colB:
    st.button("Box B", key="btn_B",
              disabled=st.session_state.round >= N_ROUNDS,
              on_click=play, args=("B",), use_container_width=True)
with colC:
    st.button("Box C", key="btn_C",
              disabled=st.session_state.round >= N_ROUNDS,
              on_click=play, args=("C",), use_container_width=True)

# --------- LIVE METRICS ---------
st.divider()
st.subheader("Live stats")

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Rounds played", st.session_state.round)
with m2:
    st.metric("Cumulative reward", f"{st.session_state.cumulative:,.1f}")
with m3:
    st.metric("Switches so far", st.session_state.switch_count)

# Last action details
if not st.session_state.log.empty:
    last = st.session_state.log.iloc[-1]
    st.info(
        f"Last pick: **Box {last['arm']}** — Reward: **{last['reward']:.1f}** — "
        f"Cumulative: **{last['cumulative']:.1f}**"
    )

# --------- PER-ARM SUMMARY ---------
def per_arm_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({"arm": ARMS, "plays": [0,0,0], "avg_reward": [np.nan, np.nan, np.nan]})
    g = df.groupby("arm")["reward"].agg(["count", "mean"]).reset_index()
    g = g.rename(columns={"count": "plays", "mean": "avg_reward"})
    full = pd.DataFrame({"arm": ARMS})
    g = full.merge(g, on="arm", how="left").fillna({"plays": 0, "avg_reward": np.nan})
    g["plays"] = g["plays"].astype(int)
    return g

summary = per_arm_summary(st.session_state.log)
c1, c2, c3 = st.columns(3)
for col, arm in zip([c1, c2, c3], ARMS):
    row = summary[summary["arm"] == arm].iloc[0]
    with col:
        st.metric(f"Box {arm} — plays", int(row["plays"]))
        st.caption(f"Avg reward: {'' if pd.isna(row['avg_reward']) else f'{row['avg_reward']:.1f}'}")

# --------- LOG TABLE ---------
with st.expander("See detailed log"):
    st.dataframe(
        st.session_state.log[["round", "arm", "reward", "cumulative", "switched", "timestamp"]],
        use_container_width=True,
        height=300
    )

# --------- END-OF-GAME SUMMARY ---------
if st.session_state.round >= N_ROUNDS:
    st.success("Game over! 🎉 Here are your final stats:")
    total_switches = int(st.session_state.switch_count)

    df = st.session_state.log.copy()
    first10 = int(df[df["round"] <= 10]["switched"].sum())
    last10 = int(df[df["round"] > N_ROUNDS - 10]["switched"].sum())

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.metric("Total reward", f"{st.session_state.cumulative:,.1f}")
    with f2:
        st.metric("Total switches", total_switches)
    with f3:
        st.metric("Switches (Rounds 1–10)", first10)
    with f4:
        st.metric(f"Switches (Rounds {N_ROUNDS-9}–{N_ROUNDS})", last10)

    st.caption("You can reset the game above to play again.")

# --------- CSV DOWNLOAD ---------
if not st.session_state.log.empty:
    csv = st.session_state.log.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download log as CSV",
        data=csv,
        file_name="bandit_game_log.csv",
        mime="text/csv"
    )