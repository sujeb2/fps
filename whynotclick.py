from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import QEvent, pyqtSignal, QObject
from PyQt6.QtGui import QMouseEvent

def clickable(widget):
    class Filter(QObject):
        clicked = pyqtSignal()
        
        def eventFilter(self, obj, event):
            if obj == widget:
                if event.type() == QEvent.MousePressEvent:
                    if obj.rect().contains(event.pos()):
                        self.clicked.emit()
                        return True
            return False
    
    filter = Filter(widget)
    widget.installEventFilter(filter)
    return filter.clicked

class Label(QLabel):
    clicked = pyqtSignal()
    def __init__(self, parent=None):
        QLabel.__init__(self, parent=parent)

    def mousePressEvent(self, event):
        self.clicked.emit()

