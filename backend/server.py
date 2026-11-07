import sqlite3
from fastapi import FastAPI
from enum import Enum

class BackendStatus(Enum):
    DATABASE_GENERIC_ERROR = -1
    DATABASE_WAIT = 0

class MainBackend:
    def __init__(self):
        super().__init__()
        try:
            self.db = sqlite3.connect('user.db')
            self.con = self.db.cursor()
            self.status = BackendStatus.DATABASE_WAIT
        except sqlite3.Error:
            self.status = BackendStatus.DATABASE_GENERIC_ERROR