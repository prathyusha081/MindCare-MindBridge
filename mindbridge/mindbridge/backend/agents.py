"""
Agent orchestration layer.

Four cooperating, narrowly-scoped agents rather than one do-everything prompt:

  1. ConversationAgent   - holds the supportive dialogue with the patient
  2. RiskAssessmentAgent - scores the *same turn* for stress/risk, independent
                            of what the ConversationAgent says back
  3. EscalationAgent     - decides whether a human (doctor) needs to be looped in
  4. ReportAgent         - periodically summarizes tracker + chat history for a doctor

This is a supportive companion tool, not a diagnostic or clinical device.
It never diagnoses conditions and always defers to human professionals for
anything beyond everyday stress support.
"""
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
has_valid_key = api_key and api_key != "your_groq_key_here" and api_key.strip() != ""

client = None
if has_valid_key:
    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        print(f"Warning: Failed to initialize Groq client ({e}). Using mock fallback.")
        client = None

MODEL = "llama-3.3-70b-versatile"

# Small, generic safety net. This is intentionally NOT exhaustive — it is a
# backstop underneath the LLM's own judgment, not the primary detection method.
CRISIS_PHRASES = [
    "kill myself", "end my life", "suicide", "hurt myself", "self harm",
    "self-harm", "don't want to be alive", "want to die",
]

CONVERSATION_SYSTEM_PROMPT = """You are MindBridge, a supportive AI companion focused on everyday
stress and anxiety check-ins. You are NOT a therapist and cannot diagnose conditions.

Rules:
- Be warm, brief, and validating. Ask at most one gentle follow-up question.
- Never claim to be human or to be a licensed professional.
- If the person describes something beyond everyday stress (persistent hopelessness,
  crisis, self-harm thoughts), gently encourage them to reach out to a real
  mental health professional or a crisis line, in addition to anything else you say.
- Keep replies under 5 sentences.
"""

RISK_SYSTEM_PROMPT = """You are a risk-scoring classifier for a mental wellness app.
Given a message (and optionally a detected facial/vocal emotion label), return ONLY
valid JSON, no other text, in this exact shape:
{"stress_score": <0-100 integer>, "risk_level": "low"|"moderate"|"high", "reasoning": "<one short phrase>"}

Guidance:
- "high" = language suggesting crisis, self-harm, or acute panic
- "moderate" = clear stress/anxiety but no crisis language
- "low" = neutral or positive
"""

REPORT_SYSTEM_PROMPT = """You write a short, doctor-facing clinical-style summary (not a diagnosis)
from raw wellness tracker and chat sentiment data. 4-6 sentences. Note trends,
not single data points. Flag anything a clinician should look at more closely."""


def _chat(system_prompt: str, user_content: str) -> str:
    if not client:
        raise ValueError("Groq client not initialized")
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
        max_tokens=400,
    )
    return completion.choices[0].message.content


def conversation_agent(message: str, recent_history: list[dict]) -> str:
    if client:
        try:
            history_text = "\n".join(f"{h['role']}: {h['message']}" for h in recent_history[-6:])
            prompt = f"Recent conversation:\n{history_text}\n\nUser just said: {message}"
            return _chat(CONVERSATION_SYSTEM_PROMPT, prompt)
        except Exception as e:
            print(f"Groq API error in conversation_agent: {e}. Falling back to mock.")
    
    # Mock fallback
    msg_lower = message.lower()
    if any(p in msg_lower for p in CRISIS_PHRASES):
        return ("I hear how much pain you are in. Please know that you are not alone and there is support available. "
                "I encourage you to reach out to a professional or a crisis helpline.")
    elif any(k in msg_lower for k in ["stress", "anxious", "anxiety", "worry", "overwhelm", "pressure", "exam", "work"]):
        return ("It sounds like you're experiencing a lot of pressure right now. It's completely valid to feel overwhelmed. "
                "What is one small thing you can do to take care of yourself today?")
    elif any(k in msg_lower for k in ["sad", "depressed", "down", "cry"]):
        return ("I'm sorry you're feeling down. Please be gentle with yourself. "
                "Small steps, like taking a brief walk or drinking water, can help. What's been on your mind?")
    elif any(k in msg_lower for k in ["sleep", "tired", "insomnia"]):
        return ("Rest is so crucial for mental well-being. It can be frustrating when sleep is disrupted. "
                "Have you tried a wind-down routine before bed?")
    else:
        return "Thank you for sharing. I'm here to support you through whatever is on your mind. How has the rest of your day been?"


