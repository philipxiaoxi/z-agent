from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_pools():
    return {"pools": []}


@router.get("/{pool_id}")
def get_pool_info(pool_id: str):
    return {"pool_id": pool_id, "info": {}}
