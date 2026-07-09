from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_files():
    return {"files": []}


@router.get("/search")
def search_files(q: str = ""):
    return {"results": []}
