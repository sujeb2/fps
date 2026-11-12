import sqlite3
from backend.encryption import Encryption
from enum import Enum
from pathlib import Path

class BackendStatus(Enum):
    DATABASE_GENERIC_ERROR = -1
    DATABASE_WAIT = 0
    DATABASE_DATA_SAVED = 1
    DATABASE_READY = 2
    DATABASE_NOT_CLOSED = 3
    DATA_SETUP_ERROR = 4

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