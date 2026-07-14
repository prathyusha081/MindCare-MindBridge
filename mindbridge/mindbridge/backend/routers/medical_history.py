from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User, Medication, DiagnosisReport
from schemas import MedicationRequest, DiagnosisReportRequest
from auth import require_role

router = APIRouter(prefix="/medical-history", tags=["medical-history"])


@router.post("/medication")
def add_medication(payload: MedicationRequest, db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    med = Medication(user_id=user.id, **payload.model_dump())
    db.add(med)
    db.commit()
    return {"status": "saved"}


@router.get("/medication")
def get_medications(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rows = db.query(Medication).filter(Medication.user_id == user.id).order_by(Medication.start_date.desc()).all()
    return [
        {"id": r.id, "medicine_name": r.medicine_name, "dosage": r.dosage, "frequency": r.frequency, "start_date": r.start_date}
        for r in rows
    ]


@router.post("/report")
def add_report(payload: DiagnosisReportRequest, db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rep = DiagnosisReport(user_id=user.id, **payload.model_dump())
    db.add(rep)
    db.commit()
    return {"status": "saved"}


@router.get("/report")
def get_reports(db: Session = Depends(get_db), user: User = Depends(require_role("patient"))):
    rows = db.query(DiagnosisReport).filter(DiagnosisReport.user_id == user.id).order_by(DiagnosisReport.date.desc()).all()
    return [
        {"id": r.id, "report_title": r.report_title, "diagnosis": r.diagnosis, "doctor": r.doctor, "date": r.date, "file_path": r.file_path}
        for r in rows
    ]
