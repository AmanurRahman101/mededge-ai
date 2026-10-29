from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.auth.security import require_user
from app.pipeline.cases import case_image, list_cases, load_case, private_inbox
from app.pipeline.fallback_assembler import assemble
from app.pipeline.schemas import EncounterFields, Extraction

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
async def inbox(request: Request) -> dict:
    if (
        not request.app.state.settings.enable_dev_routes
        or request.app.state.settings.app_env == "production"
    ):
        raise HTTPException(status_code=404, detail="Not found")
    require_user(request)
    return {"files": private_inbox()}


@router.get("/api/demo/{case_id}")
async def demo_case(case_id: str) -> dict:
    """Read a fictional, recorded sample without creating a run or calling a model."""
    case = load_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Unknown sample case")
    extraction = Extraction.model_validate(case["extraction"])
    encounter = EncounterFields.model_validate(case.get("encounter") or {})
    return {
        "id": case["id"],
        "title": case["title"],
        "kind": case["kind"],
        "summary": case["summary"],
        "image_url": f"/api/demo/{case['id']}/image",
        "extraction": extraction.model_dump(),
        "encounter": encounter.model_dump(),
        "bundle": assemble(extraction, encounter, "PT-SAMPLE", {}),
        "replay": True,
    }


@router.get("/api/demo/{case_id}/image")
async def demo_image(case_id: str) -> Response:
    image = case_image(case_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Unknown sample case")
    content, mime = image
    return Response(content=content, media_type=mime)
