import serial, time, configparser
from enum import Enum

cfg = configparser.ConfigParser()
cfg.read('conf.ini', 'utf-8')

class FingerPrintStatus(Enum):
    DEVICE_WAIT = -1
    DEVICE_IDLE = 0
    DEVICE_NOT_SETUP = 1
    DEVICE_NOT_RESPONSIVE = 2

    FINGERPRINT_FAILED = 3
    FINGERPRINT_UNKNOWN = 4

    SCAN_FAILURE = 5
    SCAN_SUCCESS = 6

class FingerPrint():
    def __init__(self):
        super().__init__()
        print('Start load module')
        self.port = cfg["Fingerprint"]["Port"]
        self.status = FingerPrintStatus.DEVICE_WAIT
        if not self.port: self.status = FingerPrintStatus.DEVICE_NOT_SETUP

    def getStatus(self):
        return self.status

    def read(self):
        try:
            ser = serial.Serial(self.port, 9600, timeout=1)
            if not ser.is_open:
                self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
                time.sleep(1)
            response = ser.readline()
            match response.decode('utf-8').strip():
                case "READY":
                    self.status = FingerPrintStatus.DEVICE_IDLE
                case _:
                    self.status = FingerPrintStatus.DEVICE_WAIT
        except serial.SerialTimeoutException:
            self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
            return self.status