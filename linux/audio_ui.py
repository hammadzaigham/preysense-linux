"""Compact UI base components for dialogs and switches."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)
from appearance import color

class AudioSwitch(QAbstractButton):
    """Checked-state pill using the original toggle geometry, with native Qt input."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True); self.setFixedSize(56, 28)
        self.setCursor(Qt.PointingHandCursor); self.setFocusPolicy(Qt.StrongFocus)
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled(): p.setOpacity(.45)
        p.setPen(QPen(QColor(color('BorderSecondColor', '#2a2a2a')), 1))
        p.setBrush(QColor(color('ButtonMainColor', '#2e2e2e')))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 13, 13)
        left = self.rect().adjusted(3, 3, -28, -3)
        right = self.rect().adjusted(28, 3, -3, -3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color('ControlActiveColor', '#3e4450') if self.isChecked()
                          else color('ButtonSecondColor', '#242424')))
        p.drawRoundedRect(right if self.isChecked() else left, 10, 10)
        p.setPen(QColor(color('TextMutedColor', '#787878') if self.isChecked()
                       else color('TextPrimaryColor', '#f0f0f0')))
        p.drawText(left, Qt.AlignCenter, '○')
        p.setPen(QColor(color('TextPrimaryColor', '#f0f0f0') if self.isChecked()
                       else color('TextMutedColor', '#787878')))
        p.drawText(right, Qt.AlignCenter, '│')
        if self.hasFocus():
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(color('ControlFocusedBorderColor', '#4e5564')), 1))
            p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 13, 13)

def button(text, callback=None):
    widget = QPushButton(text); widget.setFixedHeight(30)
    if callback is not None: widget.clicked.connect(callback)
    return widget

def row(layout, title, widget, *, bold=False):
    line = QHBoxLayout(); line.setContentsMargins(0,4,0,4);line.setSpacing(12)
    if isinstance(widget,QPushButton):widget.setFixedHeight(28)
    label = QLabel(title)
    if bold: label.setStyleSheet('font-weight:600;')
    line.addWidget(label); line.addStretch(); line.addWidget(widget)
    layout.addLayout(line)
    return label

class AudioDialog(QDialog):
    def __init__(self, parent, title, width):
        super().__init__(parent)
        self.setWindowTitle('PreySense • ' + title); self.setFixedWidth(width)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setWindowIcon(parent.windowIcon())
        self.root=QVBoxLayout(self);self.root.setContentsMargins(0,0,0,0);self.root.setSpacing(0)
        from window_chrome import WindowTitleBar
        self.header=WindowTitleBar(self,title)
        self.root.addWidget(self.header)
        content=QWidget(self);self.body=QVBoxLayout(content)
        self.body.setContentsMargins(14,10,14,8);self.body.setSpacing(8)
        self.root.addWidget(content)
    def add_footer(self,*buttons):
        panel=QWidget(self);footer=QHBoxLayout(panel)
        footer.setContentsMargins(14,10,14,16);footer.setSpacing(4)
        for control in buttons:control.setFixedHeight(34);footer.addWidget(control)
        self.root.addWidget(panel)
        return footer
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 30 and self.windowHandle():
            self.windowHandle().startSystemMove()
