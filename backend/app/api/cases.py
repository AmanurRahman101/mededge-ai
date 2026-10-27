from fastapi import APIRouter

from app.pipeline.cases import list_cases, private_inbox

router = APIRouter()


@router.get("/api/cases")
async def cases() -> dict:
    return {
        "cases": [
            {
                "id": case["id"],
                "title": case["title"],
                "kind": case["kind"],
                "summary": case["summary"],
            }
            for case in list_cases()
        ]
    }


@router.get("/api/inbox")
async def inbox() -> dict:
    return {"files": private_inbox()}
