"""PS55 - Fitness Routine Planner (Streamlit UI).  Run: streamlit run app.py"""
import os

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fitness_core import (DEFAULT_MODELS, DISCLAIMER, generate_plan,
                          plan_to_dataframe, plan_to_text)

st.set_page_config(page_title="Fitness Routine Planner", page_icon="💪", layout="wide")
st.title("💪 Fitness Routine Planner")
st.caption("Generate a weekly home workout plan from your goal, level, time and equipment.")
st.warning(DISCLAIMER)

# ---------------- sidebar: LLM settings
with st.sidebar:
    st.header("LLM settings")
    provider = st.selectbox("Provider", ["Offline demo (no API)", "Gemini", "Groq", "Ollama (local)"])
    api_key, model = "", ""
    if provider in ("Gemini", "Groq"):
        env_name = "GEMINI_API_KEY" if provider == "Gemini" else "GROQ_API_KEY"
        has_env = bool(os.getenv(env_name))
        api_key = st.text_input(f"{provider} API key", type="password",
                                help=f"Leave blank to use {env_name} from .env"
                                if has_env else "Paste your free API key")
        if has_env and not api_key:
            st.success(f"Using {env_name} from .env")
    if provider != "Offline demo (no API)":
        model = st.text_input("Model", value=DEFAULT_MODELS[provider])
    if provider == "Ollama (local)":
        st.info("Make sure Ollama is running and the model is pulled: `ollama pull llama3.2`")

# ---------------- inputs
c1, c2 = st.columns(2)
with c1:
    goal = st.selectbox("Goal", ["Lose weight", "Build muscle", "Stay fit / general health",
                                 "Improve flexibility", "Increase stamina"])
    level = st.radio("Fitness level", ["Beginner", "Intermediate", "Advanced"], horizontal=True)
with c2:
    minutes = st.slider("Minutes per day", 15, 90, 30, step=5)
    days_per_week = st.slider("Workout days per week", 3, 6, 5)
equipment = st.multiselect("Equipment available",
                           ["Dumbbells", "Resistance bands", "Yoga mat", "Pull-up bar",
                            "Skipping rope", "Chair / bench"],
                           default=["Yoga mat"])
equipment_text = ", ".join(equipment) if equipment else "No equipment (bodyweight only)"

if st.button("Generate my plan", type="primary"):
    with st.spinner("Building your plan..."):
        try:
            plan, source = generate_plan(provider, goal, level, minutes, equipment_text,
                                         days_per_week, api_key, model)
            st.session_state["plan"] = plan
            st.session_state["source"] = source
        except Exception as e:  # network, key, JSON problems
            st.error(f"Could not generate the plan: {e}")
            st.info("Check your API key / internet, or switch to 'Offline demo (no API)'.")

if "plan" in st.session_state:
    plan = st.session_state["plan"]
    st.success(f"Plan ready (source: {st.session_state['source']})")
    if plan.get("summary"):
        st.subheader(plan["summary"])
    df = plan_to_dataframe(plan)
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("Day-by-day view", expanded=False):
        for d in plan["days"]:
            st.markdown(f"**{d['day']} — {d['focus']}**" + (" 😴" if d["rest_day"] else ""))
            for ex in d["exercises"]:
                st.write(f"- {ex.get('name')}: {ex.get('sets')} × {ex.get('reps')} "
                         f"(rest {ex.get('rest_seconds')}s)")
            if d["note"]:
                st.caption(d["note"])
    if plan.get("tips"):
        st.markdown("**Tips**")
        for t in plan["tips"]:
            st.write(f"- {t}")

    d1, d2 = st.columns(2)
    d1.download_button("⬇ Download CSV", df.to_csv(index=False), "workout_plan.csv", "text/csv")
    d2.download_button("⬇ Download text", plan_to_text(plan), "workout_plan.txt")
