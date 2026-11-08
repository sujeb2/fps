import sqlite3
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
                    fingerid TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                ''')
            self.status = BackendStatus.DATABASE_READY
            print('db: loaded')
        except sqlite3.Error as e:
            self.status = BackendStatus.DATABASE_GENERIC_ERROR
            print(f'{e}')

    def getStatus(self):
        return self.status

    def fetchInformation(self, id: int):
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                'SELECT id, name, fingerid, created_at FROM fingerprint WHERE id = ?',
                (id,),
            ).fetchone()
        if row is None:
            return None
        return dict(zip(('id', 'name', 'fingerid', 'created_at'), row))

    def writeInformation(self, name: str, fingerid: str):
        if not name or not fingerid:
            self.status = BackendStatus.DATA_SETUP_ERROR
            raise ValueError("name and fingerid are required.")
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                'INSERT INTO fingerprint (name, fingerid) VALUES (?, ?)',
                (name, fingerid),
            )
            return cursor.lastrowid