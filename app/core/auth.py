from __future__ import annotations
import os, base64
from fastapi import Header, HTTPException, status
from typing import Optional

CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")

def _unauthorized():
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Basic"}
    )

def verify_basic_auth(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("basic "):
        _unauthorized()
    try:
        b64 = authorization.split(" ", 1)[1]
        raw = base64.b64decode(b64).decode("utf-8")
        incoming_id, incoming_secret = raw.split(":", 1)
    except Exception:
        _unauthorized()

    if not CLIENT_ID or not CLIENT_SECRET:
        _unauthorized()

    if incoming_id != CLIENT_ID or incoming_secret != CLIENT_SECRET:
        _unauthorized()

    return {"client_id": incoming_id}
