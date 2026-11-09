"""Native equivalents of the original WPF color wheel and stage-based fan graph."""
import colorsys
import math
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget
from fan_curve import GRAPH_MIN_C, GRAPH_MAX_C, duty_bounds, temperature_bounds
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
        ratio = max(1, int(self.devicePixelRatioF())); size = 150 * ratio
        if self.cache is not None and self.cache_ratio == ratio: return self.cache
        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied); image.fill(0); image.setDevicePixelRatio(ratio)
        center, radius = QPointF(size / 2, size / 2), size / 2 - 6 * ratio
        for y in range(size):
            for x in range(size):
                dx, dy = x - center.x(), y - center.y(); distance = math.hypot(dx, dy)
                if distance > radius: continue
                hue = (math.degrees(math.atan2(dy, dx)) + 360) % 360 / 360
                saturation = distance / radius
                r, g, b = colorsys.hsv_to_rgb(hue, saturation, 1)
                image.setPixel(x, y, QColor.fromRgbF(r, g, b).rgb())
        self.cache, self.cache_ratio = image, ratio; return image
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing); painter.drawImage(0, 0, self._image())
        center, radius = self.wheel_geometry(); hue, saturation = self.color.hsvHueF(), self.color.hsvSaturationF()
        if hue < 0: hue = 0
        angle = math.radians(hue * 360); marker = QPointF(center.x() + math.cos(angle) * saturation * radius, center.y() + math.sin(angle) * saturation * radius)
        painter.setPen(QPen(Qt.white, 2)); painter.setBrush(self.color); painter.drawEllipse(marker, 6, 6)
    def set_from_position(self, position):
        center, radius = self.wheel_geometry(); dx, dy = position.x() - center.x(), position.y() - center.y()
        distance = math.hypot(dx, dy)
        if distance < 1: self.color = QColor.fromHsvF(self.color.hsvHueF() if self.color.hsvHueF() >= 0 else 0, 0, 1)
        else:
            hue = (math.degrees(math.atan2(dy, dx)) + 360) % 360 / 360
            self.color = QColor.fromHsvF(hue, min(1, distance / radius), 1)
        self.update(); self.changed.emit(self.color)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.set_from_position(event.position())
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton: self.set_from_position(event.position())
    def keyPressEvent(self, event):
        hue = self.color.hsvHueF(); saturation = self.color.hsvSaturationF()
        if hue < 0: hue = 0
        if event.key() == Qt.Key_Left: hue = (hue - .01) % 1
        elif event.key() == Qt.Key_Right: hue = (hue + .01) % 1
        elif event.key() == Qt.Key_Up: saturation = min(1, saturation + .01)
        elif event.key() == Qt.Key_Down: saturation = max(0, saturation - .01)
        else: super().keyPressEvent(event); return
        self.color = QColor.fromHsvF(hue, saturation, 1); self.update(); self.changed.emit(self.color)


