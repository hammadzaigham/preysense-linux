"""Shared 30px title bar matching the Windows WindowTitleBar control."""
from pathlib import Path
from PySide6.QtCore import Qt,QEvent,QRectF,QTimer
from PySide6.QtGui import QPixmap,QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QPushButton

class WindowTitleBar(QWidget):
    def __init__(self,dialog,title='',on_close=None,actions=()):
        super().__init__(dialog)
        self.dialog=dialog;self.setObjectName('preysenseTitleBar');self.setFixedHeight(30)
        dialog.setProperty('preysenseShell',True)
        if not hasattr(dialog,'_preysense_border'):
            dialog._preysense_border=WindowBorder(dialog)
        dialog.setWindowFlags(dialog.windowFlags()|Qt.FramelessWindowHint|Qt.NoDropShadowWindowHint)
        layout=QHBoxLayout(self);layout.setContentsMargins(8,0,0,0);layout.setSpacing(0)
        icon=QLabel();icon.setFixedSize(16,16)
        from icon_assets import svg_icon_pixmap
        icon.setPixmap(svg_icon_pixmap(Path(__file__).resolve().parent/'assets/appicon.svg',16))
        layout.addWidget(icon);layout.addSpacing(6)
        self.brand=QLabel('PreySense');self.brand.setObjectName('windowBrand');layout.addWidget(self.brand)
        self.subtitle=QLabel(' • '+title if title else '');self.subtitle.setObjectName('windowSubtitle');layout.addWidget(self.subtitle)
        layout.addStretch()
        for action in actions:layout.addWidget(action)
        self.close_button=QPushButton('✕');self.close_button.setFixedSize(30,30)
        self.close_button.setObjectName('windowCloseButton');self.close_button.setAccessibleName('Close '+(title or 'PreySense'))
        self.close_button.clicked.connect(on_close or dialog.hide);layout.addWidget(self.close_button)
        QTimer.singleShot(0,self.finish_window_margin)
    def finish_window_margin(self):
        from shiboken6 import isValid
        if not isValid(self) or not isValid(self.dialog):return
        layout=self.dialog.layout()
        if layout is None:return
        margins=layout.contentsMargins()
        # MainWindow uses its explicit content footer margin already. Dialogs
        # have zero outer padding, so reserve a consistent extra12px below them.
        if self.dialog.inherits('QMainWindow'):return
        if not self.dialog.property('bottomMarginApplied'):
            layout.setContentsMargins(margins.left(),margins.top(),margins.right(),margins.bottom()+12)
            self.dialog.setProperty('bottomMarginApplied',True)
            layout.invalidate();layout.activate()
            # Fixed-height settings/lighting recompute from their root hint.
            if self.dialog.minimumHeight()==self.dialog.maximumHeight():
                self.dialog.setFixedHeight(layout.sizeHint().height())
            else:self.dialog.adjustSize()

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            handle=self.dialog.windowHandle()
            if handle:handle.startSystemMove()
        super().mousePressEvent(event)


class WindowBorder(QWidget):
    """Paint above child content so the shell border remains continuous."""
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setStyleSheet('background:transparent;border:none;')
        owner.installEventFilter(self)
        self.setGeometry(owner.rect());self.show();self.raise_()
    def eventFilter(self,obj,event):
        if event.type() in (QEvent.Resize,QEvent.Show):
            self.setGeometry(self.owner.rect());self.raise_()
            if event.type()==QEvent.Show:QTimer.singleShot(0,self.raise_)
        return False
    def paintEvent(self,event):
        from appearance import color
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(color('BorderMainColor','#373737')),1));painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),7.5,7.5)
