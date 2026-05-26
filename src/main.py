from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import router as v1_router
from src.db.base import engine
from src.middleware.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
