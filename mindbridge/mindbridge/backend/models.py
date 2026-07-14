from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="patient")  # "patient" | "doctor"
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # assigned doctor, if role=patient
    created_at = Column(DateTime, default=datetime.utcnow)

    doctor = relationship("User", remote_side=[id])


class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" | "agent"
    input_mode = Column(String, default="text")  # "text" | "voice" | "video"
    message = Column(Text, nullable=False)
    sentiment_score = Column(Float, nullable=True)   # -1 (negative) to 1 (positive)
    stress_score = Column(Float, nullable=True)       # 0-100
    emotion_detected = Column(String, nullable=True)  # from client-side video/voice signal
    timestamp = Column(DateTime, default=datetime.utcnow)


class DailyTracker(Base):
    __tablename__ = "daily_tracker"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    sleep_hours = Column(Float, default=0)
    water_intake = Column(Float, default=0)
    exercise_minutes = Column(Integer, default=0)
    mood_score = Column(Integer, default=5)  # 1-10


class MentalHealthTracker(Base):
    __tablename__ = "mental_health_tracker"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    stress_score = Column(Float, default=0)
    anxiety_score = Column(Float, default=0)
    depression_score = Column(Float, default=0)
    notes = Column(Text, nullable=True)


class AIReport(Base):
    __tablename__ = "ai_reports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, default=datetime.utcnow)
    stress_index = Column(Float, default=0)
    panic_count = Column(Integer, default=0)
    sleep_avg = Column(Float, default=0)
    ai_summary = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)


class IncidentLog(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    incident_type = Column(String, default="high_stress")  # "high_stress" | "crisis_language"
    input_mode = Column(String, default="text")
    stress_score = Column(Float, nullable=True)
    ai_analysis = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class DoctorReview(Base):
    __tablename__ = "doctor_reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    doctor_summary = Column(Text, nullable=True)
    suggestions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Every access to patient data is recorded — same principle as PBAC audit trails."""
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String, nullable=False)
    action = Column(String, nullable=False)       # e.g. "view_patient_report"
    target_user_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
