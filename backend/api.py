from contextlib import asynccontextmanager
import configparser
import html
import os
import re
import secrets
import threading
from pathlib import Path
from typing import AsyncIterator, Optional
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from backend.server import BackendStatus, MainBackend, QRSessionStatus
from backend.cardreader import CardReader, nameCandidates

cfg = configparser.ConfigParser()
cfg.read(Path(__file__).resolve().parent.parent / 'conf.ini', encoding='utf-8')
QR_PAGE = (Path(__file__).resolve().parent / 'qrpage.html').read_text(encoding='utf-8')
QR_TOKEN = re.compile(r'^[A-Za-z0-9_-]{16,64}$')
MAX_CARD_SIZE = 10 * 1024 * 1024 # 10MB
ocrLock = threading.Lock() # easyocr is not thread safe

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
    try:
        app.state.cardReader = CardReader()
    except ImportError:
        app.state.cardReader = None
        print('ocr: easyocr is not installed, qrcode authentication is disabled!!')
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

# qrcode authentication (opened from the phone, the qrcode token is the secret)
def getActiveQRSession(token: str, request: Request):
    if not QR_TOKEN.match(token):
        raise HTTPException(status_code=404, detail="잘못된 QR코드입니다.")
    session = request.app.state.backend.getQRSession(token)
    if session is None:
        raise HTTPException(status_code=404, detail="잘못된 QR코드입니다.")
    match session['status']:
        case QRSessionStatus.QR_WAIT | QRSessionStatus.QR_CARD_READ:
            return session
        case QRSessionStatus.QR_REJECTED:
            raise HTTPException(status_code=403, detail="시도 횟수를 초과했습니다. 기기에서 QR코드를 다시 만들어주세요.")
        case QRSessionStatus.QR_APPROVED | QRSessionStatus.QR_USED:
            raise HTTPException(status_code=410, detail="이미 승인된 QR코드입니다.")
        case _:
            raise HTTPException(status_code=410, detail="만료된 QR코드입니다. 기기에서 QR코드를 다시 만들어주세요.")

def renderQRPage(state: str, message: str):
    page = QR_PAGE.replace('%%COLOR%%', html.escape(cfg.get('School', 'MainColor', fallback='#2E3673').strip('"')))
    page = page.replace('%%SCHOOL%%', html.escape(cfg.get('School', 'SchoolName', fallback='')))
    page = page.replace('%%STATE%%', state)
    return page.replace('%%MESSAGE%%', html.escape(message))

@api.get("/qr/{token}", response_class=HTMLResponse)
def qrPage(token: str, request: Request): # phone page
    try:
        getActiveQRSession(token, request)
    except HTTPException as e:
        return HTMLResponse(renderQRPage('closed', e.detail), status_code=e.status_code)
    return renderQRPage('ready', '이름이 보이도록 학생증 앞면을 찍어주세요.')

@api.post("/qr/{token}/card")
def qrReadCard(token: str, request: Request, card: UploadFile = File(...)): # student card photo -> enrolled name
    getActiveQRSession(token, request)
    reader = request.app.state.cardReader
    if reader is None:
        raise HTTPException(status_code=503, detail="학생증 인식 기능이 준비되지 않았습니다.")
    image = card.file.read(MAX_CARD_SIZE + 1)
    if len(image) > MAX_CARD_SIZE:
        raise HTTPException(status_code=413, detail="사진 용량이 너무 큽니다.")

    try:
        with ocrLock:
            texts = reader.readText(image)
    except Exception as e:
        print(f'ocr: failed to read card ({e})')
        raise HTTPException(status_code=422, detail="사진을 읽지 못했습니다. 다시 찍어주세요.")

    backend = request.app.state.backend
    matches = {} # name: [enrolled ids]
    for name in nameCandidates(texts):
        ids = backend.findUserIdsByName(name)
        if ids:
            matches[name] = ids
    print(f'ocr: card read, enrolled match count: {len(matches)}')

    if len(matches) == 1:
        name, ids = next(iter(matches.items()))
        if len(ids) == 1 and backend.setQRCardResult(token, ids[0]):
            return {"name": name}

    # not enrolled, unreadable or same name enrolled twice
    backend.setQRCardResult(token, None)
    getActiveQRSession(token, request) # raises when attempts are used up
    raise HTTPException(status_code=404, detail="등록된 학생증을 찾지 못했습니다. 이름이 잘 보이게 다시 찍어주세요.")

@api.post("/qr/{token}/approve")
def qrApprove(token: str, request: Request):
    getActiveQRSession(token, request)
    if not request.app.state.backend.approveQRSession(token):
        raise HTTPException(status_code=409, detail="먼저 학생증 사진을 찍어주세요.")
    return {"approved": True}
