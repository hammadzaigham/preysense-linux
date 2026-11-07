"""Native equivalents of the original WPF color wheel and locked-temperature fan graph."""
import colorsys
import math
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget
from fan_curve import TEMPERATURES
from appearance import color


class ColorWheel(QWidget):
    changed = Signal(QColor)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150); self.color = QColor('#28d8ca'); self.cache = None; self.cache_ratio = 0
        self.setCursor(Qt.PointingHandCursor); self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Color wheel'); self.setAccessibleDescription('Hue and saturation; arrow keys change color')
    def wheel_geometry(self):
        return QPointF(self.width() / 2, self.height() / 2), min(self.width(), self.height()) / 2 - 6
    def _image(self):
        ratio = self.devicePixelRatioF()
        if self.cache is not None and self.cache_ratio == ratio: return self.cache
        width, height = round(self.width() * ratio), round(self.height() * ratio)
        image = QImage(width, height, QImage.Format_ARGB32); image.fill(Qt.transparent)
        center, radius = self.wheel_geometry()
        for y in range(height):
            for x in range(width):
                dx, dy = x / ratio - center.x(), y / ratio - center.y()
                distance = math.hypot(dx, dy)
                if distance <= radius:
                    rgb = colorsys.hsv_to_rgb((math.atan2(dy, dx) / (2 * math.pi)) % 1, min(1, distance / radius), 1)
                    sample = QColor(*(round(v * 255) for v in rgb))
                    sample.setAlpha(round(min(1, (radius - distance) / 1.5) * 255)); image.setPixelColor(x, y, sample)
        image.setDevicePixelRatio(ratio); self.cache, self.cache_ratio = image, ratio
        return image
    def paintEvent(self, event):
        center, radius = self.wheel_geometry()
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing); painter.drawImage(0, 0, self._image())
        border = QColor(color('TextSecondaryColor', '#a8a8a8')); border.setAlpha(120)
        painter.setPen(QPen(border, 1.5)); painter.setBrush(Qt.NoBrush); painter.drawEllipse(center, radius, radius)
        hue, saturation, _, _ = self.color.getHsvF(); angle = max(hue, 0) * 2 * math.pi
        point = QPointF(center.x() + math.cos(angle) * saturation * radius, center.y() + math.sin(angle) * saturation * radius)
        painter.setPen(QPen(Qt.black, 2.5)); painter.setBrush(self.color); painter.drawEllipse(point, 7, 7)
        painter.setPen(QPen(Qt.white, 1.5)); painter.setBrush(Qt.NoBrush); painter.drawEllipse(point, 7, 7)
        if self.hasFocus():
            painter.setPen(QPen(QColor('#3aaeef'), 1, Qt.DotLine)); painter.drawEllipse(center, radius + 3, radius + 3)
    def pick(self, event):
        center, radius = self.wheel_geometry()
        dx, dy = event.position().x() - center.x(), event.position().y() - center.y()
        selected = QColor.fromHsvF((math.atan2(dy, dx) / (2 * math.pi)) % 1, min(1, math.hypot(dx, dy) / radius), 1)
        self.color = selected; self.update(); self.changed.emit(selected)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.setFocus(); self.pick(event)
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton: self.pick(event)
    def keyPressEvent(self, event):
        hue, saturation, _, _ = self.color.getHsvF(); hue = max(0, hue)
        if event.key() == Qt.Key_Left: hue = (hue - 1 / 360) % 1
        elif event.key() == Qt.Key_Right: hue = (hue + 1 / 360) % 1
        elif event.key() == Qt.Key_Up: saturation = min(1, saturation + .01)
        elif event.key() == Qt.Key_Down: saturation = max(0, saturation - .01)
        else: super().keyPressEvent(event); return
        self.color = QColor.fromHsvF(hue, saturation, 1); self.update(); self.changed.emit(self.color)


