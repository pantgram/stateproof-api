from fastapi import APIRouter

from src.api.v1.auth import router as auth_router
from src.api.v1.verify import router as verify_router
from src.api.v1.workflows import router as workflows_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(workflows_router)
router.include_router(verify_router)


@router.get("/health")
async def health_check():
    return {"status": "ok"}
