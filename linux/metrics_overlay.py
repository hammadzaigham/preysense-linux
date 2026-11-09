"""Compact native Qt overlay using the Windows CPU/GPU row design."""
import math
import time
from collections import deque
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, Signal, QTimer, QEvent
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QFontMetricsF, QCursor
from PySide6.QtWidgets import (
    QWidget, QApplication, QLabel, QVBoxLayout, QHBoxLayout,
    QComboBox, QDialog, QPushButton, QSlider, QFrame
)
from ui_controls import RectangularSwitch, SettingSwitchRow, SettingSliderRow, SettingDropdownRow

# Layout constants matching PreySense.Overlay/HardwareOverlay.cs (Base 96 DPI, BaseScale = 2.0)
BASE_SCALE = 2.0
BASE_FONT_SIZE = 9.0
BASE_RPM_FONT_SIZE = 6.0
BASE_LINE_HEIGHT = 15
BASE_LINE_SPACING = 1
BASE_PAD_X = 4
BASE_PAD_Y = 1
BASE_INNER_PAD_X = 3
BASE_INNER_PAD_Y = 0
BASE_SECTION_GAP = 1

# Color tokens matching PreySense.Overlay
OVERLAY_TOP_GLOW = QColor(255, 255, 255, 8)
OVERLAY_BOTTOM_GLOW = QColor(0, 0, 0, 20)
OVERLAY_BORDER_COLOR = QColor(255, 255, 255, 14)
OVERLAY_SEP_COLOR = QColor(255, 255, 255, 18)
CPU_GRAPH_COLOR = QColor(44, 124, 180)
GPU_GRAPH_COLOR = QColor(58, 170, 84)

def numeric(value, *, positive=False):
    """Accept measured numeric fields, including backend unit suffixes."""
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            value = value.strip().rstrip("%W°CMHz ")
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) and value >= 0 and (not positive or value > 0) else None


def metric_text(value, suffix="", digits=0, *, positive=False):
    value = numeric(value, positive=positive)
    return "—" if value is None else f"{value:.{digits}f}{suffix}"


def first_available(*values):
    return next((v for v in values if numeric(v) is not None), None)


# Windows-aligned choices minus FPS and GPU metrics that stay N/A without NVAPI.
CPU_CHOICES = ("None", "Usage", "Temperature", "Active Clock", "Effective Clock", "Voltage", "Power", "Memory", "Memory Speed", "Fan Speed")
GPU_CHOICES = ("None", "Usage", "Temperature", "Clock", "Power", "Power Limit", "Memory", "Memory Speed", "Fan Speed")
DEFAULT_COLUMNS = (
    ("Usage", "Usage"),
    ("Temperature", "Temperature"),
    ("Effective Clock", "Clock"),
    ("Power", "Power"),
    ("Memory", "Memory"),
    ("Memory Speed", "Memory Speed"),
)
DEFAULT_GRAPHS = (False, False, False, True, False, False)
LEGACY_CPU = {"P-Core": "Effective Clock", "E-Core": "None", "Max Core": "Usage", "P-Core Usage": "Usage", "E-Core Usage": "Usage"}
LEGACY_GPU = {
    "Voltage": "None",
    "Hotspot": "Temperature",
    "Memory Temperature": "None",
    "PerfCap Reason": "None",
}
WIDTHS = {
    "Usage": 22, "Temperature": 32,
    "Active Clock": 44, "Effective Clock": 44, "Clock": 44, "Voltage": 44, "Memory Speed": 44,
    "Power": 38, "Power Limit": 38, "Memory": 32, "Fan Speed": 50,
}
MAX_OVERLAY_SLOTS = 12


def _migrate_metric(metric, gpu=False):
    table = LEGACY_GPU if gpu else LEGACY_CPU
    metric = table.get(metric, metric)
    choices = GPU_CHOICES if gpu else CPU_CHOICES
    return metric if metric in choices else "None"