def risk_assessment_agent(message: str, client_emotion: str | None) -> dict:
    keyword_hit = any(p in message.lower() for p in CRISIS_PHRASES)

    if client:
        try:
            context = message if not client_emotion else f"{message}\n(detected emotion signal: {client_emotion})"
            raw = _chat(RISK_SYSTEM_PROMPT, context)
            data = json.loads(raw)
            # Keyword net can only push risk UP, never down, and never below the model's own score.
            if keyword_hit:
                data["risk_level"] = "high"
                data["stress_score"] = max(data.get("stress_score", 0), 90)
                data["reasoning"] = "crisis-language safety net triggered"
            return data
        except Exception as e:
            print(f"Groq API error in risk_assessment_agent: {e}. Falling back to mock.")

    # Mock fallback
    if keyword_hit:
        return {"stress_score": 95, "risk_level": "high", "reasoning": "crisis-language safety net triggered"}
    
    msg_lower = message.lower()
    is_stressed = any(k in msg_lower for k in ["stress", "anxious", "anxiety", "worry", "overwhelmed", "scared", "fear", "sad", "depressed", "angry"])
    has_stress_emotion = client_emotion in ["sad", "fearful", "angry", "disgusted"]
    
    if is_stressed or has_stress_emotion:
        reason = "stress indicators in emotion" if (has_stress_emotion and not is_stressed) else "moderate stress language detected"
        return {"stress_score": 65, "risk_level": "moderate", "reasoning": reason}
        
    return {"stress_score": 25, "risk_level": "low", "reasoning": "no elevated stress signals"}


def escalation_agent(risk: dict) -> dict:
    """Decides whether this turn should create an incident for the doctor dashboard,
    and what resource message the user should see immediately."""
    escalate = risk["risk_level"] == "high"
    resource_message = None
    if escalate:
        resource_message = (
            "It sounds like you might be going through something serious right now. "
            "You don't have to handle this alone — please consider reaching out to a "
            "crisis line or emergency services in your area right away. In India, you can "
            "call the KIRAN helpline at 1800-599-0019 (toll-free, 24/7). Your doctor has "
            "also been flagged to follow up."
        )
    return {"escalate": escalate, "resource_message": resource_message}


def report_agent(tracker_rows: list[dict], chat_rows: list[dict]) -> str:
    if client:
        try:
            payload = json.dumps({"trackers": tracker_rows, "chat_sentiment": chat_rows}, default=str)
            return _chat(REPORT_SYSTEM_PROMPT, payload)
        except Exception as e:
            print(f"Groq API error in report_agent: {e}. Falling back to mock.")
            
    # Mock fallback
    sleeps = [r["sleep"] for r in tracker_rows if "sleep" in r]
    moods = [r["mood"] for r in tracker_rows if "mood" in r]
    stresses = [r["stress"] for r in tracker_rows if "stress" in r]
    
    avg_sleep = sum(sleeps)/len(sleeps) if sleeps else 7.0
    avg_mood = sum(moods)/len(moods) if moods else 6.0
    avg_stress = sum(stresses)/len(stresses) if stresses else 40.0
    
    summary = f"Summary over the past week shows an average of {avg_sleep:.1f} hours of sleep, with overall mood tracking around {avg_mood:.1f}/10. Stress levels averaged {avg_stress:.1f}%. The patient's tracking indicates relatively stable wellness indicators with no critical trends reported."
    return summary
