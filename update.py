import requests, esptool, subprocess
from serial import Serial
from enum import Enum
from urllib.parse import urljoin

class UpdateStatus(Enum):
    UPDATE_CHECK_DONE = 0
    UPDATE_URL_INVALID_OR_EMPTY = 1
    UPDATE_SERVER_REJECTED = 2
    UPDATE_DOWNLOAD_START = 3
    UPDATE_DOWNLOAD_DONE = 4
    UPDATE_IDLE = 5
    MODULE_NOT_FOUND = 6
    FIRMWARE_UPLOAD_FAILED = 7
    FIRMWARE_FILE_VERIFY_FAILED = 8
    FIRMWARE_WRITE_REJECTED = 9
    GENERIC_FIRMWARE_ERROR = 10


class Update():
    def __init__(self, port: str, current_ver: str):
        super().__init__()
        print('update: start checking update')
        self.firmwareUploadPort = port
        self.versionRequestUrl = "http://fpsversion.songro.kro.kr/"
        self.fileRequestUrl = "http://fpsota.songro.kro.kr/"
        self.currentVersion = current_ver
        self.isUpdateRequired = False
        self.newVersion = ''
        if(self.firmwareUploadPort != ''):
            try:
                self.serial = Serial(port=str(self.firmwareUploadPort), baudrate=9600)
                self.checkUpdate()
            except:
                print(f'update: cannot find port named {port}, only checking update..')
                self.checkUpdate()
        else: self.serial = None

    def checkUpdate(self):
        headers = {"User-Agent": "FPSRequester/1.0", 'Content-Type': 'text/html; charset=utf-8'}
        if(self.versionRequestUrl == False): # invalid url
            print('update: update url is invalid or empty.')
            exit(UpdateStatus.UPDATE_URL_INVALID_OR_EMPTY.name)

        ver_request = requests.get(self.versionRequestUrl, headers=headers, verify=False)
        print(f'update: requested, version got: {ver_request.content}')
        #got_ver = str.strip(ver_request.content)
        if(ver_request.status_code != 200): # server rejection
            print('update: failed to check update!!')
            exit(UpdateStatus.UPDATE_SERVER_REJECTED.name)
        elif ver_request.content != self.currentVersion:
            print(f'update: latest update found!! new version: {ver_request.content}, current version: {self.currentVersion}')
            self.isUpdateRequired = True
            self.newVersion = ver_request.content
        else:
            self.isUpdateRequired = False
            self.newVersion = self.currentVersion

    def startUpdate(self):
        headers = {"User-Agent": "FPSRequester/1.0", 'Content-Type': 'text/html; charset=utf-8'}
        if(self.versionRequestUrl == False): # invalid url
            print('update: update url is invalid or empty.')
            exit(UpdateStatus.UPDATE_URL_INVALID_OR_EMPTY.name)

        ver_request = requests.get(self.versionRequestUrl, headers=headers, verify=False)
        print(f'update: requested, version got: {ver_request.content}')

        if self.isUpdateRequired: 
            if(self.serial != None):
                self.serial.close()
                print('update: port closed')
                header = {"User-Agent": "FPSFileRequester/1.0"}
                print('update: start downloading firmware')
                file_request = requests.get(urljoin(self.fileRequestUrl, f"firmware-v{self.newVersion}.bin"), header)
                try:
                    with open("data/firmware-loaded/firmware-new.bin", "wb+") as f:
                        f.write(file_request.content)
                        print('update: download done!!')
                    runnable = ['--port', self.firmwareUploadPort, 'write_flash', '0x1000', "firmware-new.bin"]
                    esptool.main(runnable)
                    print('update: update done, please restart the system')
                except subprocess.CalledProcessError:
                    exit(UpdateStatus.FIRMWARE_WRITE_REJECTED.name)
                except FileNotFoundError:
                    exit(UpdateStatus.FIRMWARE_FILE_VERIFY_FAILED.name)
                except Exception:
                    exit(UpdateStatus.GENERIC_FIRMWARE_ERROR.name)
            else:
                exit(UpdateStatus.MODULE_NOT_FOUND.name)
        else: print('update: cannot find any other new updates available.')