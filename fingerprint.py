import serial, time, configparser
from enum import Enum

cfg = configparser.ConfigParser()
cfg.read('conf.ini', 'utf-8')

class FingerPrintStatus(Enum):
    DEVICE_IDLE = 0
    DEVICE_NOT_SETUP = 1

    FINGERPRINT_FAILED = 2
    FINGERPRINT_UNKNOWN = 3
    SCAN_FAILURE = 4
    SCAN_SUCCESS = 5

class FingerPrint():
    def __init__(self):
        super().__init__()
        self.port = cfg["Fingerprint"]["Port"]
        self.status = FingerPrintStatus.DEVICE_IDLE
        if not self.port: self.status = FingerPrintStatus.DEVICE_NOT_SETUP

    def getStatus(self):
        return self.status
