import configparser, sys, platform, argparse, asyncio, whynotclick
from fontTools.ttLib import TTFont
from fingerprint import FingerPrintStatus, FingerPrint
from backend.server import BackendStatus, MainBackend, QRSessionStatus
from qrgenerator import QRCode

from PyQt6.QtWidgets import QWidget, QLabel, QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QDateTime
from PyQt6 import QtCore
from update import Update

cfg = configparser.ConfigParser()
cfg.read(filenames='conf.ini', encoding="utf-8")
COLOR_MAIN = f'background-color : white; Color : {cfg["School"]["MainColor"]};'
COLOR_SUB = f'background-color : white; Color : {cfg["School"]["SubColor"]};'
COLOR_FAILED = f'background-color : white; Color : #ff3f2e;'
COLOR_SUCCESS = f'background-color : white; Color : #9dff73;'
QRCODE_SIZE = 150 # fits between status warning and finger status text

class Main(QWidget):
    def __init__(self, isdemo):
        self.isdemo = isdemo
        print(f'Start fps-project.. PyQt Version: {QtCore.qVersion()}, isdemo: {self.isdemo}')
        super().__init__()
        
        print('font: start checking font installation')
        try:
            font = TTFont('src\\font\\wanted.ttf')
        except FileNotFoundError:
            print('font: failed to find font file!!')
        # check only: never raises, so the app still starts offline. Flashing runs from `python update.py` with the app stopped.
        self.updater = Update(cfg["Fingerprint"]["Port"], cfg["Generic"]["Version"])
        self.isUpdateRequired = self.updater.isUpdateRequired

        self.setWindowTitle("fps")
        self.setStyleSheet("background-color : white;")
        self.setFixedSize(600, 1024)
        self.lockStatusImg = [QPixmap("assets/imgs/idle.png"), QPixmap("assets/imgs/unlock.png"), QPixmap("assets/imgs/unknown.png"), QPixmap("assets/imgs/fingerprint.png")]
        self.statusImg = [QPixmap("assets/imgs/action_required.png"), QPixmap("assets/imgs/update_required.png")]
        
        # fingerprint
        self.fingerPrintModule = FingerPrint(self.isdemo)
        self.fingerPrintStatus = self.fingerPrintModule.getStatus()

        # qrcode
        self.qrcode = QRCode()
        self.qrToken = None # current qrcode session, None when not in use
        self.qrImagePath = None

        # server
        self.backend = MainBackend()
        if self.backend.getStatus() != BackendStatus.DATABASE_READY:
            self.showError("정상적으로 백앤드에 접속하지 못하였습니다.\n다른 프로세스가 접근하고 있는지 확인해주십시오.")

        if self.isdemo == '':
            if self.fingerPrintStatus != FingerPrintStatus.DEVICE_NOT_SETUP:
                self.idleUISetup()

                # fingerprint module checker
                self.checkFingerprintStatus()
                self.fingerPrintStatusTicker = QtCore.QTimer(self)
                self.fingerPrintStatusTicker.timeout.connect(self.checkFingerprintStatus)
                self.fingerPrintStatusTicker.start(1000)

                # date time (label_CurrentDateTime only exists after setupWidget)
                self.updateCurrentDateTime()
                self.dateTimeTimer = QtCore.QTimer(self)
                self.dateTimeTimer.timeout.connect(self.updateCurrentDateTime)
                self.dateTimeTimer.start(1000)
            else:
                self.showError("모듈이 정상적으로 인식이 되지 않습니다.\n유지보수 판을 열어 모듈의 연결선이 정상적으로 연결이 되어있는지 확인해주십시오.")
        else:
            self.idleUISetup() # demo mode
            self.updateCurrentDateTime()
            self.dateTimeTimer = QtCore.QTimer(self)
            self.dateTimeTimer.timeout.connect(self.updateCurrentDateTime)
            self.dateTimeTimer.start(1000)

        if platform.system() not in ('Darwin', 'Windows'):
            self.showMaximized()

    def idleUISetup(self):
        roomName = cfg["School"]["RoomName"]
        schoolName = cfg["School"]["SchoolName"]
        if not roomName: roomName = "지정되지 않은 이름"
        elif not schoolName: schoolName = "지정되지 않은 이름"

        # default status
        self.label_SchoolName = QLabel(schoolName ,self)
        self.label_RoomName = QLabel(roomName, self)
        #self.label_versionInfo = QLabel(cfg["Generic"]["Version"], self)
        self.fingerStatus = QLabel("지문을 기다리는 중..", self)
        self.label_CurrentDateTime = QLabel(self)
        self.label_subTitleText = QLabel(self)

        self.btn_QRcodeGeneration = whynotclick.Label(self)
        self.btn_QRcodeGeneration.setText("아니면 QR코드 인식하기")

        # images
        self.img_LockStatus = QLabel(self)
        self.img_LockStatus.setPixmap(self.lockStatusImg[0])

        self.img_SchoolLogo = QLabel(self)
        self.img_SchoolLogo.setPixmap(QPixmap('assets/imgs/schoollogo.png'))

        self.img_TemporaryQRCode = QLabel(self)
        self.img_TemporaryQRCode.hide()

        self.status_ActionWarn = QLabel(self)
        if cfg["School"]["RoomRequiresEnrollment"] == "True":
            self.status_ActionWarn.setPixmap(self.statusImg[0])
        if self.isUpdateRequired:
            self.status_ActionWarn.setPixmap(self.statusImg[1])
        self.status_ActionWarn.adjustSize()

        # fonts
        self.font_default = self.label_SchoolName.font()
        self.font_default.setFamily('Pretendard JP Variable')
        self.font_default.setPointSize(60)
        self.font_default.setBold(True)

        self.font_sub = self.label_SchoolName.font()
        self.font_sub.setFamily('Pretendard JP Variable')
        self.font_sub.setPointSize(22)
        self.font_sub.setBold(True)

        self.font_date = self.label_SchoolName.font()
        self.font_date.setFamily('Pretendard JP Variable')
        self.font_date.setPointSize(30)
        self.font_date.setBold(True)

        self.font_smalltip = self.label_subTitleText.font()
        self.font_smalltip.setFamily('Pretendard JP Variable')
        self.font_smalltip.setPointSize(15)
        self.font_smalltip.setBold(True)

        # text color setup
        self.label_SchoolName.setStyleSheet(COLOR_MAIN)
        self.label_RoomName.setStyleSheet(COLOR_MAIN)
        self.label_CurrentDateTime.setStyleSheet(COLOR_SUB)
        self.fingerStatus.setStyleSheet(COLOR_MAIN)
        self.btn_QRcodeGeneration.setStyleSheet(COLOR_SUB)
        self.label_subTitleText.setStatusTip(COLOR_SUB)

        self.img_SchoolLogo.resize(116, 116)
        self.img_SchoolLogo.move(50, 45)
        self.label_SchoolName.move(187, 68)
        self.label_RoomName.move(50, 394)
        self.label_CurrentDateTime.move(50, 336)
        self.img_LockStatus.move(266, 759)
        self.status_ActionWarn.move(50, 505)
        self.btn_QRcodeGeneration.move(137, 946)
        self.label_subTitleText.move(50, 483)

        # qrcode goes to the same spot as lock status image
        lockCenter = QtCore.QRect(self.img_LockStatus.pos(), self.lockStatusImg[0].size()).center()
        self.img_TemporaryQRCode.setGeometry(lockCenter.x() - QRCODE_SIZE // 2, lockCenter.y() - QRCODE_SIZE // 2, QRCODE_SIZE, QRCODE_SIZE)

        self.label_RoomName.setFont(self.font_default)
        self.label_SchoolName.setFont(self.font_default)
        self.fingerStatus.setFont(self.font_sub)
        self.label_CurrentDateTime.setFont(self.font_date)
        self.btn_QRcodeGeneration.setFont(self.font_sub)
        self.label_subTitleText.setFont(self.font_smalltip)

        self.fingerStatus.setGeometry(0, 879, 600, 77) # centerize or smth
        self.fingerStatus.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.label_SchoolName.adjustSize()
        self.label_RoomName.adjustSize()

        self.btn_QRcodeGeneration.clicked.connect(self.genQRCode)

        # qrcode session checker (started when qrcode is shown)
        self.qrStatusTicker = QtCore.QTimer(self)
        self.qrStatusTicker.timeout.connect(self.checkQRSession)

    def genQRCode(self):
        if self.qrToken: # second click cancels
            self.backend.cancelQRSession(self.qrToken)
            self.resetQRCodeUI()
            return
        serverUrl = cfg["QRCode"]["ServerURL"].rstrip('/')
        if not serverUrl:
            self.fingerStatus.setText("QR코드 서버가 설정되지 않았습니다.")
            self.fingerStatus.setStyleSheet(COLOR_FAILED)
            return

        self.qrToken = self.backend.createQRSession(float(cfg["QRCode"]["ExpireTime"]))
        self.qrImagePath = self.qrcode.generate(f'{serverUrl}/qr/{self.qrToken}', self.qrToken)
        self.img_TemporaryQRCode.setPixmap(QPixmap(self.qrImagePath).scaled(
            QRCODE_SIZE, QRCODE_SIZE,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.FastTransformation, # keep qrcode edges sharp
        ))
        self.img_LockStatus.hide()
        self.img_TemporaryQRCode.show()

        self.fingerStatus.setText("휴대폰으로 QR코드를 스캔해주세요.")
        self.fingerStatus.setStyleSheet(COLOR_MAIN)
        self.btn_QRcodeGeneration.setText("QR코드 인증 취소하기")
        self.btn_QRcodeGeneration.adjustSize()
        self.qrStatusTicker.start(1000)

    def checkQRSession(self):
        session = self.backend.getQRSession(self.qrToken)
        status = session['status'] if session else QRSessionStatus.QR_EXPIRED
        match status:
            case QRSessionStatus.QR_WAIT: # waiting for student card
                pass
            case QRSessionStatus.QR_CARD_READ: # waiting for approval on phone
                self.fingerStatus.setText("휴대폰에서 승인해주세요.")
            case QRSessionStatus.QR_APPROVED:
                if self.backend.useQRSession(self.qrToken): # only unlock once
                    self.qrStatusTicker.stop()
                    information = self.backend.fetchInformation(session['user_id'])
                    isSent = self.fingerPrintModule.write(cfg["QRCode"]["UnlockCommand"])
                    self.qrUpdateUISetup(isSent, information['name'] if information else '')
            case _: # rejected or expired
                self.qrStatusTicker.stop()
                self.qrUpdateUISetup(False, None)

    def qrUpdateUISetup(self, isSuccess: bool, name: str | None): # qrcode status update
        self.img_TemporaryQRCode.hide()
        self.img_LockStatus.show()
        if isSuccess:
            self.dateTimeTimer.stop()
            self.label_CurrentDateTime.setText(f"안녕하세요, {name}님.")
            self.label_CurrentDateTime.adjustSize()
            self.fingerStatus.setText("확인 되었습니다.")
            self.fingerStatus.setStyleSheet(COLOR_SUCCESS)
            self.img_LockStatus.setPixmap(self.lockStatusImg[1])
        else:
            self.fingerStatus.setText("QR코드 인증에 실패했습니다." if name is None else "문을 열지 못했습니다.")
            self.fingerStatus.setStyleSheet(COLOR_FAILED)
            self.img_LockStatus.setPixmap(self.lockStatusImg[2])
        # non blocking wait, back to idle
        QtCore.QTimer.singleShot(int(float(cfg["Generic"]["FingerprintStatusUpdateTime"]) * 1000), self.resetQRCodeUI)

    def resetQRCodeUI(self):
        if self.qrToken is None:
            return
        self.qrStatusTicker.stop()
        if self.qrImagePath:
            self.qrcode.remove(self.qrImagePath)
        self.qrToken = None
        self.qrImagePath = None

        self.img_TemporaryQRCode.hide()
        self.img_TemporaryQRCode.clear()
        self.img_LockStatus.setPixmap(self.lockStatusImg[0])
        self.img_LockStatus.show()
        self.fingerStatus.setText("지문을 기다리는 중..")
        self.fingerStatus.setStyleSheet(COLOR_MAIN)
        self.btn_QRcodeGeneration.setText("아니면 QR코드 인식하기")
        self.btn_QRcodeGeneration.adjustSize()
        self.updateCurrentDateTime()
        if not self.dateTimeTimer.isActive():
            self.dateTimeTimer.start(1000)

    async def scanUpdateUISetup(self, status: FingerPrintStatus): # fingerprint status update
        if not status:
            raise ValueError("Invalid User name parameter.")
        match status:
            case FingerPrintStatus.SCAN_SUCCESS: # fingerprint success
                self.dateTimeTimer.stop()
                self.label_CurrentDateTime.setText(f"안녕하세요, (USRNAME)님.")
                self.fingerStatus.setText("확인 되었습니다.")
                self.fingerStatus.setStyleSheet(COLOR_SUCCESS)
                self.fingerStatus.adjustSize()
                self.img_LockStatus.setPixmap(self.lockStatusImg[1])
                await asyncio.sleep(float(cfg["Generic"]["FingerprintStatusUpdateTime"]))
                self.dateTimeTimer.start(1000)
            case FingerPrintStatus.FINGERPRINT_ENROLLMENT:
                self.startEnrollment()
            case _: # any other status update
                self.img_LockStatus.setPixmap(self.lockStatusImg[2])
                self.fingerStatus.setText("알 수 없는 지문입니다.")
                self.fingerStatus.setStyleSheet(COLOR_FAILED)
                self.fingerStatus.adjustSize()
                await asyncio.sleep(float(cfg["Generic"]["FingerprintStatusUpdateTime"]))

    def startEnrollment(self):
        self.dateTimeTimer.stop()

        # ui setup
        self.label_CurrentDateTime.setText("환영합니다!")
        self.label_RoomName.setText("지문 등록을 시작합니다.")
        self.label_RoomName.adjustSize()
        

    def showError(self, error_name: str):
        full_log = error_name+f"\n\nFINGERPRINT CODE: {self.fingerPrintStatus.name}\nBACKEND CODE: {self.backend.getStatus().name}"

        print(f"FAILED!!\nError log: {full_log}")
        self.setStyleSheet("background-color : black;")
        self.errorBg = QLabel(self)
        self.errorBg.setPixmap(QPixmap('assets/imgs/error.png'))
        self.errorBg.adjustSize()
        # center the error frame in the window
        bgX = (self.width() - self.errorBg.width()) // 2
        bgY = (self.height() - self.errorBg.height()) // 2
        self.errorBg.move(bgX, bgY)

        self.errorLog = QLabel(full_log, self) # error msg
        self.errorLog.setStyleSheet("background-color : transparent; color : white;")
        font_error = self.errorLog.font()
        font_error.setFamily('Pretendard JP Variable')
        font_error.setPointSize(16)
        self.errorLog.setFont(font_error)
        self.errorLog.setWordWrap(True)
        self.errorLog.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.errorLog.setGeometry(bgX + 44, bgY + 115, 414, 145)

    def updateCurrentDateTime(self):
        currentDateTime = QDateTime.currentDateTime()
        self.label_CurrentDateTime.setText(currentDateTime.toString("yyyy/MM/dd h:mmAP"))
        self.label_CurrentDateTime.adjustSize()

    def checkFingerprintStatus(self):
        if self.qrToken: # qrcode authentication in progress
            return
        self.status = self.fingerPrintModule.getStatus()
        match self.status:
            case FingerPrintStatus.DEVICE_NOT_RESPONSIVE:
                self.showError(f"모듈 응답이 없습니다.\n이 화면이 처음이면 기기를 재부팅 해주십시오.")
            case FingerPrintStatus.DEVICE_NOT_SETUP:
                self.showError(f"모듈이 정상적으로 인식이 되지 않습니다.\n유지보수 판을 열어 모듈의 연결선이 정상적으로 연결이 되어있는지 확인해주십시오.")
            case _:
                asyncio.run(self.scanUpdateUISetup(self.status))

if __name__ == '__main__':
    parse = argparse.ArgumentParser()
    parse.add_argument('--demo', default='', help='enable demo mode (module not required)')
    arg = parse.parse_args()

    app = QApplication(sys.argv[0:])
    win = Main(arg.demo)
    win.show()
    app.exec()