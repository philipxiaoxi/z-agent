import subprocess
import json

from fastapi import APIRouter


router = APIRouter()


def _run_zcli(args: list[str]) -> dict:
    result = subprocess.run(
        ["zcli", *args],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return json.loads(result.stdout)


@router.get("/")
def list_pools():
    raw = _run_zcli(["pool"])
    names = _run_zcli(["poolname"])
    pools = raw.get("data", {}).get("pool_list", [])
    for p in pools:
        p["display_name"] = names.get(p["name"], p["name"])
    return {"pools": pools}


@router.get("/{pool_id}")
def get_pool_info(pool_id: str):
    pools = list_pools()
    for p in pools["pools"]:
        if p["name"] == pool_id:
            return p
    return {"error": "pool not found"}