class FanGraph(QWidget):
    changed = Signal(int, int)
    selected = Signal(int)
    def __init__(self, spins, parent=None):
        super().__init__(parent)
        self.spins = spins; self.index = 0; self.dragging = False; self.origin = None; self.start_duty = 0
        self.setMinimumSize(440, 260); self.setFocusPolicy(Qt.StrongFocus); self.setMouseTracking(True)
        self.setAccessibleName('Fan curve'); self.setAccessibleDescription('Drag a point vertically; temperature positions are locked')
        for spin in spins: spin.valueChanged.connect(self.update)
    def plot(self): return self.rect().adjusted(40, 16, -16, -32)
    def point(self, index, value):
        rect = self.plot()
        return QPointF(rect.left() + (TEMPERATURES[index] - 40) / 60 * rect.width(), rect.bottom() - value / 100 * rect.height())
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing); rect = self.plot()
        grid = QColor(color('BorderSecondColor', '#2a2a2a')); text = QColor(color('TextSecondaryColor', '#a8a8a8'))
        label_font = painter.font(); label_font.setPixelSize(10); painter.setFont(label_font)
        for value in range(0, 101, 10):
            y = rect.bottom() - value / 100 * rect.height(); painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y)); painter.setPen(text)
            painter.drawText(QRectF(0, y - 7, 33, 14), Qt.AlignRight | Qt.AlignVCenter, f'{value}%')
        for temperature in range(40, 101, 5):
            x = rect.left() + (temperature - 40) / 60 * rect.width(); painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom())); painter.setPen(text)
            painter.drawText(QRectF(x - 16, rect.bottom() + 7, 32, 16), Qt.AlignCenter, f'{temperature}°')
        if len(self.spins) != len(TEMPERATURES): return
        points = [self.point(index, spin.value()) for index, spin in enumerate(self.spins) if TEMPERATURES[index]>=40]
        path = QPainterPath(points[0])
        for point in points[1:]: path.lineTo(point)
        accent = QColor('#3aaeef'); painter.setPen(QPen(accent, 2)); painter.drawPath(path)
        for index, point in enumerate(points,start=1):
            painter.setBrush(accent if index == self.index else QColor(color('CardBgColor', '#1c1c1c')))
            radius = 5 if index == self.index else 3; painter.drawEllipse(point, radius, radius)
    def hit_point(self, position):
        candidates = [(math.hypot(self.point(i, spin.value()).x() - position.x(), self.point(i, spin.value()).y() - position.y()), i)
                      for i, spin in enumerate(self.spins) if TEMPERATURES[i]>=40]
        distance, index = min(candidates) if candidates else (13, -1)
        return index if distance <= 12 else -1
    def set_duty(self, value):
        low = self.spins[self.index - 1].value() if self.index else 0
        high = self.spins[self.index + 1].value() if self.index + 1 < len(self.spins) else 100
        value = min(high, max(low, round(value))); old = self.spins[self.index].value()
        self.spins[self.index].setValue(value)
        if value != old: self.changed.emit(self.index, value)
        self.update()
    def change(self, event):
        if self.origin is None: return
        difference = self.origin.y() - event.position().y()
        if not self.dragging and abs(difference) < QApplication.startDragDistance(): return
        self.dragging = True; self.set_duty(self.start_duty + difference / self.plot().height() * 100)
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton: return
        index = self.hit_point(event.position())
        if index < 0: return
        self.index = index; self.origin = event.position(); self.start_duty = self.spins[index].value()
        self.dragging = False; self.setFocus(); self.selected.emit(index); self.update()
    def mouseMoveEvent(self, event):
        if self.origin is not None: self.change(event)
        else: self.setCursor(Qt.SizeVerCursor if self.hit_point(event.position()) >= 0 else Qt.ArrowCursor)
    def mouseReleaseEvent(self, event):
        if self.origin is not None: self.change(event)
        self.origin = None; self.dragging = False
    def keyPressEvent(self, event):
        if not self.spins: return
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            self.index = max(1, min(len(self.spins) - 1, self.index + (-1 if event.key() == Qt.Key_Left else 1)))
            self.selected.emit(self.index); self.update()
        elif event.key() in (Qt.Key_Up, Qt.Key_Down):
            if self.index<1:return
            self.set_duty(self.spins[self.index].value() + (1 if event.key() == Qt.Key_Up else -1))
        else: super().keyPressEvent(event)
