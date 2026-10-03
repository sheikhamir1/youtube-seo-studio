"""System status, model registry, quota and maintenance endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import success
from app.db.dependencies import get_db
from app.services.cleanup import CleanupService
from app.services.system_service import SystemService

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)) -> dict:
    return success(await SystemService(db).status())


@router.get("/models")
async def models(db: AsyncSession = Depends(get_db)) -> dict:
    return success(await SystemService(db).models())


@router.get("/quota")
async def quota(db: AsyncSession = Depends(get_db)) -> dict:
    return success(await SystemService(db).quota())


@router.get("/storage")
async def storage(db: AsyncSession = Depends(get_db)) -> dict:
    return success(await SystemService(db).storage_usage())


@router.post("/cleanup")
async def cleanup(db: AsyncSession = Depends(get_db)) -> dict:
    service = CleanupService()
    result = await service.cleanup_stale_uploads()
    result["orphan_directories"] = await service.find_orphan_directories()
    return success(result, message="Temporary files cleaned.")
