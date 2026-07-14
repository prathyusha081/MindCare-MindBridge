from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, DailyTracker, MentalHealthTracker
from schemas import DailyTrackerRequest, MentalHealthEntryRequest
from auth import require_role

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
         "exercise_minutes": r.exercise_minutes, "mood_score": r.mood_score}
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
         "depression_score": r.depression_score, "notes": r.notes}
        for r in rows
    ]
