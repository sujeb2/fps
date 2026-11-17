from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QEvent, Signal, QObject
from PySide6.QtGui import QMouseEvent

def clickable(widget):
    class Filter(QObject):
        clicked = Signal()
        
        def eventFilter(self, obj, event):
            if obj == widget:
                if event.type() == QEvent.Type.MousePressEvent:
                    if obj.rect().contains(event.position().toPoint()):
                        self.clicked.emit()
                        return True
            return False
    
    filter = Filter(widget)
    widget.installEventFilter(filter)
    return filter.clicked

class Label(QLabel):
    clicked = Signal()
    def __init__(self, parent=None):
        QLabel.__init__(self, parent=parent)

    def mousePressEvent(self, event):
        self.clicked.emit()

