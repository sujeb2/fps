import sys, os, requests
from serial import Serial
from enum import Enum
from fingerprint import FingerPrint

class UpdateStatus(Enum):
    UPDATE_CHECK_DONE = 0
    UPDATE_URL_INVALID_OR_EMPTY = 1
    UPDATE_SERVER_REJECTED = 2
    UPDATE_DOWNLOAD_START = 3
    UPDATE_DOWNLOAD_DONE = 4
    UPDATE_IDLE = 5
    MODULE_NOT_FOUND = 6


class Update():
    def __init__(self, port: str, current_ver: str):
        super().__init__()
        print('update: start checking update')
        self.firmwareUploadPort = port
        if(self.firmwareUploadPort != ''):
            self.serial = Serial(port=self.firmwareUploadPort, baudrate=9600)
        else: self.serial = None
        self.versionRequestUrl = "http://fpsversion.songro.kro.kr/"
        self.fileRequestUrl = "http://fpsota.songro.kro.kr/"
        self.currentVersion = current_ver

    async def checkUpdate(self):
        headers = {"User-Agent": "FPSRequester/1.0", 'Content-Type': 'text/html; charset=utf-8'}
        if(self.versionRequestUrl == False): # invalid url
            print('update: update url is invalid or empty.')
            exit(UpdateStatus.UPDATE_URL_INVALID_OR_EMPTY.name)

        ver_request = requests.get(self.versionRequestUrl, headers=headers, verify=False)

        if(ver_request.status_code != 200): # server rejection
            print('update: failed to check update!!')
            exit(UpdateStatus.UPDATE_SERVER_REJECTED.name)
        elif ver_request.content != self.currentVersion:
            print(f'update: latest update found!! new version: {ver_request.content}, current version: {self.currentVersion}')
            if(self.serial != None):
                self.serial.close()
                print('update: port closed')
            else:
                exit(UpdateStatus.MODULE_NOT_FOUND.name)
        else:
            print(f'update: no update available.')