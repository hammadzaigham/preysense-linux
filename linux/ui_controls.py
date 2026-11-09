"""Custom Qt Widgets reproducing the Windows PreySense design tokens."""
from PySide6.QtCore import Qt, QPoint, QRect, QRectF, Signal, Property
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath
from PySide6.QtWidgets import QWidget, QAbstractButton, QSlider, QLabel, QHBoxLayout, QVBoxLayout

class RectangularSwitch(QAbstractButton):
    """Exact port of PreySense.Frontend.Controls.RectangularSwitch."""
    def __init__(self, parent=None, width=56, height=28, on_text="│", off_text="○"):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(width, height)
        self._on_text = on_text
        self._off_text = off_text
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        try:
            from appearance import color
        except ImportError:
            from linux.appearance import color
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():p.setOpacity(.45)

        w = self.width()
        h = self.height()
        radius = h / 2.0

        # Outer border & background matching Windows Styles/Colors.xaml
        p.setPen(QPen(QColor(color("BorderSecondColor", "#2A2A2A")), 1))
        p.setBrush(QColor(color("ButtonMainColor", "#2E2E2E")))
        p.drawRoundedRect(0.5, 0.5, w - 1.0, h - 1.0, radius, radius)

        # Segment geometries
        half_w = (w - 4) / 2.0
        seg_h = h - 4

        font = QFont("Segoe UI", 9)
        font.setBold(True)
        p.setFont(font)

        if self.isChecked():
            # Right active (On) - Slate blue pill #3E4450
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color("ControlActiveColor", "#3E4450")))
            p.drawRoundedRect(2 + half_w, 2, half_w, seg_h, radius - 1, radius - 1)

            # Left text (Off text, muted #787878)
            p.setPen(QColor(color("TextMutedColor", "#787878")))
            p.drawText(QRectF(2, 2, half_w, seg_h), Qt.AlignCenter, self._off_text)

            # Right text (On text, pure white #FFFFFF)
            p.setPen(QColor(color("TextPrimaryColor", "#FFFFFF")))
            p.drawText(QRectF(2 + half_w, 2, half_w, seg_h), Qt.AlignCenter, self._on_text)
        else:
            # Left active (Off) - Dark button pill #242424
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color("ButtonSecondColor", "#242424")))
            p.drawRoundedRect(2, 2, half_w, seg_h, radius - 1, radius - 1)

            # Left text (Off text, light white #F0F0F0)
            p.setPen(QColor(color("TextPrimaryColor", "#F0F0F0")))
            p.drawText(QRectF(2, 2, half_w, seg_h), Qt.AlignCenter, self._off_text)

            # Right text (On text, muted #787878)
            p.setPen(QColor(color("TextMutedColor", "#787878")))
            p.drawText(QRectF(2 + half_w, 2, half_w, seg_h), Qt.AlignCenter, self._on_text)

    def mousePressEvent(self, event):
        if not self.isEnabled() or event.button()!=Qt.LeftButton:return
        # Left half = off, Right half = on
        target = event.position().x() > (self.width() / 2.0)
        self.setChecked(target if self.isChecked() != target else not target)
        self.clicked.emit(self.isChecked())


class SettingSwitchRow(QWidget):
    """Exact port of SettingSwitchRow.xaml."""
    toggled = Signal(bool)

    def __init__(self, title, parent=None, checked=False, on_text="│", off_text="○", width=56):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self.label = QLabel(title)
        self.label.setStyleSheet("font-weight: 600; font-size: 12px; ")
        layout.addWidget(self.label)
        layout.addStretch()

        self.switch = RectangularSwitch(self, width=width, on_text=on_text, off_text=off_text)
        self.switch.setChecked(checked)
        self.switch.toggled.connect(self.toggled)
        layout.addWidget(self.switch)

    def isChecked(self):
        return self.switch.isChecked()

    def setChecked(self, val):
        self.switch.setChecked(val)

    def blockSignals(self, blocked):
        return self.switch.blockSignals(blocked)


class SettingDropdownRow(QWidget):
    """Exact port of SettingDropdownRow.xaml."""
    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)

    def __init__(self, title, parent=None, dropdown_width=180):
        super().__init__(parent)
        from PySide6.QtWidgets import QComboBox
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        self.label = QLabel(title)
        self.label.setStyleSheet("font-weight: 600; font-size: 12px; margin-right: 12px;")
        layout.addWidget(self.label)
        layout.addStretch()

        self.combo = QComboBox(self)
        self.combo.setFixedHeight(28)
        self.combo.setFixedHeight(28)
        if dropdown_width:
            self.combo.setFixedWidth(dropdown_width)
        self.combo.currentIndexChanged.connect(self.currentIndexChanged)
        self.combo.currentTextChanged.connect(self.currentTextChanged)
        layout.addWidget(self.combo)

    def addItems(self, items):
        self.combo.addItems(items)

    def addItem(self, text, userData=None):
        self.combo.addItem(text, userData)

    def currentText(self):
        return self.combo.currentText()

    def setCurrentText(self, text):
        self.combo.setCurrentText(text)

    def currentIndex(self):
        return self.combo.currentIndex()

    def setCurrentIndex(self, index):
        self.combo.setCurrentIndex(index)