class FanGraph(QWidget):
    """Editable EC stage graph matching WpfFanCurveControl (X = entry °C, Y = duty %)."""
    changed = Signal()
    selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.temperatures = []
        self.values = []
        self.lead_in_duty = 0
        self.index = -1
        self.dragging = False
        self.origin = None
        self.start_duty = 0
        self.start_celsius = 0
        self.setMinimumSize(440, 260)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName('Fan curve')
        self.setAccessibleDescription('Drag a stage point; temperatures and duties stay unique and nondecreasing')

    def set_curve(self, temperatures, values, lead_in_duty=0):
        self.temperatures = [int(t) for t in temperatures]
        self.values = [int(v) for v in values]
        self.lead_in_duty = int(lead_in_duty)
        if self.index >= len(self.values):
            self.index = len(self.values) - 1 if self.values else -1
        self.update()

    def plot(self):
        return self.rect().adjusted(42, 14, -16, -28)

    def celsius_to_x(self, celsius):
        rect = self.plot()
        t = max(GRAPH_MIN_C, min(GRAPH_MAX_C, float(celsius)))
        return rect.left() + rect.width() * (t - GRAPH_MIN_C) / (GRAPH_MAX_C - GRAPH_MIN_C)

    def point(self, index, duty=None):
        rect = self.plot()
        celsius = self.temperatures[index] if index < len(self.temperatures) else GRAPH_MIN_C
        value = self.values[index] if duty is None else duty
        return QPointF(self.celsius_to_x(celsius), rect.bottom() - max(0, min(100, value)) / 100 * rect.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.plot()
        grid = QColor(color('BorderSecondColor', '#2a2a2a'))
        text = QColor(color('TextSecondaryColor', '#a8a8a8'))
        label_font = painter.font()
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        for value in range(0, 101, 20):
            y = rect.bottom() - value / 100 * rect.height()
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(text)
            painter.drawText(QRectF(0, y - 7, 36, 14), Qt.AlignRight | Qt.AlignVCenter, f'{value}%')
        for celsius in self.temperatures:
            x = self.celsius_to_x(celsius)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.setPen(text)
            painter.drawText(QRectF(x - 14, rect.bottom() + 4, 28, 16), Qt.AlignCenter, f'{celsius}°')
        if not self.values:
            return
        accent = QColor('#3aaeef')
        painter.setPen(QPen(accent, 2))
        lead_y = rect.bottom() - max(0, min(100, self.lead_in_duty)) / 100 * rect.height()
        first = self.point(0)
        painter.drawLine(QPointF(rect.left(), lead_y), QPointF(first.x(), lead_y))
        if abs(lead_y - first.y()) > 0.5:
            painter.drawLine(QPointF(first.x(), lead_y), first)
        for i in range(1, len(self.values)):
            previous = self.point(i - 1)
            nxt = self.point(i)
            painter.drawLine(previous, QPointF(nxt.x(), previous.y()))
            if abs(previous.y() - nxt.y()) > 0.5:
                painter.drawLine(QPointF(nxt.x(), previous.y()), nxt)
        last = self.point(len(self.values) - 1)
        if last.x() < rect.right():
            painter.drawLine(last, QPointF(rect.right(), last.y()))
        for i in range(len(self.values)):
            point = self.point(i)
            painter.setBrush(accent if i == self.index else QColor(color('CardBgColor', '#1c1c1c')))
            radius = 5 if i == self.index else 3
            painter.drawEllipse(point, radius, radius)

    def hit_point(self, position):
        best, distance = -1, 12 * 12
        for i in range(len(self.values)):
            point = self.point(i)
            d = (point.x() - position.x()) ** 2 + (point.y() - position.y()) ** 2
            if d <= distance:
                best, distance = i, d
        return best

    def x_to_celsius(self, x):
        rect = self.plot()
        if rect.width() <= 0:
            return GRAPH_MIN_C
        t = (x - rect.left()) / rect.width()
        return int(round(GRAPH_MIN_C + max(0, min(1, t)) * (GRAPH_MAX_C - GRAPH_MIN_C)))

    def apply_edit(self, duty=None, celsius=None):
        if self.index < 0 or self.index >= len(self.values):
            return
        if duty is not None:
            low, high = duty_bounds(self.values, self.index)
            self.values[self.index] = max(low, min(high, int(round(duty))))
        if celsius is not None:
            low, high = temperature_bounds(self.temperatures, self.index)
            self.temperatures[self.index] = max(low, min(high, int(round(celsius))))
        self.changed.emit()
        self.update()

    def change(self, event):
        if self.origin is None or self.index < 0:
            return
        dx = event.position().x() - self.origin.x()
        dy = self.origin.y() - event.position().y()
        if not self.dragging and math.hypot(dx, dy) < QApplication.startDragDistance():
            return
        self.dragging = True
        duty = self.start_duty + dy / max(1, self.plot().height()) * 100
        celsius = self.x_to_celsius(self.origin.x() + dx) if abs(dx) > abs(dy) * 0.35 else None
        # Prefer vertical duty edits; allow horizontal temp when clearly horizontal.
        if abs(dx) > abs(dy) and abs(dx) > QApplication.startDragDistance():
            self.apply_edit(duty=self.start_duty + dy / max(1, self.plot().height()) * 100,
                            celsius=self.x_to_celsius(self.celsius_to_x(self.start_celsius) + dx))
        else:
            self.apply_edit(duty=duty)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        index = self.hit_point(event.position())
        if index < 0:
            return
        self.index = index
        self.origin = event.position()
        self.start_duty = self.values[index]
        self.start_celsius = self.temperatures[index]
        self.dragging = False
        self.setFocus()
        self.selected.emit(index)
        self.update()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.change(event)
        else:
            self.setCursor(Qt.SizeAllCursor if self.hit_point(event.position()) >= 0 else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            self.change(event)
        self.origin = None
        self.dragging = False

    def keyPressEvent(self, event):
        if not self.values:
            return
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            step = -1 if event.key() == Qt.Key_Left else 1
            self.index = max(0, min(len(self.values) - 1, (self.index if self.index >= 0 else 0) + step))
            self.selected.emit(self.index)
            self.update()
        elif event.key() in (Qt.Key_Up, Qt.Key_Down) and self.index >= 0:
            self.apply_edit(duty=self.values[self.index] + (1 if event.key() == Qt.Key_Up else -1))
        else:
            super().keyPressEvent(event)
