import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from models import User, Medication, DiagnosisReport
from schemas import MedicationRequest
from auth import require_role

router = APIRouter(prefix="/medical-history", tags=["medical-history"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
def add_report(
    report_title: str = Form(...),
    diagnosis: str = Form(...),
    doctor: str = Form(...),
    date: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("patient"))
):
    file_path = None
    if file:
        filename = f"{user.id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_path = f"/static/uploads/{filename}"

    rep = DiagnosisReport(
        user_id=user.id,
        report_title=report_title,
        diagnosis=diagnosis,
        doctor=doctor,
        date=datetime.fromisoformat(date.replace("Z", "")),
        file_path=file_path
    )
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