class SettingActionRow(QWidget):
    """Exact port of SettingActionRow.xaml."""
    clicked = Signal()

    def __init__(self, title, action_text="Open", parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QPushButton
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self.label = QLabel(title)
        self.label.setStyleSheet("font-weight: 600; font-size: 12px; ")
        layout.addWidget(self.label)
        layout.addStretch()

        self.button = QPushButton(action_text, self)
        self.button.setFixedHeight(28)
        self.button.setStyleSheet("padding: 0 16px; font-weight: 600;")
        self.button.clicked.connect(self.clicked)
        layout.addWidget(self.button)


class SettingValueRow(QWidget):
    """Exact port of SettingValueRow.xaml."""
    valueChanged = Signal(int)

    def __init__(self, title, value=0, unit="W", min_val=0, max_val=255, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QSpinBox
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self.label = QLabel(title)
        self.label.setStyleSheet("font-weight: 600; font-size: 12px; ")
        layout.addWidget(self.label)
        layout.addStretch()

        self.spin = QSpinBox(self)
        self.spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(value)
        if unit:
            self.spin.setSuffix(f" {unit}")
        self.spin.setFixedWidth(90)
        self.spin.setFixedHeight(28)
        self.spin.valueChanged.connect(self.valueChanged)
        layout.addWidget(self.spin)

    def value(self):
        return self.spin.value()

    def setValue(self, val):
        self.spin.setValue(val)


class SettingSliderRow(QWidget):
    """Exact port of SettingSliderRow.xaml."""
    valueChanged = Signal(int)

    def __init__(self, title, minimum, maximum, value, unit="", parent=None):
        super().__init__(parent)
        self._unit = unit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self.label_title = QLabel(title)
        self.label_title.setStyleSheet("font-weight: 600; font-size: 12px; ")
        top.addWidget(self.label_title)
        top.addStretch()

        self.label_value = QLabel(f"{value}{unit}")
        self.label_value.setStyleSheet("font-weight: 600; font-size: 12px; ")
        top.addWidget(self.label_value)
        layout.addLayout(top)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.slider)

    def _on_value_changed(self, val):
        self.label_value.setText(f"{val}{self._unit}")
        self.valueChanged.emit(val)

    def value(self):
        return self.slider.value()

    def setValue(self, val):
        self.slider.setValue(val)


def confirm_gpu_mode(parent, mode):
    """PreySense shell and footer, matching Windows CustomModalDialog."""
    from PySide6.QtWidgets import QDialog, QPushButton, QFrame
    dialog = QDialog(parent)
    dialog.setWindowTitle('PreySense • Hardware Discrete GPU')
    dialog.setWindowFlags(dialog.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    dialog.setModal(True)
    dialog.setFixedWidth(440)
    dialog.setObjectName('gpuModeConfirmation')
    # Footer already reserves bottom padding; avoid a second outer blank strip.
    dialog.setProperty('bottomMarginApplied', True)
    body = QVBoxLayout(dialog)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)
    from window_chrome import WindowTitleBar
    body.addWidget(WindowTitleBar(dialog,title='Hardware Display MUX',on_close=dialog.reject))
    content = QVBoxLayout(); content.setContentsMargins(14, 10, 14, 8)
    prompt_text = f'Would you like to switch to {mode} mode and restart now?'
    message = QLabel(prompt_text)
    message.setWordWrap(True)
    message.setStyleSheet('font-size:15px; font-weight:400;')
    content.addWidget(message); body.addLayout(content)

    panel = QFrame(); panel.setObjectName('windowFooter')
    from appearance import color
    panel.setStyleSheet('QFrame#windowFooter {background:%s;border-top:1px solid %s;}' % (color('CardBgColor','#202020'),color('BorderSecondColor','#2a2a2a')))
    footer = QHBoxLayout(panel); footer.setContentsMargins(14, 10, 14, 16); footer.setSpacing(4)
    cancel = QPushButton('Cancel')
    confirm = QPushButton('Apply && Restart Now')
    for button in (cancel, confirm):
        button.setMinimumHeight(34)
        footer.addWidget(button)
    cancel.clicked.connect(dialog.reject)
    confirm.clicked.connect(dialog.accept)
    cancel.setDefault(True)
    cancel.setFocus()
    body.addWidget(panel)
    dialog.adjustSize()
    dialog.move(parent.frameGeometry().center() - dialog.rect().center())
    return dialog.exec() == QDialog.Accepted


from PySide6.QtWidgets import QComboBox

class CenteredComboBox(QComboBox):
    """Center the selected label without introducing an editable field."""
    def paintEvent(self,event):
        from PySide6.QtWidgets import QStylePainter,QStyleOptionComboBox,QStyle
        from PySide6.QtGui import QPalette
        option=QStyleOptionComboBox();self.initStyleOption(option)
        painter=QStylePainter(self)
        painter.drawComplexControl(QStyle.CC_ComboBox,option)
        rect=self.style().subControlRect(QStyle.CC_ComboBox,option,QStyle.SC_ComboBoxEditField,self)
        painter.drawItemText(rect,Qt.AlignCenter,option.palette,self.isEnabled(),option.currentText,QPalette.ButtonText)
