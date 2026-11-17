import serial, time, configparser
from enum import Enum

cfg = configparser.ConfigParser()
cfg.read('conf.ini', 'utf-8')

class FingerPrintStatus(Enum):
    DEVICE_WAIT = -1
    DEVICE_IDLE = 0
    DEVICE_NOT_SETUP = 1
    DEVICE_NOT_RESPONSIVE = 2
    DEVICE_FLASH_ERROR = 9
    DEVICE_BAD_LOCATION = 10

    FINGERPRINT_FAILED = 3 # register fail
    FINGERPRINT_UNKNOWN = 4 # not found
    FINGERPRINT_ENROLLMENT = 7 # fingerprint enrollment (register)

    SCAN_FAILURE = 5 # didn't captured
    SCAN_SUCCESS = 6
    DEBUG_MODE = 8 # dev mdoe

    # enrollment progress
    ENROLL_PLACE_FINGER = 11
    ENROLL_CAPTURED = 12
    ENROLL_REMOVE_FINGER = 13
    ENROLL_PLACE_AGAIN = 14
    ENROLL_IMAGE_ERROR = 15 # bad image, module asks for the finger again
    # enrollment results
    ENROLL_SUCCESS = 16
    ENROLL_MISMATCH = 17 # first and second scan were different fingers
    ENROLL_TIMEOUT = 18 # no finger in time

# one token per line from the firmware (see firmware/firmware.ino)
RESPONSES = {
    "READY": FingerPrintStatus.DEVICE_IDLE,
    "SENSOR_NOT_FOUND": FingerPrintStatus.DEVICE_NOT_SETUP,
    "SUCCESS": FingerPrintStatus.SCAN_SUCCESS,
    "NOT_FOUND": FingerPrintStatus.FINGERPRINT_UNKNOWN,
    "UNKNOWN": FingerPrintStatus.FINGERPRINT_UNKNOWN,
    "DEBUGMODE": FingerPrintStatus.DEBUG_MODE,
    "ENROLLMENT_STARTED": FingerPrintStatus.FINGERPRINT_ENROLLMENT,
    "PLACE_FINGER": FingerPrintStatus.ENROLL_PLACE_FINGER,
    "CAPTURED": FingerPrintStatus.ENROLL_CAPTURED,
    "REMOVE_FINGER": FingerPrintStatus.ENROLL_REMOVE_FINGER,
    "PLACE_AGAIN": FingerPrintStatus.ENROLL_PLACE_AGAIN,
    "IMAGE_ERROR": FingerPrintStatus.ENROLL_IMAGE_ERROR,
    "ENROLLED": FingerPrintStatus.ENROLL_SUCCESS,
    "MISMATCH": FingerPrintStatus.ENROLL_MISMATCH,
    "TIMEOUT": FingerPrintStatus.ENROLL_TIMEOUT,
    "FAILED": FingerPrintStatus.FINGERPRINT_FAILED,
    "FLASH_ERROR": FingerPrintStatus.DEVICE_FLASH_ERROR,
    "BAD_LOCATION": FingerPrintStatus.DEVICE_BAD_LOCATION,
}

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
        self.buffer = b''
        self.matchedSlot = None # sensor slot of the last SUCCESS:<slot>
        if not isdemo and self.status != FingerPrintStatus.DEVICE_NOT_SETUP:
            try:
                self.ser = serial.Serial(self.port, 9600, timeout=0) # non blocking, read() is polled from the ui timer
            except serial.SerialException as e:
                print(f'module: cannot open {self.port} ({e})')
                self.status = FingerPrintStatus.DEVICE_NOT_SETUP
        print('module: started')

    def getStatus(self):
        return self.status

    def read(self): # returns every status received since the last call, oldest first
        if self.isdemo:
            return []
        if self.ser is None or not self.ser.is_open:
            self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
            return []
        try:
            waiting = self.ser.in_waiting
            if waiting:
                self.buffer += self.ser.read(waiting)
        except serial.SerialException as e: # unplugged
            print(f'module: read failed ({e})')
            self.status = FingerPrintStatus.DEVICE_NOT_RESPONSIVE
            return []

        events = []
        *lines, self.buffer = self.buffer.split(b'\n') # keep the unfinished line for the next call
        for line in lines:
            text = line.decode('utf-8', errors='replace').strip()
            if not text:
                continue
            if text.startswith('LOG:'):
                print(f'module: {text[4:]}')
                continue
            token, _, arg = text.partition(':') # SUCCESS:<slot> carries the matched slot
            status = RESPONSES.get(token)
            if status == FingerPrintStatus.SCAN_SUCCESS:
                self.matchedSlot = int(arg) if arg.isdigit() else None
            if status is None:
                print(f'module: unknown response "{text}"')
                continue
            self.status = status
            events.append(status)
        return events

    def enroll(self, slot: int): # stores the next scanned finger in sensor slot
        return self.write(f'ENROLL:{slot}')

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
        if self.ser is not None:
            self.ser.close()
        print('module: port closed')
        return 0
