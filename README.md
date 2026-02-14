# Guardrails Chat — Groq + Local SLM Guardrails

A chat app that uses a **cloud model (Groq)** to answer you and **small models on your PC (Ollama)** to check each answer for safety and relevance before showing it. You see who generated the reply and which guards ran, so the flow is transparent.

---

## Objective

- **Answer questions** using a strong model (Groq).
- **Check every answer** locally with small models (safety, topic, optional format/PII) so nothing goes out without a basic review.
- **Show clearly** which model answered and which models acted as guardrails.

---

## What It Does (Task)

1. You type a message in the web UI.
2. Groq generates a reply (e.g. Llama 3.3 70B).
3. Local SLMs (e.g. phi3, llama3.2) run as **guardrails**: they judge the reply (pass / flag / block).
4. If any guard says **block**, you see a safe message instead of the reply. Otherwise you see the reply plus which guards ran and their result (pass/flag).
5. The UI shows **response by: [Groq model]** and **guardrails: [guard name (model): verdict]** so the LLM flow is visible.

---

## Setup

**You need:** Python 3.9+, a Groq API key, and Ollama installed and running.

1. **Get a Groq API key** at [console.groq.com](https://console.groq.com/keys).

2. **Install Ollama** from [ollama.com](https://ollama.com), start it, then pull guard models:
   ```bash
   ollama pull phi3
   ollama pull llama3.2
   ```

3. **Clone the repo** and run:
   ```bash
   cd "Guardrails using SLM's"
   python -m venv .venv
   .venv\Scripts\activate    # Windows
   pip install -r requirements.txt
   ```

4. **Create a `.env` file** in the project root:
   ```
   GROQ_API_KEY=your_key_here
   ```
   Optional: `MODEL_NAME=llama-3.3-70b-versatile` (or another [Groq model](https://console.groq.com/docs/models)).

5. **Start the app:**
   ```bash
   python run.py
   ```
   Open [http://localhost:8000](http://localhost:8000).

**Config:** `config.yaml` lets you turn guards on/off (safety, topic, format, pii) and set which Ollama model each guard uses. Increase `guard_timeout_seconds` (e.g. 90) if guards often time out.

---

## Use Cases

- **Transparent Q&A** — You see which model answered and which models checked it.
- **Local guardrails** — Safety and topic checks run on your machine (Ollama), not in the cloud.
- **Controlled strictness** — Enable only the guards you need; use “Skip guards” in the UI for a quick Groq-only reply.
- **Learning / demos** — Good for showing how a primary model plus local SLM guards can work together.

---

## Impact

- **Privacy** — Guard logic and content stay on your PC (Ollama); only the main question/answer go to Groq.
- **Trust** — Every reply is labeled with the generating model and guard results (pass/flag/block).
- **Flexibility** — You can relax or tighten behavior via `config.yaml` (timeouts, which guards run, on_safety_timeout: flag vs block).

---

## Known Issues / Limitations

- **Slow guard responses on low-spec PCs** — Local SLMs (phi3, llama3.2, etc.) can take 30–90+ seconds per guard on modest hardware. The app uses timeouts (default 60s per guard) and, when the safety guard times out, still shows the reply by default and marks it as unverified. To reduce wait: use “Skip guards” for speed, disable some guards in `config.yaml`, or increase `guard_timeout_seconds`.
- **No auth** — The web UI has no login; suitable for local or trusted use.
- **In-memory history** — Chat history is kept in memory (and in the browser); it is not persisted on the server across restarts.

---

## Quick Reference

| Item | Where |
|------|--------|
| Groq model | `.env` `MODEL_NAME` or `config.yaml` → `groq.model` |
| Enable/disable guards | `config.yaml` → `guards.<name>.enabled` |
| Guard timeout | `config.yaml` → `guard_timeout_seconds` (default 60) |
| Safety timeout = block or flag | `config.yaml` → `on_safety_timeout` (default `flag`) |
| Health / models | [http://localhost:8000/health](http://localhost:8000/health) |

**Troubleshooting:** Missing Groq key → set `GROQ_API_KEY` in `.env`. Empty `ollama_models` in `/health` → start Ollama and run `ollama pull phi3` (and llama3.2 if using topic guard). Slow replies → try “Skip guards” or increase `guard_timeout_seconds`.
