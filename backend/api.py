from contextlib import asynccontextmanager
import os
import secrets
from typing import AsyncIterator, Optional
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from backend.server import BackendStatus, MainBackend

bearer_scheme = HTTPBearer(auto_error=False)


def require_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    configured_token = os.environ.get("FPS_API_TOKEN")
    if not configured_token:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured.",
        )
    if credentials is None or not secrets.compare_digest(
        credentials.credentials, configured_token
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


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

@api.get("/id/{user_id}", dependencies=[Depends(require_api_token)])
def getUserInformation(user_id: int, request: Request): # registered user info
    information = request.app.state.backend.fetchInformation(user_id)
    if information is None:
        raise HTTPException(status_code=404, detail="Fingerprint record not found.")
    return information

@api.get("/checkline/userExists/{user_id}", dependencies=[Depends(require_api_token)])
def checkUserExist(user_id: int, request: Request):
    info = request.app.state.backend.isExist(user_id)
    if info is False:
        raise HTTPException(status_code=404, detail="Imported user id has not found or not enrolled correctly.")
    return info
