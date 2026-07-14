from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "patient"  # "patient" | "doctor"
    doctor_id: Optional[int] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    name: str


class ChatMessageRequest(BaseModel):
    message: str
    input_mode: str = "text"          # "text" | "voice" | "video"
    client_emotion: Optional[str] = None   # e.g. from face-api.js on the frontend


class ChatMessageResponse(BaseModel):
    reply: str
    stress_score: float
    risk_level: str          # "low" | "moderate" | "high"
    escalated: bool


class DailyTrackerRequest(BaseModel):
    sleep_hours: float
    water_intake: float
    exercise_minutes: int
    mood_score: int
    food_quality: Optional[str] = None


class MentalHealthEntryRequest(BaseModel):
    stress_score: float
    anxiety_score: float
    depression_score: float
    focus_score: float
    energy_level: float
    notes: Optional[str] = None


class IncidentLogRequest(BaseModel):
    incident_type: str
    notes: Optional[str] = None
    input_mode: str = "text"


class MedicationRequest(BaseModel):
    medicine_name: str
    dosage: str
    frequency: str
    start_date: datetime


class DiagnosisReportRequest(BaseModel):
    report_title: str
    diagnosis: str
    doctor: str
    date: datetime
    file_path: Optional[str] = None


class DoctorReviewRequest(BaseModel):
    user_id: int
    doctor_summary: str
    suggestions: str
