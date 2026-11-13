import sqlite3, secrets, time
from backend.encryption import Encryption
from enum import Enum
from pathlib import Path

QR_MAX_ATTEMPT = 3 # student card upload attempts per qrcode

class BackendStatus(Enum):
    DATABASE_GENERIC_ERROR = -1
    DATABASE_WAIT = 0
    DATABASE_DATA_SAVED = 1
    DATABASE_READY = 2
    DATABASE_NOT_CLOSED = 3
    DATA_SETUP_ERROR = 4

class QRSessionStatus(Enum):
    QR_WAIT = 0 # waiting for student card
    QR_CARD_READ = 1 # enrolled name found, waiting for approval
    QR_APPROVED = 2 # approved on phone, waiting for kiosk
    QR_REJECTED = 3 # too many failed card attempts
    QR_EXPIRED = 4
    QR_USED = 5 # kiosk already unlocked with this qrcode

class MainBackend:
    def __init__(self, db_path: str | Path | None = None):
        super().__init__()
        print('db: starting up')
        self.status = BackendStatus.DATABASE_WAIT
        self.db_path = Path(db_path) if db_path is not None else Path(__file__).resolve().parent.parent / 'user.db'
        try:
            with sqlite3.connect(self.db_path) as db:
                db.execute('''CREATE TABLE IF NOT EXISTS fingerprint(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    nametag TEXT NOT NULL,
                    fingerid TEXT NOT NULL,
                    fingertag TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                db.execute('''CREATE TABLE IF NOT EXISTS qrsession(
                    token TEXT PRIMARY KEY,
                    status INTEGER NOT NULL DEFAULT 0,
                    user_id INTEGER,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                ''')
            self.encryptionEnviron = Encryption()
            self.status = BackendStatus.DATABASE_READY
            print(f'db: loaded, current fingerprint enroll count: {self.count()}')
        except (sqlite3.Error, ValueError, OSError) as e:
            self.status = BackendStatus.DATABASE_GENERIC_ERROR
            print(f'{e}')

    def getStatus(self):
        return self.status

    def count(self):
        with sqlite3.connect(self.db_path) as db:
            row = db.execute('SELECT COUNT(*) FROM fingerprint;').fetchone()
            return row[0]

    def fetchInformation(self, id: int):
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                'SELECT id, name, nametag, fingerid, fingertag, created_at FROM fingerprint WHERE id = ?',
                (id,),
            ).fetchone()
        if row is None:
            return None
        record_id, name, nametag, fingerid, fingertag, created_at = row
        return {
            'id': record_id,
            'name': self.encryptionEnviron.decryptEncryptedKey(name, nametag).decode('utf-8'),
            'fingerid': self.encryptionEnviron.decryptEncryptedKey(fingerid, fingertag).decode('utf-8'),
            'created_at': created_at,
        }

    def isItemExist(self, id: int):
        if not id:
            self.status = BackendStatus.DATA_SETUP_ERROR
            raise ValueError("id parameter is required to gather the data.")
        try:
            with sqlite3.connect(self.db_path) as db:
                row = db.execute('SELECT id FROM fingerprint').fetchone()
            if not row:
                return False
            else:
                return True
        except:
            self.status = BackendStatus

    def writeInformation(self, name: str, fingerid: str):
        if not name or not fingerid:
            self.status = BackendStatus.DATA_SETUP_ERROR
            raise ValueError("name and fingerid are required.")
        encrypted_name = self.encryptionEnviron.createEncryptedKey(name)
        encrypted_fingerid = self.encryptionEnviron.createEncryptedKey(fingerid)
        
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                'INSERT INTO fingerprint (name, nametag, fingerid, fingertag) VALUES (?, ?, ?, ?)',
                (encrypted_name[0], encrypted_name[1], encrypted_fingerid[0], encrypted_fingerid[1]),
            )
            return cursor.lastrowid

    def findUserIdsByName(self, name: str): # every enrolled id with this name
        target = ''.join(name.split())
        if not target:
            return []
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute('SELECT id, name, nametag FROM fingerprint').fetchall()
        found = []
        for record_id, enc_name, nametag in rows:
            enrolled = self.encryptionEnviron.decryptEncryptedKey(enc_name, nametag).decode('utf-8')
            if ''.join(enrolled.split()) == target:
                found.append(record_id)
        return found

    # qrcode authentication
    def createQRSession(self, expire_sec: float):
        token = secrets.token_urlsafe(16)
        now = time.time()
        with sqlite3.connect(self.db_path) as db:
            db.execute('DELETE FROM qrsession WHERE expires_at < ?', (now - 3600,)) # cleanup old sessions
            db.execute(
                'INSERT INTO qrsession (token, status, created_at, expires_at) VALUES (?, ?, ?, ?)',
                (token, QRSessionStatus.QR_WAIT.value, now, now + expire_sec),
            )
        print(f'db: qrcode session created (expires in {expire_sec}s)')
        return token

    def getQRSession(self, token: str):
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                'SELECT status, user_id, attempt, expires_at FROM qrsession WHERE token = ?',
                (token,),
            ).fetchone()
        if row is None:
            return None
        status, user_id, attempt, expires_at = row
        status = QRSessionStatus(status)
        if status in (QRSessionStatus.QR_WAIT, QRSessionStatus.QR_CARD_READ, QRSessionStatus.QR_APPROVED) and time.time() > expires_at:
            status = QRSessionStatus.QR_EXPIRED
        return {'status': status, 'user_id': user_id, 'attempt': attempt}

    def setQRCardResult(self, token: str, user_id: int | None): # student card read result (None = not enrolled)
        now = time.time()
        with sqlite3.connect(self.db_path) as db:
            if user_id is not None:
                cursor = db.execute(
                    'UPDATE qrsession SET status = ?, user_id = ? WHERE token = ? AND status IN (?, ?) AND expires_at > ?',
                    (QRSessionStatus.QR_CARD_READ.value, user_id, token, QRSessionStatus.QR_WAIT.value, QRSessionStatus.QR_CARD_READ.value, now),
                )
            else:
                cursor = db.execute(
                    'UPDATE qrsession SET attempt = attempt + 1, status = CASE WHEN attempt + 1 >= ? THEN ? ELSE status END WHERE token = ? AND status IN (?, ?) AND expires_at > ?',
                    (QR_MAX_ATTEMPT, QRSessionStatus.QR_REJECTED.value, token, QRSessionStatus.QR_WAIT.value, QRSessionStatus.QR_CARD_READ.value, now),
                )
        return cursor.rowcount == 1

    def approveQRSession(self, token: str): # only the card that was read by the server can be approved
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                'UPDATE qrsession SET status = ? WHERE token = ? AND status = ? AND user_id IS NOT NULL AND expires_at > ?',
                (QRSessionStatus.QR_APPROVED.value, token, QRSessionStatus.QR_CARD_READ.value, time.time()),
            )
        return cursor.rowcount == 1

    def useQRSession(self, token: str): # kiosk side, one unlock per qrcode
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                'UPDATE qrsession SET status = ? WHERE token = ? AND status = ? AND expires_at > ?',
                (QRSessionStatus.QR_USED.value, token, QRSessionStatus.QR_APPROVED.value, time.time()),
            )
        return cursor.rowcount == 1

    def cancelQRSession(self, token: str):
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                'UPDATE qrsession SET status = ? WHERE token = ? AND status IN (?, ?, ?)',
                (QRSessionStatus.QR_EXPIRED.value, token, QRSessionStatus.QR_WAIT.value, QRSessionStatus.QR_CARD_READ.value, QRSessionStatus.QR_APPROVED.value),
            )
