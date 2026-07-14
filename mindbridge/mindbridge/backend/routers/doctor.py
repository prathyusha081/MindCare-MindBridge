from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    User, MentalHealthTracker, DailyTracker, IncidentLog, 
    DoctorReview, AuditLog, Medication, DiagnosisReport, AIReport
)
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


def _calculate_risk(db: Session, patient_id: int) -> dict:
    since = datetime.utcnow() - timedelta(days=7)
    
    # 1. Stress Score (from Mental Health Questionnaire)
    mh_entries = db.query(MentalHealthTracker).filter(MentalHealthTracker.user_id == patient_id).order_by(MentalHealthTracker.date.desc()).limit(5).all()
    avg_stress = sum(e.stress_score for e in mh_entries) / len(mh_entries) if mh_entries else 50.0
    
    # 2. Panic Events Count
    incidents_count = db.query(IncidentLog).filter(
        IncidentLog.user_id == patient_id,
        IncidentLog.timestamp >= since,
        IncidentLog.incident_type.notin_(["user_utterance", "agent_reply"])
    ).count()
    panic_score = min(100.0, incidents_count * 20.0)
    
    # 3. Sleep Deprivation
    daily_entries = db.query(DailyTracker).filter(DailyTracker.user_id == patient_id).order_by(DailyTracker.date.desc()).limit(7).all()
    avg_sleep = sum(d.sleep_hours for d in daily_entries) / len(daily_entries) if daily_entries else 7.5
    sleep_dep_score = max(0.0, (8.0 - avg_sleep) * 25.0)
    
    # 4. Sentiment (scaled from mood score 1-10)
    avg_mood = sum(d.mood_score for d in daily_entries) / len(daily_entries) if daily_entries else 6.0
    sentiment_score = max(0.0, (10.0 - avg_mood) * 10.0)
    
    # Risk Formula: 0.4*stress + 0.3*panic + 0.2*sleep + 0.1*sentiment
    score = int(0.4 * avg_stress + 0.3 * panic_score + 0.2 * sleep_dep_score + 0.1 * sentiment_score)
    score = max(0, min(100, score))
    
    if score >= 71:
        level = "High"
    elif score >= 41:
        level = "Medium"
    else:
        level = "Low"
        
    return {"score": score, "level": level}


@router.get("/patients")
def list_patients(db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    patients = db.query(User).filter(User.role == "patient", User.doctor_id == doctor.id).all()
    res = []
    for p in patients:
        risk = _calculate_risk(db, p.id)
        res.append({
            "id": p.id,
            "name": p.name,
            "email": p.email,
            "risk_score": risk["score"],
            "risk_level": risk["level"]
        })
    return res


@router.get("/patients/{patient_id}/trends")
def patient_trends(patient_id: int, db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    _assert_owns_patient(db, doctor, patient_id)
    _log_access(db, doctor, "view_patient_trends", patient_id)

    mh = db.query(MentalHealthTracker).filter(MentalHealthTracker.user_id == patient_id).order_by(MentalHealthTracker.date).all()
    daily = db.query(DailyTracker).filter(DailyTracker.user_id == patient_id).order_by(DailyTracker.date).all()
    return {
        "mental_health": [{"date": r.date, "stress_score": r.stress_score, "anxiety_score": r.anxiety_score,
                            "depression_score": r.depression_score, "focus_score": r.focus_score, "energy_level": r.energy_level} for r in mh],
        "daily": [{"date": r.date, "sleep_hours": r.sleep_hours, "mood_score": r.mood_score, "food_quality": r.food_quality} for r in daily],
    }


@router.get("/patients/{patient_id}/incidents")
def patient_incidents(patient_id: int, db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    _assert_owns_patient(db, doctor, patient_id)
    _log_access(db, doctor, "view_patient_incidents", patient_id)

    rows = db.query(IncidentLog).filter(IncidentLog.user_id == patient_id).order_by(IncidentLog.timestamp.desc()).all()
    return [{"id": r.id, "type": r.incident_type, "notes": r.notes, "stress_score": r.stress_score,
             "analysis": r.ai_analysis, "resolved": r.resolved, "timestamp": r.timestamp} for r in rows]


@router.get("/patients/{patient_id}/profile")
def patient_profile(patient_id: int, db: Session = Depends(get_db), doctor: User = Depends(require_role("doctor"))):
    _assert_owns_patient(db, doctor, patient_id)
    _log_access(db, doctor, "view_patient_profile", patient_id)
    
    # Fetch all logs
    mh = db.query(MentalHealthTracker).filter(MentalHealthTracker.user_id == patient_id).order_by(MentalHealthTracker.date.desc()).all()
    daily = db.query(DailyTracker).filter(DailyTracker.user_id == patient_id).order_by(DailyTracker.date.desc()).all()
    incidents = db.query(IncidentLog).filter(IncidentLog.user_id == patient_id).order_by(IncidentLog.timestamp.desc()).all()
    meds = db.query(Medication).filter(Medication.user_id == patient_id).order_by(Medication.start_date.desc()).all()
    reports = db.query(DiagnosisReport).filter(DiagnosisReport.user_id == patient_id).order_by(DiagnosisReport.date.desc()).all()
    ai_reports = db.query(AIReport).filter(AIReport.user_id == patient_id).order_by(AIReport.generated_at.desc()).all()
    reviews = db.query(DoctorReview).filter(DoctorReview.user_id == patient_id).order_by(DoctorReview.created_at.desc()).all()
    
    risk = _calculate_risk(db, patient_id)
    
    return {
        "risk": risk,
        "mental_health": [
            {"date": r.date, "stress_score": r.stress_score, "anxiety_score": r.anxiety_score,
             "depression_score": r.depression_score, "focus_score": r.focus_score, "energy_level": r.energy_level, "notes": r.notes}
            for r in mh
        ],
        "daily": [
            {"date": r.date, "sleep_hours": r.sleep_hours, "water_intake": r.water_intake,
             "exercise_minutes": r.exercise_minutes, "mood_score": r.mood_score, "food_quality": r.food_quality}
            for r in daily
        ],
        "incidents": [
            {"id": r.id, "type": r.incident_type, "notes": r.notes, "stress_score": r.stress_score,
             "analysis": r.ai_analysis, "resolved": r.resolved, "timestamp": r.timestamp}
            for r in incidents
        ],
        "medications": [
            {"id": r.id, "medicine_name": r.medicine_name, "dosage": r.dosage, "frequency": r.frequency, "start_date": r.start_date}
            for r in meds
        ],
        "diagnosis_reports": [
            {"id": r.id, "report_title": r.report_title, "diagnosis": r.diagnosis, "doctor": r.doctor, "date": r.date, "file_path": r.file_path}
            for r in reports
        ],
        "ai_reports": [
            {"id": r.id, "summary": r.ai_summary, "stress_index": r.stress_index, "sleep_avg": r.sleep_avg, "generated_at": r.generated_at}
            for r in ai_reports
        ],
        "reviews": [
            {"id": r.id, "summary": r.doctor_summary, "suggestions": r.suggestions, "created_at": r.created_at}
            for r in reviews
        ]
    }


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


@router.get("/reviews/mine")
def get_my_reviews(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rows = db.query(DoctorReview).filter(DoctorReview.user_id == user.id).order_by(DoctorReview.created_at.desc()).all()
    return [
        {"id": r.id, "summary": r.doctor_summary, "suggestions": r.suggestions, "created_at": r.created_at}
        for r in rows
    ]
