"""Automatic factory-defaults capture UI (Windows CaptureMissingFactoryDefaults path).

No Later/Calibrate consent prompt — missing defaults are captured on startup.
ERM4-first capture is instantaneous; live mode settle shows progress.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from window_chrome import WindowTitleBar


def run_calibration(parent):
    """Show progress while the worker captures factory defaults automatically."""
    dialog = QDialog(parent)
    dialog.setWindowTitle('PreySense • Factory Power Limits')
    dialog.setFixedWidth(440)
    dialog.setModal(True)
    dialog.setProperty('bottomMarginApplied', True)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    header = WindowTitleBar(dialog, title='Factory Power Limits')
    header.close_button.setEnabled(False)
    root.addWidget(header)
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.setContentsMargins(14, 10, 14, 8)
    message = QLabel('Capturing factory defaults…')
    message.setStyleSheet('font-size:15px;font-weight:400;')
    message.setWordWrap(True)
    layout.addWidget(message)
    root.addWidget(body)
    footer = QHBoxLayout()
    footer.setContentsMargins(14, 10, 14, 16)
    done_btn = QPushButton('Done')
    done_btn.setFixedHeight(34)
    done_btn.setVisible(False)
    footer.addWidget(done_btn)
    root.addLayout(footer)
    finished = [False]
    success = [False]

    def complete(error):
        finished[0] = True
        success[0] = not error
        message.setText(('Could not capture factory defaults: ' + error) if error else 'Factory defaults saved.')
        done_btn.setVisible(True)
        done_btn.setEnabled(True)
        header.close_button.setEnabled(True)

    def close():
        if finished[0]:
            dialog.accept()

    done_btn.clicked.connect(close)
    header.close_button.clicked.connect(close)
    dialog.reject = lambda: close()
    parent.worker.calibration_progress.connect(message.setText)
    parent.worker.calibration_finished.connect(complete)
    QTimer.singleShot(0, lambda: parent.command.emit('calibrate', True))
    dialog.adjustSize()
    dialog.move(parent.frameGeometry().center() - dialog.rect().center())
    try:
        dialog.exec()
    finally:
        parent.worker.calibration_progress.disconnect(message.setText)
        parent.worker.calibration_finished.disconnect(complete)
    return success[0]


def confirm_calibration(parent):
    """Deprecated: Windows path captures automatically. Kept for older call sites."""
    return True
