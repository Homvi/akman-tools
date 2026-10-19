from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import settings
from apps.api.db import Base, SessionLocal, engine
from apps.api.routers import (
    areas,
    auth,
    cables,
    calculator,
    dataset,
    errors,
    export,
    ids,
    progress,
    routes,
    stichmass,
    stopped,
    stutzen,
    workforce,
)
from apps.api.services.bootstrap import ensure_roles_and_admin


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_roles_and_admin(db)
    finally:
        db.close()
    settings.appdata_path  # ensure dirs
    yield


app = FastAPI(title="Cable installation API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dataset.router)
app.include_router(cables.router)
app.include_router(export.router)
app.include_router(errors.router)
app.include_router(stopped.router)
app.include_router(stutzen.router)
app.include_router(ids.router)
app.include_router(calculator.router)
app.include_router(stichmass.router)
app.include_router(progress.router)
app.include_router(workforce.router)
app.include_router(areas.router)
app.include_router(routes.router)


@app.get("/health")
def health():
    return {"ok": True}
