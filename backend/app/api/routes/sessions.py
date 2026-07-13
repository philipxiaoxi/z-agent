from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel
from app.blocks import build_blocks
from app.core import session_store

router = APIRouter()


class CreateSessionReq(BaseModel):
    name: str = ""


class RenameSessionReq(BaseModel):
    name: str


@router.get("/")
def list_all_sessions():
    return {"sessions": session_store.list_sessions()}


@router.post("/")
def create_new_session(req: CreateSessionReq):
    return session_store.create_session(req.name)


@router.delete("/{session_id}")
def delete_existing_session(session_id: str):
    ok = session_store.delete_session(session_id)
    return {"ok": ok}


@router.get("/{session_id}")
def get_session_detail(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        return {"error": "not found"}, 404
    for msg in session.get("messages", []):
        if msg.get("blocks"):
            continue
        if msg.get("role") == "user":
            msg["blocks"] = [{"id": str(uuid4()), "type": "text", "content": msg.get("content", ""), "collapsed": False}]
        elif msg.get("role") == "assistant" and msg.get("segments"):
            msg["blocks"] = build_blocks(msg["segments"])
        msg.pop("segments", None)
    return session


@router.put("/{session_id}/name")
def rename_existing_session(session_id: str, req: RenameSessionReq):
    ok = session_store.rename_session(session_id, req.name)
    return {"ok": ok}
