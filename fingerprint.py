import serial, time, configparser
from enum import Enum

cfg = configparser.ConfigParser()
cfg.read('conf.ini', 'utf-8')

class FingerPrintStatus(Enum):
    DEVICE_WAIT = -1
    DEVICE_IDLE = 0
    DEVICE_NOT_SETUP = 1
    DEVICE_NOT_RESPONSIVE = 2

    FINGERPRINT_FAILED = 3 # register fail
    FINGERPRINT_UNKNOWN = 4 # not found

    SCAN_FAILURE = 5 # didn't captured
    SCAN_SUCCESS = 6

class FingerPrint():
    def __init__(self):
        super().__init__()
        print('module: startup')
        self.port = cfg["Fingerprint"]["Port"]
        self.status = FingerPrintStatus.DEVICE_WAIT
        if not self.port: self.status = FingerPrintStatus.DEVICE_NOT_SETUP
        else: self.status = FingerPrintStatus.DEVICE_IDLE
        self.ser = serial.Serial(self.port, 9600, timeout=1)
        print('module: started')

    def getStatus(self):
        return self.status

    def read(self):
        try:
            if not self.ser.is_open:
                self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
                time.sleep(1)
            response = self.ser.readline()
            match response.decode('utf-8').strip():
                case "READY": # fingerprint idle
                    self.status = FingerPrintStatus.DEVICE_IDLE
                case "SUCCESS": # fingerprint found
                    return self.ser.readline()
                case "FAILED": # fingerprint read error
                    self.status = FingerPrintStatus.FINGERPRINT_FAILED
                case "NOT_FOUND": # fingerprint not found
                    self.status = FingerPrintStatus.FINGERPRINT_UNKNOWN
                case "CAPTURED": # fingerprint capture status
                    return response
                case _:
                    self.status = FingerPrintStatus.DEVICE_WAIT
        except serial.SerialTimeoutException:
            self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
            return self.status

    def closePort(self):
        self.ser.close()
        print('module: port closed')
        return 0