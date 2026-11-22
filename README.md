# PS55 - Fitness Routine Planner

Generates a weekly home workout plan (sets, reps, rest days) from goal, fitness level,
minutes per day and equipment, using an LLM (Gemini / Groq / Ollama). Includes an
offline demo mode that needs no API key.

> General fitness information only - not medical advice. Consult a doctor first.

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
Optional: copy `.env.example` to `.env` and add `GEMINI_API_KEY` (free at aistudio.google.com)
or `GROQ_API_KEY` (free at console.groq.com). Or paste the key in the sidebar.

## Test
```
python test_core.py
```

## Files
- `app.py` - Streamlit UI
- `fitness_core.py` - prompt, LLM calls, JSON parsing, offline generator
- `test_core.py` - tests
