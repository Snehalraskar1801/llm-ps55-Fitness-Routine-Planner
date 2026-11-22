"""Core logic for PS55 - Fitness Routine Planner.

Takes goal, fitness level, minutes per day and equipment, asks an LLM
(Gemini / Groq / Ollama) for a weekly plan as JSON, and parses it into a
pandas DataFrame. Includes an offline rule-based generator so the app
works even without an API key.
"""
import json
import os
import re

import pandas as pd
import requests

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIMEOUT = 60

DISCLAIMER = ("General fitness information only - not medical advice. "
              "Consult a doctor before starting any new exercise routine.")


# ---------------------------------------------------------------- prompt
def build_prompt(goal, level, minutes, equipment, days_per_week=5):
    rest_days = 7 - days_per_week
    return f"""You are a certified beginner-friendly fitness coach.
Create a 7-day home workout plan.

User details:
- Goal: {goal}
- Fitness level: {level}
- Time available per workout: {minutes} minutes
- Equipment available: {equipment}
- Workout days per week: {days_per_week} (so exactly {rest_days} rest day(s))

Rules:
- Use ONLY the listed equipment (bodyweight is always allowed).
- Every workout day starts with a warm-up and ends with a cool-down/stretch.
- Fit each workout inside {minutes} minutes.
- Give sets, reps (or seconds for holds) and rest between sets for every exercise.
- Rest days must have an empty exercise list and a short recovery tip.
- Keep it safe for a {level.lower()}.

Return ONLY valid JSON in exactly this shape, no extra text:
{{
  "summary": "one-line overview of the plan",
  "days": [
    {{
      "day": "Monday",
      "focus": "e.g. Full body / Cardio / Rest",
      "rest_day": false,
      "exercises": [
        {{"name": "Push-ups", "sets": 3, "reps": "10", "rest_seconds": 45}}
      ],
      "note": "short tip"
    }}
  ],
  "tips": ["tip 1", "tip 2", "tip 3"]
}}
The "days" array must contain all 7 days from Monday to Sunday in order."""


# ---------------------------------------------------------------- LLM calls
def _call_gemini(prompt, api_key, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}}
    r = requests.post(url, json=body, headers={"x-goog-api-key": api_key}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt, api_key, model):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "temperature": 0.7,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "user", "content": prompt}]},
        timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_ollama(prompt, model, host="http://localhost:11434"):
    r = requests.post(f"{host}/api/chat",
                      json={"model": model, "stream": False, "format": "json",
                            "messages": [{"role": "user", "content": prompt}]},
                      timeout=300)
    r.raise_for_status()
    return r.json()["message"]["content"]


DEFAULT_MODELS = {"Gemini": "gemini-2.5-flash",
                  "Groq": "llama-3.3-70b-versatile",
                  "Ollama (local)": "llama3.2"}


def call_llm(provider, prompt, api_key="", model=""):
    model = model or DEFAULT_MODELS[provider]
    if provider == "Gemini":
        return _call_gemini(prompt, api_key or os.getenv("GEMINI_API_KEY", ""), model)
    if provider == "Groq":
        return _call_groq(prompt, api_key or os.getenv("GROQ_API_KEY", ""), model)
    if provider == "Ollama (local)":
        return _call_ollama(prompt, model)
    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------- parsing
