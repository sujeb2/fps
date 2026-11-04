import configparser, sys, platform, whynotclick
from PyQt6.QtWidgets import QWidget, QLabel, QListView, QApplication
from PyQt6.QtGui import QPixmap
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
        if platform.system() not in ('Darwin', 'Windows'):
            self.showMaximized()
        self.setupWidget()
        

    def setupWidget(self):
        roomName = cfg["School"]["RoomName"]
        schoolName = cfg["School"]["SchoolName"]
        if(roomName == "" or schoolName == ""): roomName = "지정되지 않은 이름"

        # default status
        self.label_SchoolName = QLabel(schoolName ,self)
        self.label_RoomName = QLabel(roomName, self)
        self.fingerStatus = QLabel("지문을 기다리는 중..", self)

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
        self.font_sub.setPointSize(48)
        self.font_sub.setBold(True)

        # text color setup
        self.label_SchoolName.setStyleSheet(COLOR_MAIN)
        self.label_RoomName.setStyleSheet(COLOR_MAIN)

        self.img_SchoolLogo.resize(116, 116)
        self.img_SchoolLogo.move(50, 45)
        self.label_SchoolName.move(187, 68)
        self.label_RoomName.move(50, 394)
        self.img_LockStatus.move(266, 759)
        self.fingerStatus.move(266, 879)

        self.label_RoomName.setFont(self.font_default)
        self.label_SchoolName.setFont(self.font_default)
        self.fingerStatus.setFont(self.font_sub)

if __name__ == '__main__':
    app = QApplication(sys.argv[0:])
    win = Main()
    win.show()
    app.exec()