def metric_value(data, metric, gpu=False):
    """Only read semantically matching fields."""
    info = (data.get("gpu") or {}) if gpu else data
    fields = {
        "Usage": "usage" if gpu else "cpu_usage",
        "Temperature": "temperature" if gpu else "cpu_temp",
        "Power": "power" if gpu else "cpu_power_w",
        "Power Limit": "enforced_power_limit_w",
        "Clock": "clock",
        "Active Clock": "cpu_p_core_mhz",
        "Effective Clock": "cpu_p_core_mhz",
        "Voltage": "cpu_voltage_v",
        "Memory": "memory_used_gb" if gpu else "memory_used_gb",
        "Memory Speed": "memory_clock_mhz" if gpu else "memory_speed_mhz",
    }
    if metric == "Fan Speed":
        value = data.get("gpu_fan" if gpu else "cpu_fan")
    elif metric == "Voltage":
        if gpu:
            return None
        value = first_available(info.get("cpu_voltage_v"), data.get("cpu_voltage_v"))
    elif metric in ("Active Clock", "Effective Clock"):
        value = first_available(info.get("cpu_p_core_mhz"), data.get("cpu_p_core_mhz"), data.get("cpu_frequency_mhz"))
    else:
        value = info.get(fields.get(metric, ""))
    if gpu and metric == "Temperature":
        value = first_available(value, data.get("gpu_temp"))
    return numeric(value, positive=metric in (
        "Temperature", "Active Clock", "Effective Clock", "Clock", "Memory Speed", "Power Limit", "Voltage",
    ))


def graph_value(data, metric, gpu=False):
    """Windows TelemetryGraphValue: missing samples are zero, memory is MB."""
    value = metric_value(data, metric, gpu)
    if value is None: return 0.0
    return value * 1024 if metric == 'Memory' else value


def column_text(data, metric, gpu=False):
    if metric == "None": return ""
    value = metric_value(data, metric, gpu)
    if value is None: return "N/A"
    if metric == "Fan Speed":value=math.floor(value/100+.5)*100
    units = {
        "Usage": "%", "Temperature": "°C",
        "Active Clock": "MHz", "Effective Clock": "MHz", "Clock": "MHz", "Voltage": "V",
        "Power": "W", "Power Limit": "W", "Memory": "GB", "Memory Speed": "MHz", "Fan Speed": "RPM",
    }
    digits = 3 if metric == "Voltage" else (1 if metric in ("Power", "Power Limit", "Memory") else 0)
    return metric_text(value, units.get(metric, ""), digits)


