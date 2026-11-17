import requests, esptool, subprocess, ssl
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
        self.url = "https://fps-ota.pages.dev"
        self.currentVersion = current_ver
        self.isUpdateRequired = False
        self.newVersion = ''
        self.gotVersionInfo = []
        if(self.firmwareUploadPort != ''):
            try:
                self.serial = Serial(port=str(self.firmwareUploadPort), baudrate=9600)
                self.serial.close() # only a presence check, the fingerprint module needs this port (exclusive on windows)
                self.checkUpdate()
            except:
                print(f'update: cannot find port named {port}, only checking update..')
                self.checkUpdate()
        else: self.serial = None

    def checkUpdate(self):
        headers = {"User-Agent": "FPSRequester/1.0", 'Content-Type': 'text/html; charset=utf-8'}
        if(self.url == False): # invalid url
            print('update: update url is invalid or empty.')
            exit(UpdateStatus.UPDATE_URL_INVALID_OR_EMPTY.name)

        ver_request = requests.get(f"{self.url}/version.json", headers=headers, verify=False)
        if ver_request.status_code == 200:
            self.gotVersionInfo = ver_request.json()
            got_ver = self.gotVersionInfo["version"]
            print(f'update: requested, version got: {got_ver}')
            if(ver_request.status_code != 200): # server rejection
                print('update: failed to check update!!')
                exit(UpdateStatus.UPDATE_SERVER_REJECTED.name)
            elif got_ver != self.currentVersion:
                print(f'update: latest update found!! new version: {got_ver}, current version: {self.currentVersion}')
                self.isUpdateRequired = True
                self.newVersion = got_ver
            else:
                print(f'update: no update found')
                self.isUpdateRequired = False
                self.newVersion = self.currentVersion
        else:
            print('update: ota sever is not available at this moment please try again later.')

    def startUpdate(self):
        headers = {"User-Agent": "FPSRequester/1.0", 'Content-Type': 'text/html; charset=utf-8'}
        if(self.url == False): # invalid url
            print('update: update url is invalid or empty.')
            exit(UpdateStatus.UPDATE_URL_INVALID_OR_EMPTY.name)

        ver_request = requests.get(self.url, headers=headers, verify=False)
        print(f'update: requested, version got: {ver_request.content}')

        if self.isUpdateRequired: 
            if(self.serial != None):
                self.serial.close()
                print('update: port closed')
                header = {"User-Agent": "FPSFileRequester/1.0"}
                print('update: start downloading firmware')
                file_request = requests.get(urljoin(self.url, self.gotVersionInfo["file_name"]), header)
                if file_request.status_code == 200:
                    try:
                        with open("data/firmware-loaded/firmware-new.bin", "wb+") as f:
                            f.write(file_request.content)
                        print(f'update: download done!! (filesize: {len(file_request.content)}bytes.)')
                        print('update: start uploading..')
                        runnable = ['--port', self.firmwareUploadPort, 'write_flash', '0x1000', "firmware-new.bin"]
                        esptool.main(runnable)
                        print('update: update done, please restart the system')
                    except subprocess.CalledProcessError:
                        exit(UpdateStatus.FIRMWARE_WRITE_REJECTED.name)
                    except FileNotFoundError:
                        exit(UpdateStatus.FIRMWARE_FILE_VERIFY_FAILED.name)
                    except Exception:
                        exit(UpdateStatus.GENERIC_FIRMWARE_ERROR.name)
                else: # server invalid or unavailable
                    exit(UpdateStatus.UPDATE_SERVER_REJECTED.name)
            else:
                exit(UpdateStatus.MODULE_NOT_FOUND.name)
        else: print('update: cannot find any other new updates available.')