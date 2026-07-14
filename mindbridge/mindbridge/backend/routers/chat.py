from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, ChatLog, IncidentLog
from schemas import ChatMessageRequest, ChatMessageResponse
from auth import get_current_user, require_role
from agents import conversation_agent, risk_assessment_agent, escalation_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("patient")),
):
    # 1. log the user's turn
    user_log = ChatLog(
        user_id=user.id, role="user", input_mode=payload.input_mode,
        message=payload.message, emotion_detected=payload.client_emotion,
    )
    db.add(user_log)
    db.commit()

    # 2. risk-assessment agent scores this turn independently
    risk = risk_assessment_agent(payload.message, payload.client_emotion)

    # 3. escalation agent decides whether a human needs to be looped in
    escalation = escalation_agent(risk)
    if escalation["escalate"]:
        db.add(IncidentLog(
            user_id=user.id, incident_type="crisis_language" if "safety net" in risk["reasoning"] else "high_stress",
            input_mode=payload.input_mode, stress_score=risk["stress_score"],
            ai_analysis=risk["reasoning"],
        ))
        db.commit()

    # 4. conversation agent drafts the reply (sees recent history for continuity)
    recent = [
        {"role": r.role, "message": r.message}
        for r in db.query(ChatLog).filter(ChatLog.user_id == user.id).order_by(ChatLog.timestamp.desc()).limit(6)
    ][::-1]
    reply = conversation_agent(payload.message, recent)
    if escalation["resource_message"]:
        reply = f"{reply}\n\n{escalation['resource_message']}"

    db.add(ChatLog(
        user_id=user.id, role="agent", input_mode=payload.input_mode,
        message=reply, stress_score=risk["stress_score"], sentiment_score=None,
    ))
    db.commit()

    return ChatMessageResponse(
        reply=reply,
        stress_score=risk["stress_score"],
        risk_level=risk["risk_level"],
        escalated=escalation["escalate"],
    )


@router.get("/history")
def get_history(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    logs = db.query(ChatLog).filter(ChatLog.user_id == user.id).order_by(ChatLog.timestamp).all()
    return [
        {"role": l.role, "message": l.message, "timestamp": l.timestamp, "stress_score": l.stress_score}
        for l in logs
    ]
