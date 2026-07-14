from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, MentalHealthTracker, DailyTracker, IncidentLog, DoctorReview, AuditLog
from schemas import DoctorReviewRequest
from auth import require_role

router = APIRouter(prefix="/doctor", tags=["doctor"])


def _assert_owns_patient(db: Session, doctor: User, patient_id: int) -> User:
    """The core access-control check: a doctor may only read data for patients
    explicitly assigned to them — mirrors a PBAC 'relationship-based' policy."""
    patient = db.query(User).filter(User.id == patient_id, User.role == "patient").first()
    if not patient or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this patient")
    return patient


def _log_access(db: Session, doctor: User, action: str, target_id: int):
    db.add(AuditLog(actor_id=doctor.id, actor_role="doctor", action=action, target_user_id=target_id))
    db.commit()


@router.get("/patients")
def list_patients(db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    patients = db.query(User).filter(User.role == "patient", User.doctor_id == doctor.id).all()
    return [{"id": p.id, "name": p.name, "email": p.email} for p in patients]


@router.get("/patients/{patient_id}/trends")
def patient_trends(patient_id: int, db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    _assert_owns_patient(db, doctor, patient_id)
    _log_access(db, doctor, "view_patient_trends", patient_id)

    mh = db.query(MentalHealthTracker).filter(MentalHealthTracker.user_id == patient_id).order_by(MentalHealthTracker.date).all()
    daily = db.query(DailyTracker).filter(DailyTracker.user_id == patient_id).order_by(DailyTracker.date).all()
    return {
        "mental_health": [{"date": r.date, "stress_score": r.stress_score, "anxiety_score": r.anxiety_score,
                            "depression_score": r.depression_score} for r in mh],
        "daily": [{"date": r.date, "sleep_hours": r.sleep_hours, "mood_score": r.mood_score} for r in daily],
    }


@router.get("/patients/{patient_id}/incidents")
def patient_incidents(patient_id: int, db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    _assert_owns_patient(db, doctor, patient_id)
    _log_access(db, doctor, "view_patient_incidents", patient_id)

    rows = db.query(IncidentLog).filter(IncidentLog.user_id == patient_id).order_by(IncidentLog.timestamp.desc()).all()
    return [{"id": r.id, "type": r.incident_type, "stress_score": r.stress_score,
             "analysis": r.ai_analysis, "resolved": r.resolved, "timestamp": r.timestamp} for r in rows]


@router.post("/review")
def add_review(payload: DoctorReviewRequest, db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    _assert_owns_patient(db, doctor, payload.user_id)
    _log_access(db, doctor, "add_review", payload.user_id)

    review = DoctorReview(
        user_id=payload.user_id, doctor_id=doctor.id,
        doctor_summary=payload.doctor_summary, suggestions=payload.suggestions,
    )
    db.add(review)
    db.commit()
    return {"status": "saved"}
