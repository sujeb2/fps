from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI, HTTPException, Request
from backend.server import BackendStatus, MainBackend

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    backend = MainBackend()
    if backend.getStatus() != BackendStatus.DATABASE_READY:
        raise RuntimeError("Could not initialize the database.")

    app.state.backend = backend
    yield
api = FastAPI(title="FPSAPI", version="0.0.1", lifespan=lifespan)

@api.get("/test") # connection test
def pingpong():
    return {"ping": "pong!"}

@api.get("/id/{user_id}")
def getUserInformation(user_id: int, request: Request):
    information = request.app.state.backend.fetchInformation(user_id)
    if information is None:
        raise HTTPException(status_code=404, detail="Fingerprint record not found.")
    return information