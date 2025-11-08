"""
High School Management System API

This version uses a small DB helper to persist activities to MongoDB when
configured. If `MONGO_URL` is not set, it falls back to a JSON-backed
in-memory store located at `src/activities.json`.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
import os

from . import db

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")


@app.on_event("startup")
def startup_event():
    # If DB is configured and empty, seed from JSON
    if db.using_db:
        db.ensure_seed(current_dir / "activities.json")


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return db.get_activities()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    try:
        db.signup(activity_name, email)
    except db.ActivityNotFoundError:
        raise HTTPException(status_code=404, detail="Activity not found")
    except db.AlreadySignedUpError:
        raise HTTPException(status_code=400, detail="Student is already signed up")
    except db.ActivityFullError:
        raise HTTPException(status_code=400, detail="Activity is full")

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    try:
        db.unregister(activity_name, email)
    except db.ActivityNotFoundError:
        raise HTTPException(status_code=404, detail="Activity not found")
    except db.NotSignedUpError:
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    return {"message": f"Unregistered {email} from {activity_name}"}