def extract_json(text):
    """Parse JSON even if the model wrapped it in ``` fences or added text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Model did not return JSON.")
        return json.loads(text[start:end + 1])


def validate_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("days"), list) or not plan["days"]:
        raise ValueError("Plan has no 'days' list.")
    for d in plan["days"]:
        d.setdefault("day", "")
        d.setdefault("focus", "")
        d.setdefault("rest_day", not d.get("exercises"))
        d.setdefault("exercises", [])
        d.setdefault("note", "")
    plan.setdefault("summary", "")
    plan.setdefault("tips", [])
    return plan


def plan_to_dataframe(plan):
    rows = []
    for d in plan["days"]:
        if d["rest_day"] or not d["exercises"]:
            rows.append({"Day": d["day"], "Focus": d["focus"] or "Rest",
                         "Exercise": "REST DAY", "Sets": "-", "Reps": "-",
                         "Rest (sec)": "-", "Note": d["note"]})
            continue
        for i, ex in enumerate(d["exercises"]):
            rows.append({"Day": d["day"] if i == 0 else "",
                         "Focus": d["focus"] if i == 0 else "",
                         "Exercise": ex.get("name", ""),
                         "Sets": ex.get("sets", ""),
                         "Reps": ex.get("reps", ""),
                         "Rest (sec)": ex.get("rest_seconds", ""),
                         "Note": d["note"] if i == 0 else ""})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- offline generator
BODYWEIGHT = {
    "push": ["Push-ups", "Pike push-ups", "Tricep dips (on chair)"],
    "pull": ["Superman hold", "Reverse snow angels", "Towel rows (door/table)"],
    "legs": ["Bodyweight squats", "Lunges", "Glute bridges", "Calf raises"],
    "core": ["Plank", "Bicycle crunches", "Mountain climbers", "Leg raises"],
    "cardio": ["Jumping jacks", "High knees", "Burpees", "Skater hops"],
}
DUMBBELL = {
    "push": ["Dumbbell floor press", "Dumbbell shoulder press"],
    "pull": ["One-arm dumbbell row", "Dumbbell bicep curls"],
    "legs": ["Goblet squats", "Dumbbell Romanian deadlift"],
}
BAND = {
    "pull": ["Resistance band rows", "Band pull-aparts"],
    "legs": ["Banded squats", "Banded glute kickbacks"],
}
YOGA = ["Sun salutation", "Downward dog hold", "Child's pose", "Cat-cow stretch"]

REPS = {"Beginner": (2, "10"), "Intermediate": (3, "12"), "Advanced": (4, "15")}
SPLITS = {
    "Lose weight": ["cardio", "legs", "cardio", "push", "cardio", "core", "pull"],
    "Build muscle": ["push", "legs", "pull", "core", "push", "legs", "pull"],
    "Stay fit / general health": ["cardio", "legs", "push", "core", "pull", "cardio", "legs"],
    "Improve flexibility": ["yoga", "core", "yoga", "legs", "yoga", "core", "yoga"],
    "Increase stamina": ["cardio", "legs", "cardio", "core", "cardio", "push", "pull"],
}


def _pool(kind, equipment):
    if kind == "yoga":
        return YOGA
    pool = list(BODYWEIGHT.get(kind, []))
    eq = equipment.lower()
    if "dumbbell" in eq:
        pool = DUMBBELL.get(kind, []) + pool
    if "band" in eq:
        pool = BAND.get(kind, []) + pool
    return pool


def offline_plan(goal, level, minutes, equipment, days_per_week=5):
    sets, reps = REPS.get(level, REPS["Beginner"])
    n_ex = max(3, min(8, (int(minutes) - 10) // 6))
    split = SPLITS.get(goal, SPLITS["Stay fit / general health"])
    rest_idx = {0: [], 1: [6], 2: [2, 6], 3: [2, 4, 6], 4: [1, 3, 5, 6]}
    rest_days = set(rest_idx.get(7 - days_per_week, [2, 6])[:7 - days_per_week])
    days = []
    for i, name in enumerate(DAYS):
        if i in rest_days:
            days.append({"day": name, "focus": "Rest", "rest_day": True, "exercises": [],
                         "note": "Light walk, stretching and 7-8 hours of sleep."})
            continue
        kind = split[i]
        pool = _pool(kind, equipment)
        if kind not in ("cardio", "yoga"):
            pool = pool + _pool("core", equipment)
        chosen = [pool[j % len(pool)] for j in range(n_ex)]
        chosen = list(dict.fromkeys(chosen))
        exercises = [{"name": "Warm-up: marching + arm circles", "sets": 1,
                      "reps": "3 min", "rest_seconds": 0}]
        for e in chosen:
            hold = e in ("Plank", "Superman hold", "Downward dog hold", "Child's pose")
            exercises.append({"name": e, "sets": sets,
                              "reps": "30 sec" if hold else reps,
                              "rest_seconds": 30 if level == "Advanced" else 45})
        exercises.append({"name": "Cool-down stretching", "sets": 1,
                          "reps": "3 min", "rest_seconds": 0})
        days.append({"day": name, "focus": kind.capitalize(), "rest_day": False,
                     "exercises": exercises,
                     "note": f"Fit in about {minutes} min. Stop if you feel pain."})
    return {"summary": f"Offline {level.lower()} plan for '{goal}', {minutes} min/day.",
            "days": days,
            "tips": ["Drink water before and after workouts.",
                     "Increase reps slowly each week.",
                     "Sleep 7-8 hours for recovery."]}


# ---------------------------------------------------------------- main entry
def generate_plan(provider, goal, level, minutes, equipment, days_per_week=5,
                  api_key="", model=""):
    """Returns (plan_dict, source_string)."""
    if provider == "Offline demo (no API)":
        return offline_plan(goal, level, minutes, equipment, days_per_week), "offline"
    prompt = build_prompt(goal, level, minutes, equipment, days_per_week)
    raw = call_llm(provider, prompt, api_key, model)
    return validate_plan(extract_json(raw)), provider


def plan_to_text(plan):
    lines = [plan.get("summary", ""), ""]
    for d in plan["days"]:
        lines.append(f"{d['day']} - {d['focus']}")
        if d["rest_day"] or not d["exercises"]:
            lines.append("  REST DAY")
        for ex in d["exercises"]:
            lines.append(f"  - {ex.get('name')}: {ex.get('sets')} x {ex.get('reps')} "
                         f"(rest {ex.get('rest_seconds')}s)")
        if d["note"]:
            lines.append(f"  Note: {d['note']}")
        lines.append("")
    lines.append("Tips: " + "; ".join(plan.get("tips", [])))
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
