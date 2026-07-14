# MindBridge — Agentic AI Mental Wellness Companion

A multi-agent AI system where a patient chats with a supportive AI companion (text, voice,
or webcam-based), and a doctor monitors trends and incidents through a role-restricted
dashboard. Built as a portfolio project bridging **IAM/access-control engineering** and
**applied GenAI/agentic systems**.

> **Not a medical device.** This is a wellness-support demo. It does not diagnose
> conditions and is not a substitute for licensed care. See the in-app disclaimer.

---

## Why this project, and how it's scoped

The original concept (in `research/` — kept as a roadmap, not implemented) explored fusing
EEG, video, audio, and text for clinical-grade anxiety detection. That's a genuine research
problem, not something a portfolio project can honestly claim to run in production. This build
instead ships a real, working system across three input modes that **are** achievable without
specialized hardware:

| Modality | How it actually works here |
|---|---|
| Text | Direct to the LLM-based agent pipeline |
| Voice | Browser's native Speech-to-Text (Web Speech API) → same text pipeline |
| Video | Client-side facial-expression model (face-api.js, runs in-browser — no video ever leaves the device) → an emotion label passed alongside the text |

This is the honest, defensible version of "multimodal" for a project you can demo live.

## Architecture: four cooperating agents, not one prompt

```
User message ──▶ ConversationAgent   (drafts a warm, bounded reply)
             ├─▶ RiskAssessmentAgent (scores THIS turn independently: stress 0-100, risk level)
             │        │
             │        ▼
             └─▶ EscalationAgent     (decides: does a human need to be looped in?)
                      │
                      ├─ if high risk → creates an Incident row the doctor's
                      │                  dashboard surfaces, + shows the user a
                      │                  real crisis-line resource immediately
                      └─ ReportAgent  (on-demand: turns a week of tracker + chat
                                        data into a doctor-facing summary)
```

Each agent has a single narrow responsibility and its own system prompt — this is what makes
it "agentic" rather than a single chatbot: the risk score is never influenced by what the
conversational reply *says*, only by what the user *said*, which matters for safety (a warm
reply shouldn't be able to suppress a risk flag).

A small keyword safety net sits underneath the LLM's own risk classification and can only
push the risk level **up**, never down — so a model mistake can't silently downgrade a
crisis signal.

## Access control: PBAC principles, kept simple

Per your call to not over-engineer this build: it's plain role-based auth (JWT, `patient` /
`doctor`), not a full PlainID-style policy engine. But the *shape* of the access model still
follows PBAC thinking, which is the differentiator worth calling out to recruiters:

- A doctor can only read data for patients explicitly assigned to them (`doctor_id` on the
  patient record) — checked on every doctor route in `routers/doctor.py`.
- Every doctor read of patient data is written to an `AuditLog` row — the same instinct as an
  authorization audit trail in a real PBAC/IGA system.
- If you want to extend this toward your actual professional differentiator, the natural next
  step is swapping `require_role()` + `_assert_owns_patient()` for real PlainID policy
  evaluation calls — that's a strong "V2" talking point in an interview.

## Stack

- **Backend:** FastAPI + SQLAlchemy + SQLite (swap `DATABASE_URL` for Postgres in prod)
- **LLM:** Groq (`llama-3.3-70b-versatile`) — free tier, same choice as your DLP Gateway project
- **Frontend:** single-file HTML/JS (no build step), Chart.js for trend graphs
- **Auth:** JWT, bcrypt password hashing

## Running locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your free Groq key from console.groq.com
uvicorn main:app --reload
```

Open `frontend/index.html` directly in a browser (or serve it with any static server).
Update `API_BASE` at the top of the `<script>` block if your backend isn't on
`localhost:8000`.

## Deploying (zero-cost, same pattern as your other projects)

- **Backend:** Render (free web service) — set `GROQ_API_KEY`, `JWT_SECRET`, and
  `DATABASE_URL` as environment variables in the dashboard.
- **Frontend:** Netlify — drag-and-drop the `frontend/` folder, update `API_BASE` to your
  Render URL first.

## What's genuinely working vs. what's a roadmap item

**Working end-to-end:** signup/login with roles, text/voice/video chat input, live agent
pipeline (conversation + risk + escalation), daily and mental-health trackers, AI weekly
report generation, doctor dashboard with trend charts, incident feed, and review notes,
per-patient access control, audit logging.

**Roadmap (say this explicitly in interviews, don't imply it's built):** EEG integration,
a production-grade CV model (face-api.js here is a lightweight demo model, not clinical-grade),
real-time push notifications to doctors, HIPAA-grade infrastructure hardening, a proper PBAC
policy engine in place of the simple role check.

## Resume bullet (draft)

> Designed and built MindBridge, a multi-agent GenAI wellness platform (FastAPI, Groq LLM,
> SQLAlchemy) with independent conversation, risk-assessment, and escalation agents; implemented
> role-scoped access control and audit logging for doctor–patient data boundaries, and shipped
> text/voice/webcam input via browser-native APIs — deployed end-to-end at zero infrastructure cost.
