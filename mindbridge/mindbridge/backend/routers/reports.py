from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, MentalHealthTracker, DailyTracker, ChatLog, AIReport
from auth import require_role
from agents import report_agent

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate")
def generate_report(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    since = datetime.utcnow() - timedelta(days=7)

    mh_rows = db.query(MentalHealthTracker).filter(
        MentalHealthTracker.user_id == user.id, MentalHealthTracker.date >= since
    ).all()
    daily_rows = db.query(DailyTracker).filter(
        DailyTracker.user_id == user.id, DailyTracker.date >= since
    ).all()
    chat_rows = db.query(ChatLog).filter(
        ChatLog.user_id == user.id, ChatLog.timestamp >= since, ChatLog.role == "agent"
    ).all()

    tracker_payload = [{"stress": r.stress_score, "anxiety": r.anxiety_score, "depression": r.depression_score} for r in mh_rows]
    tracker_payload += [{"sleep": r.sleep_hours, "mood": r.mood_score} for r in daily_rows]
    chat_payload = [{"stress_score": r.stress_score} for r in chat_rows if r.stress_score is not None]

    summary = report_agent(tracker_payload, chat_payload)

    avg_stress = sum(c["stress_score"] for c in chat_payload) / len(chat_payload) if chat_payload else 0
    avg_sleep = sum(r.sleep_hours for r in daily_rows) / len(daily_rows) if daily_rows else 0

    report = AIReport(
        user_id=user.id, start_date=since, end_date=datetime.utcnow(),
        stress_index=avg_stress, panic_count=sum(1 for c in chat_payload if c["stress_score"] and c["stress_score"] > 80),
        sleep_avg=avg_sleep, ai_summary=summary,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "summary": summary, "stress_index": avg_stress, "sleep_avg": avg_sleep}


@router.get("/mine")
def my_reports(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rows = db.query(AIReport).filter(AIReport.user_id == user.id).order_by(AIReport.generated_at.desc()).all()
    return [{"id": r.id, "summary": r.ai_summary, "stress_index": r.stress_index,
             "sleep_avg": r.sleep_avg, "generated_at": r.generated_at} for r in rows]
