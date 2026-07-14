from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, DailyTracker, MentalHealthTracker, IncidentLog
from schemas import DailyTrackerRequest, MentalHealthEntryRequest, IncidentLogRequest, ChatMessageRequest
from fastapi import UploadFile, File, Form
from auth import require_role
from agents import live_companion_agent, live_companion_analysis, transcribe_audio

router = APIRouter(prefix="/trackers", tags=["trackers"])


@router.post("/daily")
def add_daily_entry(payload: DailyTrackerRequest, db: Session = Depends(get_db),
                     user: User = Depends(require_role("patient"))):
    entry = DailyTracker(user_id=user.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    return {"status": "saved"}


@router.get("/daily")
def get_daily_entries(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rows = db.query(DailyTracker).filter(DailyTracker.user_id == user.id).order_by(DailyTracker.date).all()
    return [
        {"date": r.date, "sleep_hours": r.sleep_hours, "water_intake": r.water_intake,
         "exercise_minutes": r.exercise_minutes, "mood_score": r.mood_score, "food_quality": r.food_quality}
        for r in rows
    ]


@router.post("/mental-health")
def add_mh_entry(payload: MentalHealthEntryRequest, db: Session = Depends(get_db),
                  user: User = Depends(require_role("patient"))):
    entry = MentalHealthTracker(user_id=user.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    return {"status": "saved"}


@router.get("/mental-health")
def get_mh_entries(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rows = db.query(MentalHealthTracker).filter(MentalHealthTracker.user_id == user.id).order_by(MentalHealthTracker.date).all()
    return [
        {"date": r.date, "stress_score": r.stress_score, "anxiety_score": r.anxiety_score,
         "depression_score": r.depression_score, "focus_score": r.focus_score, "energy_level": r.energy_level, "notes": r.notes}
        for r in rows
    ]


@router.post("/incident")
def add_incident(payload: IncidentLogRequest, db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    entry = IncidentLog(
        user_id=user.id,
        incident_type=payload.incident_type,
        notes=payload.notes,
        input_mode=payload.input_mode,
        stress_score=85.0 if "panic" in payload.incident_type.lower() else 65.0,
        ai_analysis="Manual incident log entry by patient.",
        resolved=False
    )
    db.add(entry)
    db.commit()
    return {"status": "saved"}


@router.get("/incident")
def get_incidents(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rows = db.query(IncidentLog).filter(
        IncidentLog.user_id == user.id,
        IncidentLog.incident_type.notin_(["user_utterance", "agent_reply"])
    ).order_by(IncidentLog.timestamp.desc()).all()
    return [
        {"id": r.id, "type": r.incident_type, "notes": r.notes, "input_mode": r.input_mode,
         "stress_score": r.stress_score, "analysis": r.ai_analysis, "timestamp": r.timestamp, "resolved": r.resolved}
        for r in rows
    ]


@router.post("/incident/companion")
def incident_companion_chat(payload: ChatMessageRequest, db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    from datetime import datetime, timedelta
    
    # Fetch recent incident dialog history for context
    recent_logs = db.query(IncidentLog).filter(
        IncidentLog.user_id == user.id,
        IncidentLog.incident_type.in_(["user_utterance", "agent_reply"])
    ).order_by(IncidentLog.timestamp.desc()).limit(6).all()
    
    recent = [
        {"role": "user" if r.incident_type == "user_utterance" else "agent", "message": r.notes or ""}
        for r in recent_logs
    ][::-1]

    # Get stabilizing response and classification details
    analysis = live_companion_analysis(payload.message, recent)
    reply = analysis["reply"]
    stress_score = float(analysis["stress_score"])
    emotion = analysis["emotion"]
    ai_analysis = analysis["ai_analysis"]
    is_incident = analysis["is_incident"]

    # Log parent incident alert if the AI identifies this as an active panic event
    if is_incident or stress_score > 60:
        time_threshold = datetime.utcnow() - timedelta(minutes=30)
        recent_panic = db.query(IncidentLog).filter(
            IncidentLog.user_id == user.id,
            IncidentLog.incident_type.notin_(["user_utterance", "agent_reply"]),
            IncidentLog.timestamp >= time_threshold
        ).first()
        
        if not recent_panic:
            panic_alert = IncidentLog(
                user_id=user.id,
                incident_type="panic_incident",
                notes=f"Text Panic Trigger: {payload.message}",
                input_mode=payload.input_mode,
                stress_score=stress_score,
                ai_analysis=f"AI Analysis: {ai_analysis} | Detected emotion: {emotion}",
                resolved=False
            )
            db.add(panic_alert)

    # Log this conversation turn as incident records
    user_entry = IncidentLog(
        user_id=user.id,
        incident_type="user_utterance",
        notes=payload.message,
        input_mode=payload.input_mode,
        stress_score=stress_score,
        ai_analysis=f"Grounding mode chat. Detected emotion: {emotion}",
        resolved=False
    )
    agent_entry = IncidentLog(
        user_id=user.id,
        incident_type="agent_reply",
        notes=reply,
        input_mode="text",
        stress_score=stress_score,
        ai_analysis="Calming agent response",
        resolved=False
    )
    db.add(user_entry)
    db.add(agent_entry)
    db.commit()

    return {"reply": reply, "emotion": emotion, "stress_score": stress_score}


@router.post("/incident/voice-companion")
async def incident_voice_companion(
    file: UploadFile = File(...),
    client_emotion: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("patient"))
):
    from datetime import datetime, timedelta
    
    file_bytes = await file.read()
    transcript = transcribe_audio(file_bytes, file.filename)
    
    # Fetch recent incident dialog history for context
    recent_logs = db.query(IncidentLog).filter(
        IncidentLog.user_id == user.id,
        IncidentLog.incident_type.in_(["user_utterance", "agent_reply"])
    ).order_by(IncidentLog.timestamp.desc()).limit(6).all()
    
    recent = [
        {"role": "user" if r.incident_type == "user_utterance" else "agent", "message": r.notes or ""}
        for r in recent_logs
    ][::-1]

    # Get stabilizing response and classification details
    analysis = live_companion_analysis(transcript, recent)
    reply = analysis["reply"]
    stress_score = float(analysis["stress_score"])
    emotion = analysis["emotion"]
    ai_analysis = analysis["ai_analysis"]
    is_incident = analysis["is_incident"]

    # Log parent incident alert if the AI identifies this as an active panic event
    if is_incident or stress_score > 60:
        time_threshold = datetime.utcnow() - timedelta(minutes=30)
        recent_panic = db.query(IncidentLog).filter(
            IncidentLog.user_id == user.id,
            IncidentLog.incident_type.notin_(["user_utterance", "agent_reply"]),
            IncidentLog.timestamp >= time_threshold
        ).first()
        
        if not recent_panic:
            panic_alert = IncidentLog(
                user_id=user.id,
                incident_type="voice_panic_incident",
                notes=f"Voice Panic Trigger: {transcript}",
                input_mode="voice",
                stress_score=stress_score,
                ai_analysis=f"AI Analysis: {ai_analysis} | Detected emotion: {emotion}",
                resolved=False
            )
            db.add(panic_alert)

    # Log this conversation turn as incident records
    user_entry = IncidentLog(
        user_id=user.id,
        incident_type="user_utterance",
        notes=f"[Voice Message] {transcript}",
        input_mode="voice",
        stress_score=stress_score,
        ai_analysis=f"Grounding voice chat. Detected emotion: {emotion}",
        resolved=False
    )
    agent_entry = IncidentLog(
        user_id=user.id,
        incident_type="agent_reply",
        notes=reply,
        input_mode="text",
        stress_score=stress_score,
        ai_analysis="Calming agent response",
        resolved=False
    )
    db.add(user_entry)
    db.add(agent_entry)
    db.commit()

    return {"reply": reply, "transcript": transcript, "emotion": emotion, "stress_score": stress_score}
