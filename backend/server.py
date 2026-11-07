import sqlite3
from fastapi import FastAPI
from enum import Enum

class BackendStatus(Enum):
    DATABASE_GENERIC_ERROR = -1
    DATABASE_WAIT = 0
    DATABASE_DATA_SAVED = 1
    DATABASE_NOT_CLOSED = 3

class MainBackend:
    def __init__(self):
        super().__init__()
        print('db: starting up')
        self.status = BackendStatus.DATABASE_WAIT
        try:
            self.db = sqlite3.connect('user.db')
            self.con = self.db.cursor()
            self.con.execute('''CREATE TABLE IF NOT EXISTS fingerprint(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                fingerid TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            self.db.commit()
            self.db.close()
            print('db: loaded')
        except sqlite3.Error as e:
            self.status = BackendStatus.DATABASE_GENERIC_ERROR
            print(f'{e}')

    def getStatus(self):
        return self.status

    def fetchInformation(self, id: int):
        self.con.execute('SELECT * FROM fingerprint')
        self.rows = self.con.fetchall()
        print(f'db: fetched user id {id+1}, information: {self.rows[id+1]}')
        return self.rows[id+1]