"""Simple DB helper for activities with MongoDB (optional) and JSON fallback.

Environment variables:
- MONGO_URL: if set, connect to this MongoDB instance
- MONGO_DB: database name to use (default: mergington)

This module exposes:
- using_db: bool
- get_activities()
- signup(activity_name, email)
- unregister(activity_name, email)
- ensure_seed(json_path)

Errors: ActivityNotFoundError, AlreadySignedUpError, NotSignedUpError, ActivityFullError
"""

import os
import json
from pathlib import Path
from typing import Dict

MONGO_URL = os.getenv("MONGO_URL")
MONGO_DB = os.getenv("MONGO_DB", "mergington")

using_db = False
_client = None
_db = None


class ActivityNotFoundError(Exception):
    pass


class AlreadySignedUpError(Exception):
    pass


class NotSignedUpError(Exception):
    pass


class ActivityFullError(Exception):
    pass


def _connect():
    global using_db, _client, _db
    if not MONGO_URL:
        using_db = False
        return
    try:
        from pymongo import MongoClient
        _client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
        # Trigger a server selection to surface errors early
        _client.server_info()
        _db = _client[MONGO_DB]
        using_db = True
    except Exception:
        # If connection fails, fall back to JSON in-memory
        using_db = False


_connect()


# JSON fallback storage
_in_memory: Dict[str, Dict] = {}


def _load_json(json_path: Path):
    global _in_memory
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            # Ensure participants list exists
            for k, v in data.items():
                v.setdefault("participants", [])
            _in_memory = data
    except Exception:
        _in_memory = {}


def ensure_seed(json_path: Path):
    """If using MongoDB and activities collection is empty, seed from json_path."""
    if not using_db:
        # ensure fallback has data loaded
        _load_json(json_path)
        return

    coll = _db.get_collection("activities")
    if coll.count_documents({}) == 0:
        # seed
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                docs = []
                for name, body in data.items():
                    doc = body.copy()
                    doc["name"] = name
                    docs.append(doc)
                if docs:
                    coll.insert_many(docs)
        except Exception:
            pass


def get_activities():
    if using_db:
        coll = _db.get_collection("activities")
        out = {}
        for doc in coll.find():
            name = doc.get("name") or doc.get("_id")
            # copy fields except _id
            activity = {k: v for k, v in doc.items() if k != "_id"}
            if "name" in activity:
                activity.pop("name", None)
            out[name] = activity
        return out

    return _in_memory


def _get_activity_doc(coll, activity_name):
    return coll.find_one({"name": activity_name})


def signup(activity_name: str, email: str):
    if using_db:
        coll = _db.get_collection("activities")
        doc = _get_activity_doc(coll, activity_name)
        if not doc:
            raise ActivityNotFoundError()
        participants = doc.get("participants", [])
        maxp = doc.get("max_participants")
        if email in participants:
            raise AlreadySignedUpError()
        if maxp is not None and len(participants) >= maxp:
            raise ActivityFullError()
        coll.update_one({"name": activity_name}, {"$push": {"participants": email}})
        return

    # fallback
    if activity_name not in _in_memory:
        raise ActivityNotFoundError()
    activity = _in_memory[activity_name]
    if email in activity.get("participants", []):
        raise AlreadySignedUpError()
    if activity.get("max_participants") is not None and len(activity.get("participants", [])) >= activity.get("max_participants"):
        raise ActivityFullError()
    activity.setdefault("participants", []).append(email)


def unregister(activity_name: str, email: str):
    if using_db:
        coll = _db.get_collection("activities")
        doc = _get_activity_doc(coll, activity_name)
        if not doc:
            raise ActivityNotFoundError()
        participants = doc.get("participants", [])
        if email not in participants:
            raise NotSignedUpError()
        coll.update_one({"name": activity_name}, {"$pull": {"participants": email}})
        return

    # fallback
    if activity_name not in _in_memory:
        raise ActivityNotFoundError()
    activity = _in_memory[activity_name]
    if email not in activity.get("participants", []):
        raise NotSignedUpError()
    activity["participants"].remove(email)