class OverlaySeparator(QFrame):
    """One flat line using the current theme, without a native raised border."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(1)
    def paintEvent(self,event):
        from appearance import color
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor(color('BorderSecondColor','#2A2A2A')))


class HardwareOverlay(QWidget):
    """Read-only telemetry HUD; unavailable measurements remain unavailable."""
    metrics_changed = Signal(dict)
    def __init__(self, settings, parent=None):
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint |
                         Qt.WindowDoesNotAcceptFocus | Qt.BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.owner = parent
        self._last_metrics_request = None
        application=QApplication.instance()
        if application:application.aboutToQuit.connect(self.close)
        if parent is not None:parent.destroyed.connect(self.close)
        self._target_screen = None
        self._geometry_dirty = True
        self._screen_signature = None
        self._text_widths = {}
        self.settings = settings
        self.data = {}
        self.scale_percent = int(settings.value("hud_scale", 100))
        self.bg_alpha = int(settings.value("hud_background", 50))
        self.text_alpha = int(settings.value("hud_text", 100))
        self.h_pos = settings.value("hud_h_pos", "Left")
        self.v_pos = settings.value("hud_v_pos", "Top")
        self.position = settings.value("hud_position", "Top left")
        self.corner_radius = int(settings.value("hud_corner_radius", settings.value("overlay_corner_radius", 6)))
        self.drag_start = None
        self.columns = []
        self.column_graphs = []
        self.metric_history = {}
        slot_count = int(settings.value("overlay_slot_count", len(DEFAULT_COLUMNS)))
        slot_count = max(0, min(MAX_OVERLAY_SLOTS, slot_count))
        if slot_count == 0 and settings.contains("overlay_col_1"):
            slot_count = len(DEFAULT_COLUMNS)
        for i in range(slot_count or len(DEFAULT_COLUMNS)):
            default = DEFAULT_COLUMNS[i] if i < len(DEFAULT_COLUMNS) else ("None", "None")
            stored = str(settings.value(f"overlay_col_{i+1}", "|".join(default))).split("|")
            if len(stored) != 2:
                stored = list(default)
            cpu = _migrate_metric(stored[0], False)
            gpu = _migrate_metric(stored[1], True)
            if (cpu, gpu) != tuple(stored):
                settings.setValue(f"overlay_col_{i+1}", f"{cpu}|{gpu}")
            self.columns.append((cpu, gpu))
            default_graph = DEFAULT_GRAPHS[i] if i < len(DEFAULT_GRAPHS) else False
            self.column_graphs.append(settings.value(f"overlay_col_{i+1}_graph", default_graph, type=bool))
        self.settings.setValue("overlay_slot_count", len(self.columns))

        # 60 samples history matching C# deque
        self.history_len = 60
        self.sync_graph_metrics()
        self.cpu_usage_history = deque([0.0]*self.history_len, maxlen=self.history_len)
        self.gpu_usage_history = deque([0.0]*self.history_len, maxlen=self.history_len)

        self.cpu_history_valid = deque([False]*self.history_len, maxlen=self.history_len)
        self.gpu_history_valid = deque([False]*self.history_len, maxlen=self.history_len)
        self.recalculate_size()
        self.reposition()

    def configure(self, key, value):
        if key == "scale":
            self.scale_percent = max(50, min(200, int(value)))
            self.settings.setValue("hud_scale", self.scale_percent)
            self.recalculate_size()
            self.reposition()
        elif key == "background":
            self.bg_alpha = max(0, min(100, int(value)))
            self.settings.setValue("hud_background", self.bg_alpha)
        elif key == "alpha":
            self.text_alpha = max(0, min(100, int(value)))
            self.settings.setValue("hud_text", self.text_alpha)
        elif key == "h_pos":
            self.h_pos = str(value)
            self.settings.setValue("hud_h_pos", self.h_pos)
            self.reposition()
        elif key == "v_pos":
            self.v_pos = str(value)
            self.settings.setValue("hud_v_pos", self.v_pos)
            self.reposition()
        elif key == "position":
            self.position = str(value)
            self.settings.setValue("hud_position", self.position)
            if "Top" in self.position: self.v_pos = "Top"
            elif "Bottom" in self.position: self.v_pos = "Bottom"
            if "left" in self.position.lower(): self.h_pos = "Left"
            elif "right" in self.position.lower(): self.h_pos = "Right"
            self.reposition()
        elif key in ("corner_radius", "radius"):
            self.corner_radius = max(0, min(32, int(value)))
            self.settings.setValue("hud_corner_radius", self.corner_radius)
        self.update()

    def _measure_layout(self, sc):
        font=QFont("DejaVu Sans")
        font.setPixelSize(max(5, round(BASE_FONT_SIZE*sc)))
        font.setWeight(QFont.DemiBold)
        font.setStretch(85)
        fm=QFontMetricsF(font)
        pad_x=max(2,math.ceil((BASE_PAD_X+BASE_INNER_PAD_X)*sc))
        pad=max(1,math.ceil(BASE_PAD_Y*sc))
        inset=max(0, math.ceil(BASE_INNER_PAD_Y*sc))
        line=max(math.ceil(BASE_LINE_HEIGHT*sc), math.ceil(fm.height()))
        gap=max(1, math.ceil(sc))
        label=math.ceil(max(fm.horizontalAdvance(v) for v in ('CPU','GPU')))+math.ceil(1*sc)
        samples={'Usage':'100%', 'Temperature':'100°C',
                 'Active Clock':'6000MHz','Effective Clock':'6000MHz','Clock':'6000MHz','Voltage':'1.250V',
                 'Power':'250.0W','Power Limit':'250.0W',
                 'Memory':'32.0GB','Memory Speed':'12000MHz','Fan Speed':'10000RPM'}
        columns=[]
        for i,pair in enumerate(self.columns):
            if pair==('None','None'):columns.append((0,0));continue
            texts=['N/A']+[samples[m] for m in pair if m in samples]
            texts += [column_text(self.data,m,bool(row)) for row,m in enumerate(pair)]
            width=math.ceil(max(fm.horizontalAdvance(v) for v in texts))+math.ceil(6*sc)
            graph=math.ceil(74*sc) if self.column_graphs[i] else 0
            columns.append((width,graph))
        width=2*pad_x+label+sum(w+g for w,g in columns)
        height=2*pad+2*inset+2*line+gap
        return dict(font=font,pad=pad,pad_x=pad_x,inset=inset,line=line,gap=gap,label=label,columns=columns,width=width,height=height,scale=sc)

    def recalculate_size(self):
        requested=BASE_SCALE*(self.scale_percent/100)
        layout=self._measure_layout(requested)
        screen=self.get_current_screen()
        if screen:
            geo=screen.availableGeometry()
            # Requested zoom remains saved; fit oversized layouts on this screen.
            for _ in range(16):
                ratio=min(1,(geo.width()-24)/layout['width'],(geo.height()-24)/layout['height'])
                if ratio>=.999:break
                layout=self._measure_layout(layout['scale']*max(.05,ratio*.98))
        self._layout=layout
        self._font_metrics=QFontMetricsF(layout['font'])
        self._text_widths={}
        self._screen_signature=self._screen_key()
        self._geometry_dirty=False
        self.setFixedSize(max(1,layout['width']),max(1,layout['height']))

    def _screen_key(self):
        screen=self.get_current_screen()
        if screen is None:return None
        geo=screen.availableGeometry()
        return (screen.name() if hasattr(screen,'name') else None,geo.x(),geo.y(),geo.width(),geo.height(),
                screen.logicalDotsPerInch() if hasattr(screen,'logicalDotsPerInch') else None)

    def _ensure_geometry(self):
        """Keep common updates measurement-free; grow only when a value needs it."""
        changed=self._geometry_dirty or self._screen_key()!=self._screen_signature
        if not changed:
            padding=math.ceil(6*self._layout['scale'])
            for index,pair in enumerate(self.columns):
                available=self._layout['columns'][index][0]-padding
                for row,metric in enumerate(pair):
                    if metric=='None':continue
                    text=column_text(self.data,metric,bool(row))
                    # Bound this tiny cache without retaining every changing value.
                    if text not in self._text_widths:
                        if len(self._text_widths)>=512:self._text_widths.clear()
                        self._text_widths[text]=self._font_metrics.horizontalAdvance(text)
                    if math.ceil(self._text_widths[text])>available:
                        changed=True;break
                if changed:break
        if changed:self.recalculate_size();self.reposition()

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange,QEvent.ApplicationFontChange,QEvent.StyleChange):
            self._geometry_dirty=True
            if self.isVisible():self._ensure_geometry()

    def column_width(self, index):
        return max(WIDTHS.get(metric, 0) for metric in self.columns[index])

    def requested_metrics(self):
        """Union of selected CPU and GPU metrics across visible overlay columns."""
        visible=self.isVisible() and not self.isMinimized()
        if not visible:return {"cpu":[],"gpu":[],"visible":False}
        cpu = set()
        gpu = set()
        for c, g in self.columns:
            if c != "None":
                cpu.add(c)
            if g != "None":
                gpu.add(g)
        return {"cpu": sorted(cpu), "gpu": sorted(gpu), "visible": visible}

    def set_column(self, index, cpu, gpu, graph=None):
        if not 0 <= index < MAX_OVERLAY_SLOTS or cpu not in CPU_CHOICES or gpu not in GPU_CHOICES:
            raise ValueError("Invalid overlay column")
        while len(self.columns) <= index:
            self.columns.append(("None", "None"))
            self.column_graphs.append(False)
        self.columns[index] = (cpu, gpu)
        self.settings.setValue(f"overlay_col_{index+1}", f"{cpu}|{gpu}")
        if graph is not None:
            self.column_graphs[index] = bool(graph)
            self.settings.setValue(f"overlay_col_{index+1}_graph", bool(graph))
        self.sync_graph_metrics()
        self.recalculate_size()
        self.reposition()
        self._notify_metrics_demand()
        self.update()

    def add_slot(self, cpu="None", gpu="None", graph=False):
        if len(self.columns) >= MAX_OVERLAY_SLOTS:
            return False
        self.columns.append((_migrate_metric(cpu), _migrate_metric(gpu, True)))
        self.column_graphs.append(bool(graph))
        index = len(self.columns) - 1
        self.settings.setValue(f"overlay_col_{index+1}", f"{self.columns[index][0]}|{self.columns[index][1]}")
        self.settings.setValue(f"overlay_col_{index+1}_graph", bool(graph))
        self.settings.setValue("overlay_slot_count", len(self.columns))
        self.sync_graph_metrics()
        self.recalculate_size()
        self.reposition()
        self._notify_metrics_demand()
        self.update()
        return True

    def remove_slot(self, index):
        if not 0 <= index < len(self.columns):
            return False
        self.columns.pop(index)
        self.column_graphs.pop(index)
        for i, pair in enumerate(self.columns):
            self.settings.setValue(f"overlay_col_{i+1}", f"{pair[0]}|{pair[1]}")
            self.settings.setValue(f"overlay_col_{i+1}_graph", self.column_graphs[i])
        for i in range(len(self.columns), MAX_OVERLAY_SLOTS):
            self.settings.remove(f"overlay_col_{i+1}")
            self.settings.remove(f"overlay_col_{i+1}_graph")
        self.settings.setValue("overlay_slot_count", len(self.columns))
        self.sync_graph_metrics()
        self.recalculate_size()
        self.reposition()
        self._notify_metrics_demand()
        self.update()
        return True

    def setVisible(self, visible):
        super().setVisible(visible)
        self._notify_metrics_demand()

    def _notify_metrics_demand(self):
        """Report actual visibility, including native hide/close/minimize events."""
        if not hasattr(self,'columns'):return
        request=self.requested_metrics()
        signature=(request['visible'],tuple(request['cpu']),tuple(request['gpu']))
        if signature!=self._last_metrics_request:
            self._last_metrics_request=signature
            self.metrics_changed.emit(request)

    def hideEvent(self,event):
        super().hideEvent(event)
        self._notify_metrics_demand()

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.WindowStateChange:self._notify_metrics_demand()

    def sync_graph_metrics(self):
        selected={(bool(row),metric) for pair,enabled in zip(self.columns,self.column_graphs)
                  if enabled for row,metric in enumerate(pair) if metric != "None"}
        # Newly enabled graph metrics start with a clean Windows-sized history.
        self.metric_history={key:self.metric_history.get(key,deque([0.0]*60,maxlen=60))
                             for key in selected}

    def get_current_screen(self):
        if self._target_screen in QApplication.screens():return self._target_screen
        if self.owner is not None:
            screen=self.owner.screen()
            if screen:return screen
        return QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()

    def showEvent(self,event):
        super().showEvent(event)
        self._notify_metrics_demand()
        self._ensure_geometry()
        self.reposition()
        QTimer.singleShot(0,self.reposition)

    def reposition(self):
        screen = self.get_current_screen()
        if not screen: return
        geo = screen.availableGeometry()
        margin = 12

        h = self.h_pos.strip().capitalize()
        v = self.v_pos.strip().capitalize()

        if h == "Left":
            x = geo.left() + margin
        elif h == "Center":
            x = geo.left() + (geo.width() - self.width()) // 2
        else:
            x = geo.left() + geo.width() - self.width() - margin

        if v == "Top":
            y = geo.top() + margin
        elif v == "Center":
            y = geo.top() + (geo.height() - self.height()) // 2
        else:
            y = geo.top() + geo.height() - self.height() - margin

        min_x = geo.left() + 5
        max_x = max(min_x, geo.left() + geo.width() - self.width() - 5)
        min_y = geo.top() + 5
        max_y = max(min_y, geo.top() + geo.height() - self.height() - 5)

        self.move(max(min_x, min(x, max_x)), max(min_y, min(y, max_y)))

    def update_data(self, data):
        self.data = data
        if not self.isVisible() or self.isMinimized():return
        if self.isVisible():
            self._ensure_geometry()
            for (gpu,metric),history in self.metric_history.items():
                history.append(graph_value(data,metric,gpu))
        cpu_u = numeric(data.get("cpu_usage"))
        gpu_u = numeric(first_available((data.get("gpu") or {}).get("usage"), data.get("gpu_usage")))
        for value, history, valid in ((cpu_u, self.cpu_usage_history, self.cpu_history_valid),
                                      (gpu_u, self.gpu_usage_history, self.gpu_history_valid)):
            usable = value is not None and value <= 100
            history.append(value if usable else 0.0)
            valid.append(usable)
        self.update()

    def background_color(self, color):
        result = QColor(color)
        result.setAlpha(round(result.alpha() * self.bg_alpha / 100))
        return result

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        layout=self._layout
        sc = layout["scale"]
        w, h = self.width(), self.height()

        # 1. Background fill and rounded shell matching Windows
        alpha = int(255 * (self.bg_alpha / 100.0))
        radius = float(self.corner_radius) * (sc / 2.0)
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.fillPath(path, QColor(0, 0, 0, alpha))

        # 2. Glowing Borders matching HardwareOverlay.cs clipped to rounded path
        p.save()
        p.setClipPath(path)
        p.fillRect(0, 0, w, int(1 * sc), self.background_color(OVERLAY_TOP_GLOW))
        p.fillRect(0, h - int(1 * sc), w, int(1 * sc), self.background_color(OVERLAY_BOTTOM_GLOW))
        p.restore()
        p.setPen(QPen(self.background_color(OVERLAY_BORDER_COLOR), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # Typography
        text_a = int(255 * (self.text_alpha / 100.0))
        font_main = layout['font']
        pad_x=layout['pad_x'];pad_y=layout['pad']
        line_h=layout['line']
        cur_x=pad_x

        # Windows column order and widths from HardwareOverlay.Layout.cs.
        p.setPen(QColor(255, 255, 255, text_a))
        p.setFont(font_main)
        top = pad_y + layout["inset"]
        label_w = layout["label"]
        for row, label in enumerate(("CPU", "GPU")):
            p.drawText(QRectF(cur_x, top + row*(line_h + layout["gap"]), label_w, line_h), Qt.AlignLeft | Qt.AlignVCenter, label)
        cur_x += label_w
        for i, pair in enumerate(self.columns):
            width = layout["columns"][i][0]
            if not width: continue
            p.setPen(QColor(255, 255, 255, text_a))
            for row, metric in enumerate(pair):
                p.drawText(QRectF(cur_x, top + row*(line_h + layout["gap"]), width, line_h), Qt.AlignRight | Qt.AlignVCenter, column_text(self.data, metric, bool(row)))
            cur_x += width
            if self.column_graphs[i]:
                gx = cur_x + int(6*sc)
                gw = int(72*sc)
                gh = max(1, line_h+layout["gap"]+round(9*sc))
                gy = top + (2*line_h+layout["gap"]-gh)/2
                histories = [self.metric_history.get((bool(row), metric), [0.0]*60) for row, metric in enumerate(pair)]
                peak = max([10.0] + [v for history,metric in zip(histories,pair) if metric != "None" for v in history])
                p.save();p.setClipRect(QRectF(gx,gy,gw,gh))
                for row,color,fill_alpha in ((1,GPU_GRAPH_COLOR,34),(0,CPU_GRAPH_COLOR,24)):
                    if pair[row] != "None":
                        scaled = [v/peak*100 for v in histories[row]]
                        self.draw_mini_graph(p,gx,gy,gw,gh,scaled,color,fill_alpha=fill_alpha)
                p.restore()
                axis=QColor(60,60,60,round(255*self.text_alpha/100))
                p.setPen(QPen(axis,sc*.5));p.drawLine(QPointF(gx,gy+gh),QPointF(gx+gw,gy+gh))
                cur_x += layout["columns"][i][1]

    def draw_mini_graph(self, p, x, y, w, h, history, color, valid=None, fill_alpha=24):
        """Windows area chart: no glow, fixed-width line, shared external scale."""
        if len(history) < 2: return
        step = w / float(len(history) - 1)
        path=QPainterPath()
        for i,val in enumerate(history):
            px=x+i*step;py=y+h-max(0.0,min(100.0,float(val)))/100*h
            if i==0:path.moveTo(px,py)
            else:path.lineTo(px,py)
        area=QPainterPath(path);area.lineTo(x+w,y+h);area.lineTo(x,y+h);area.closeSubpath()
        fill=QColor(color);fill.setAlpha(round(fill_alpha*self.text_alpha/100))
        p.fillPath(area,fill)
        line=QColor(color);line.setAlpha(round(255*self.text_alpha/100))
        p.setPen(QPen(line,1.5));p.setBrush(Qt.NoBrush);p.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_start is not None:
            self.move(event.globalPosition().toPoint() - self.drag_start)

    def mouseReleaseEvent(self, event):
        self.drag_start = None
        # Save custom position relative to screen
        screen = QApplication.screenAt(self.geometry().center()) or self.get_current_screen()
        if screen:
            self._target_screen=screen
            geo = screen.availableGeometry()
            # If user dragged near edge, preserve edge affinity
            cx = self.x() + self.width() / 2
            cy = self.y() + self.height() / 2
            if cx < geo.left() + geo.width() / 3:
                self.h_pos = "Left"
            elif cx > geo.left() + (2 * geo.width()) / 3:
                self.h_pos = "Right"
            else:
                self.h_pos = "Center"
            if cy < geo.top() + geo.height() / 3:
                self.v_pos = "Top"
            elif cy > geo.top() + (2 * geo.height()) / 3:
                self.v_pos = "Bottom"
            else:
                self.v_pos = "Center"
            self.settings.setValue("hud_h_pos",self.h_pos)
            self.settings.setValue("hud_v_pos",self.v_pos)
            self.recalculate_size();self.reposition()


def _metric_label(metric, gpu=False):
    if metric == "None":
        return "None"
    labels = {
        "Fan Speed": "Fan",
        "Active Clock": "Active Clock",
        "Effective Clock": "Effective Clock",
        "Voltage": "VID",
        "Power Limit": "Power Limit",
    }
    return ("GPU " if gpu else "CPU ") + labels.get(metric, metric)


def controls(owner, layout):
    """Exact port of PreySense.Frontend/Views/MetricsWindow.xaml."""
    dialog=layout.parentWidget()
    if isinstance(dialog,QDialog):
        # A utility/settings window should not create a separate taskbar item.
        dialog.setWindowFlags((dialog.windowFlags() & ~Qt.WindowType_Mask) | Qt.Tool | Qt.FramelessWindowHint)
        dialog.setFixedWidth(540)
        from window_chrome import WindowTitleBar
        layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        layout.addWidget(WindowTitleBar(dialog,'Overlay'))
        content=QWidget(dialog)
        root=layout
        layout=QVBoxLayout(content)
        layout.setContentsMargins(14,10,14,8);layout.setSpacing(0)
        root.addWidget(content)
    owner.overlay.owner=owner
    owner.overlay.recalculate_size();owner.overlay.reposition()
    # 1. Enable Metrics Overlay (Rectangular Switch)
    row_enable = SettingSwitchRow("Enable Metrics Overlay", checked=owner.overlay_toggle.isChecked())
    row_enable.toggled.connect(owner.overlay_toggle.setChecked)
    def reflect_overlay(enabled):
        row_enable.switch.blockSignals(True);row_enable.setChecked(enabled);row_enable.switch.blockSignals(False)
    owner.overlay_toggle.toggled.connect(reflect_overlay)
    owner.overlay_enabled_row=row_enable
    layout.addWidget(row_enable)

    # Separator
    layout.addSpacing(4);sep1 = OverlaySeparator();layout.addWidget(sep1);layout.addSpacing(8)

    # 2. Sliders matching MetricsWindow.xaml
    slider_scale = SettingSliderRow("HUD Scale", 50, 200, owner.overlay.scale_percent, unit="%")
    __import__('slider_snap').configure_snap(slider_scale.slider,5)
    slider_scale.valueChanged.connect(lambda v: owner.overlay.configure("scale", v))
    layout.addWidget(slider_scale)

    slider_bg = SettingSliderRow("Background Opacity", 0, 100, owner.overlay.bg_alpha, unit="%")
    __import__('slider_snap').configure_snap(slider_bg.slider,10)
    slider_bg.valueChanged.connect(lambda v: owner.overlay.configure("background", v))
    layout.addWidget(slider_bg)

    slider_text = SettingSliderRow("Text Opacity", 0, 100, owner.overlay.text_alpha, unit="%")
    __import__('slider_snap').configure_snap(slider_text.slider,10)
    slider_text.valueChanged.connect(lambda v: owner.overlay.configure("alpha", v))
    layout.addWidget(slider_text)

    # Separator
    layout.addSpacing(4);sep2 = OverlaySeparator();layout.addWidget(sep2);layout.addSpacing(8)

    # 3. Position Dropdowns (Horizontal Position & Vertical Position)
    row_hpos = SettingDropdownRow("Horizontal Position", dropdown_width=110)
    row_hpos.addItems(["Left", "Center", "Right"])
    row_hpos.setCurrentText(owner.overlay.h_pos)
    row_hpos.currentTextChanged.connect(lambda v: owner.overlay.configure("h_pos", v))
    layout.addWidget(row_hpos)

    row_vpos = SettingDropdownRow("Vertical Position", dropdown_width=110)
    row_vpos.addItems(["Top", "Center", "Bottom"])
    row_vpos.setCurrentText(owner.overlay.v_pos)
    row_vpos.currentTextChanged.connect(lambda v: owner.overlay.configure("v_pos", v))
    layout.addWidget(row_vpos)

    layout.addSpacing(4);separator = OverlaySeparator()
    layout.addWidget(separator);layout.addSpacing(8)

    header = QWidget(); header_box = QHBoxLayout(header)
    header_box.setContentsMargins(0, 2, 0, 6); header_box.setSpacing(4)
    header_box.addWidget(QLabel("Overlay Metric Slots")); header_box.addStretch()
    add_btn = QPushButton("+ Add Slot"); add_btn.setFixedSize(88, 26)
    header_box.addWidget(add_btn)
    layout.addWidget(header)
    slots_host = QWidget(); slots_layout = QVBoxLayout(slots_host)
    slots_layout.setContentsMargins(0, 0, 0, 0); slots_layout.setSpacing(0)
    layout.addWidget(slots_host)
    empty = QLabel("No overlay slots configured. Click '+ Add Slot' to add metrics.")
    empty.setStyleSheet("font-style: italic; color: #888;")
    slots_layout.addWidget(empty)

    def rebuild_slots():
        while slots_layout.count():
            item = slots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        owner.overlay_slots = []
        if not owner.overlay.columns:
            note = QLabel("No overlay slots configured. Click '+ Add Slot' to add metrics.")
            note.setStyleSheet("font-style: italic; color: #888;")
            slots_layout.addWidget(note)
            dialog.adjustSize() if isinstance(dialog, QDialog) else None
            return
        for index, pair in enumerate(owner.overlay.columns):
            row = QWidget(); box = QHBoxLayout(row)
            box.setContentsMargins(0, 3, 0, 3); box.setSpacing(4)
            label = QLabel(f"Slot #{index+1}"); label.setFixedWidth(46); box.addWidget(label)
            combos = []
            for gpu, choices in ((False, CPU_CHOICES), (True, GPU_CHOICES)):
                combo = QComboBox(); combo.setFixedSize(168, 28)
                for metric in choices:
                    combo.addItem(_metric_label(metric, gpu), metric)
                combo.setCurrentIndex(max(0, choices.index(pair[int(gpu)])))
                box.addWidget(combo); combos.append(combo)
            graph = RectangularSwitch(); graph.setChecked(owner.overlay.column_graphs[index])
            box.addSpacing(4); box.addWidget(graph)
            remove = QPushButton("–"); remove.setFixedSize(28, 28); remove.setToolTip("Remove slot")
            box.addWidget(remove)
            def save_column(*_, i=index, c=combos, g=graph):
                owner.overlay.set_column(i, c[0].currentData(), c[1].currentData(), g.isChecked())
            def remove_column(*_, i=index):
                owner.overlay.remove_slot(i); rebuild_slots()
            for combo in combos: combo.currentIndexChanged.connect(save_column)
            graph.toggled.connect(save_column)
            remove.clicked.connect(remove_column)
            owner.overlay_slots.append((combos[0], combos[1], graph))
            slots_layout.addWidget(row)
        if isinstance(dialog, QDialog):
            dialog.adjustSize()

    def add_slot():
        if owner.overlay.add_slot():
            rebuild_slots()
    add_btn.clicked.connect(add_slot)
    rebuild_slots()


MetricsOverlay = HardwareOverlay
