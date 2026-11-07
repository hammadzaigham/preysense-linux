"""Confirmed performance-mode toast, ported from Views/ModeToastWindow."""
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontMetrics, QPixmap, QCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget, QApplication

MODE_NAMES = {0: 'Quiet', 1: 'Balanced', 4: 'Performance', 5: 'Turbo', 6: 'Eco'}
MODE_COLORS = {'Quiet': '#06B48A', 'Eco': '#06B48A', 'Balanced': '#3AAEEF',
               'Performance': '#9333EA', 'Turbo': '#FF2020'}


def toast_position(work_area, width, height, device_pixel_ratio):
    """Qt coordinates are logical; the Windows bottom offset is 72 physical px."""
    ratio = max(0.1, float(device_pixel_ratio))
    x=round(work_area.x()+(work_area.width()-width)/2)
    y=round(work_area.y()+work_area.height()-height-72/ratio)
    return (max(work_area.left(),min(x,work_area.x()+work_area.width()-width)),
            max(work_area.top(),min(y,work_area.y()+work_area.height()-height)))


class ModeToast(QWidget):
    """Caller must supply a confirmed mode, never a pending hardware request."""
    def __init__(self, owner=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput |
                         Qt.BypassWindowManagerHint)
        self.owner = owner
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(40)
        self.mode_name = 'Balanced'
        self._opacity = 1.0
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(1800)
        self.hide_timer.timeout.connect(self.fade_out)
        self._fading_out=False
        self.animation=QPropertyAnimation(self,b'toastOpacity',self)
        self.animation.finished.connect(self._animation_finished)
        self.label_font = QFont('Segoe UI')
        self.label_font.setPixelSize(14)
        self.label_font.setWeight(QFont.Medium)
        self._icon = QPixmap()

    def get_opacity(self):return self._opacity
    def set_opacity(self,value):
        self._opacity=max(0.0,min(1.0,float(value)));self.update()
    toastOpacity=Property(float,get_opacity,set_opacity)

    def show_mode(self, mode):
        name = MODE_NAMES.get(mode) if type(mode) is int else mode
        if not isinstance(name, str) or name not in MODE_COLORS:
            return False
        self.hide_timer.stop();self.animation.stop();self._fading_out=False
        self.mode_name = name

        screen = None
        if self.owner and hasattr(self.owner, 'screen'):
            screen = self.owner.screen()
        if not screen:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0

        asset = Path(__file__).parent / 'assets' / f'{name}.svg'
        renderer = QSvgRenderer(str(asset))
        phys_size = int(round(18 * dpr))
        pix = QPixmap(phys_size, phys_size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        renderer.render(p)
        p.end()
        pix.setDevicePixelRatio(dpr)
        self._icon = pix

        text_width = QFontMetrics(self.label_font).horizontalAdvance(name)
        self.setFixedWidth(max(160, min(220, 24+18+9+text_width)))
        if screen:
            x,y = toast_position(screen.availableGeometry(), self.width(), self.height(), screen.devicePixelRatio())
            self.move(x,y)
        self.set_opacity(0.0)
        self.show()
        if screen:self.move(*toast_position(screen.availableGeometry(),self.width(),self.height(),screen.devicePixelRatio()))
        self.animation.setDuration(150);self.animation.setStartValue(0.0);self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutQuad);self.animation.start()
        return True

    def fade_out(self):
        self.hide_timer.stop();self.animation.stop();self._fading_out=True
        self.animation.setDuration(250);self.animation.setStartValue(self._opacity);self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.InQuad);self.animation.start()

    def _animation_finished(self):
        if self._fading_out:self.hide()
        elif self.isVisible():self.hide_timer.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self._opacity)
        painter.setBrush(QColor('#E6181A20'))
        painter.setPen(QPen(QColor(MODE_COLORS[self.mode_name]), 1))
        painter.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),20,20)
        painter.setFont(self.label_font)
        painter.setPen(QColor('#F5F7FA'))
        text_width = QFontMetrics(self.label_font).horizontalAdvance(self.mode_name)
        x = (self.width()-18-9-text_width)/2
        painter.drawPixmap(round(x),11,18,18,self._icon)
        painter.drawText(QRectF(x+27,0,text_width+1,40),Qt.AlignVCenter|Qt.AlignLeft,self.mode_name)

    def closeEvent(self, event):
        self.hide_timer.stop();self.animation.stop()
        super().closeEvent(event)
