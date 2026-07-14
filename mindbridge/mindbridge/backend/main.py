from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
import models  # noqa: F401  (ensures models are registered before create_all)
from routers import auth_routes, chat, trackers, doctor, reports

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MindBridge API",
    description="Agentic AI mental wellness companion — chat, mood tracking, and doctor dashboard.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your deployed frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(chat.router)
app.include_router(trackers.router)
app.include_router(doctor.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "MindBridge API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
