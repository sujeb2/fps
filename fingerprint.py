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
    FINGERPRINT_ENROLLMENT = 7 # fingerprint enrollment (register)

    SCAN_FAILURE = 5 # didn't captured
    SCAN_SUCCESS = 6
    DEBUG_MODE = 8 # dev mdoe

class FingerPrint():
    def __init__(self, isdemo):
        super().__init__()
        print('module: startup')
        self.port = cfg["Fingerprint"]["Port"]
        self.status = FingerPrintStatus.DEVICE_WAIT
        if not self.port: self.status = FingerPrintStatus.DEVICE_NOT_SETUP
        else: self.status = FingerPrintStatus.DEVICE_IDLE
        self.isdemo = isdemo
        self.ser = None # no serial in demo mode
        if not isdemo:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
        print('module: started')

    def getStatus(self):
        return self.status

    def read(self):
        try:
            if self.ser is None or not self.ser.is_open:
                self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
                time.sleep(1)
                return self.status
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
                case "ENROLLMENT_STARTED":
                    self.status = FingerPrintStatus.FINGERPRINT_ENROLLMENT
                case "DEBUGMODE":
                    self.status = FingerPrintStatus.DEBUG_MODE
                case _:
                    self.status = FingerPrintStatus.DEVICE_WAIT
        except serial.SerialTimeoutException:
            self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
            return self.status

    def write(self, data: str): # send command to esp32
        if self.isdemo:
            print(f'module: (demo) would send "{data}"')
            return True
        if self.ser is None or not self.ser.is_open:
            print(f'module: cannot send "{data}", port is not opened')
            return False
        try:
            self.ser.write(f'{data}\n'.encode('utf-8')) # esp32 reads until newline
            self.ser.flush()
            print(f'module: sent "{data}"')
            return True
        except serial.SerialException as e:
            self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
            print(f'module: failed to send "{data}" ({e})')
            return False

    def closePort(self):
        self.ser.close()
        print('module: port closed')
        return 0