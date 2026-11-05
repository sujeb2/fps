import configparser, sys, platform, whynotclick
from fingerprint import FingerPrintStatus, FingerPrint
from PyQt6.QtWidgets import QWidget, QLabel, QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QDateTime
from PyQt6 import QtCore

cfg = configparser.ConfigParser()
cfg.read(filenames='conf.ini', encoding="utf-8")
COLOR_MAIN = f'background-color : white; Color : {cfg["School"]["MainColor"]};'
COLOR_SUB = f'background-color : white; Color : {cfg["School"]["SubColor"]};'

class Main(QWidget):
    def __init__(self):
        print(f'Start fps-project.. PyQt Version: {QtCore.qVersion()}')
        super().__init__()

        self.setWindowTitle("fps")
        self.setStyleSheet("background-color : white;")
        self.setFixedSize(600, 1024)

        # fingerprint status
        self.fingerPrintModule = FingerPrint()
        self.fingerPrintStatus = self.fingerPrintModule.getStatus()
        if self.fingerPrintStatus != FingerPrintStatus.DEVICE_NOT_SETUP:
            self.setupWidget()

            # date time (label_CurrentDateTime only exists after setupWidget)
            self.updateCurrentDateTime()
            self.dateTimeTimer = QtCore.QTimer(self)
            self.dateTimeTimer.timeout.connect(self.updateCurrentDateTime)
            self.dateTimeTimer.start(1000)
        else:
            self.showError("모듈이 정상적으로 인식이 되지 않습니다.\n유지보수 판을 열어 모듈의 연결선이 정상적으로 연결이 되어있는지 확인해주십시오.")

        # show only after children exist, otherwise they stay hidden on Linux
        if platform.system() not in ('Darwin', 'Windows'):
            self.showMaximized()

    def setupWidget(self):
        roomName = cfg["School"]["RoomName"]
        schoolName = cfg["School"]["SchoolName"]
        if not roomName: roomName = "지정되지 않은 이름"
        elif not schoolName: schoolName = "지정되지 않은 이름"

        # default status
        self.label_SchoolName = QLabel(schoolName ,self)
        self.label_RoomName = QLabel(roomName, self)
        self.fingerStatus = QLabel("지문을 기다리는 중..", self)
        self.label_CurrentDateTime = QLabel(self)

        # images
        self.img_LockStatus = QLabel(self)
        self.img_LockStatus.setPixmap(QPixmap('assets/imgs/idle.png'))
        self.img_SchoolLogo = QLabel(self)
        self.img_SchoolLogo.setPixmap(QPixmap('assets/imgs/schoollogo.png'))

        # fonts
        self.font_default = self.label_SchoolName.font()
        self.font_default.setFamily('Pretendard JP Variable')
        self.font_default.setPointSize(64)
        self.font_default.setBold(True)

        self.font_sub = self.label_SchoolName.font()
        self.font_sub.setFamily('Pretendard JP Variable')
        self.font_sub.setPointSize(24)
        self.font_sub.setBold(True)

        self.font_date = self.label_SchoolName.font()
        self.font_date.setFamily('Pretendard JP Variable')
        self.font_date.setPointSize(36)
        self.font_date.setBold(True)

        # text color setup
        self.label_SchoolName.setStyleSheet(COLOR_MAIN)
        self.label_RoomName.setStyleSheet(COLOR_MAIN)
        self.label_CurrentDateTime.setStyleSheet(COLOR_SUB)
        self.fingerStatus.setStyleSheet(COLOR_MAIN)

        self.img_SchoolLogo.resize(116, 116)
        self.img_SchoolLogo.move(50, 45)
        self.label_SchoolName.move(187, 68)
        self.label_RoomName.move(50, 394)
        self.label_CurrentDateTime.move(50, 336)
        self.img_LockStatus.move(266, 759)

        self.label_RoomName.setFont(self.font_default)
        self.label_SchoolName.setFont(self.font_default)
        self.fingerStatus.setFont(self.font_sub)
        self.label_CurrentDateTime.setFont(self.font_date)

        # full window width, centered under the lock icon
        self.fingerStatus.setGeometry(0, 879, 600, 77)
        self.fingerStatus.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.label_SchoolName.adjustSize()
        self.label_RoomName.adjustSize()

    def showError(self, error_name: str):
        self.setStyleSheet("background-color : black;")
        self.errorBg = QLabel(self)
        self.errorBg.setPixmap(QPixmap('assets/imgs/error.png'))
        self.errorBg.adjustSize()
        # center the error frame in the window
        bgX = (self.width() - self.errorBg.width()) // 2
        bgY = (self.height() - self.errorBg.height()) // 2
        self.errorBg.move(bgX, bgY)

        # message goes inside the frame, under its divider line
        self.errorLog = QLabel(error_name, self)
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

if __name__ == '__main__':
    app = QApplication(sys.argv[0:])
    win = Main()
    win.show()
    app.exec()