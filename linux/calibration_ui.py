"""Consent and progress for missing-only per-mode calibration."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame,QWidget
from window_chrome import WindowTitleBar
from appearance import color

def confirm_calibration(parent):
    dialog=QDialog(parent);dialog.setWindowTitle('PreySense • Factory Calibration')
    dialog.setModal(True);dialog.setFixedWidth(440)
    dialog.setObjectName('calibrationConfirmation');dialog.setProperty('bottomMarginApplied',True)
    root=QVBoxLayout(dialog);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
    root.addWidget(WindowTitleBar(dialog,title='Factory Calibration',on_close=dialog.reject))
    content=QVBoxLayout();content.setContentsMargins(14,10,14,8)
    message=QLabel('PreySense needs to capture factory power limits for each mode before tuning can continue. Already-saved modes are kept. Plug in AC power, then start calibration.')
    message.setWordWrap(True);message.setStyleSheet('font-size:15px;font-weight:400;');content.addWidget(message)
    root.addLayout(content)
    panel=QFrame();panel.setObjectName('calibrationFooter')
    panel.setStyleSheet('QFrame#calibrationFooter {background:%s;border-top:1px solid %s;}'%(color('CardBgColor','#202020'),color('BorderSecondColor','#2a2a2a')))
    footer=QHBoxLayout(panel);footer.setContentsMargins(14,10,14,16);footer.setSpacing(4)
    later=QPushButton('Later');accept=QPushButton('Calibrate Now')
    for button in (later,accept):button.setFixedHeight(34);footer.addWidget(button)
    later.clicked.connect(dialog.reject);accept.clicked.connect(dialog.accept);later.setDefault(True)
    root.addWidget(panel);dialog.adjustSize();dialog.move(parent.frameGeometry().center()-dialog.rect().center())
    return dialog.exec()==QDialog.Accepted


def run_calibration(parent):
    """Keep the mode cycle in the worker; this modal only displays progress."""
    from PySide6.QtCore import QTimer
    dialog=QDialog(parent);dialog.setWindowTitle('PreySense • Factory Power Limits');dialog.setFixedWidth(440)
    dialog.setModal(True);dialog.setProperty('bottomMarginApplied',True)
    root=QVBoxLayout(dialog);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
    header=WindowTitleBar(dialog,title='Factory Power Limits');header.close_button.setEnabled(False);root.addWidget(header)
    body=QWidget();layout=QVBoxLayout(body);layout.setContentsMargins(14,10,14,8)
    message=QLabel('Reading Eco...');message.setStyleSheet('font-size:15px;font-weight:400;');message.setWordWrap(True);layout.addWidget(message);root.addWidget(body)
    footer=QHBoxLayout();footer.setContentsMargins(14,10,14,16)
    done_btn=QPushButton('Done');done_btn.setFixedHeight(34);done_btn.setVisible(False);footer.addWidget(done_btn);root.addLayout(footer)
    finished=[False];success=[False]
    def complete(error):
        finished[0]=True;success[0]=not error
        message.setText(('Could not finish calibration: '+error) if error else 'Factory defaults saved.')
        done_btn.setVisible(True);done_btn.setEnabled(True);header.close_button.setEnabled(True)
    def close():
        if finished[0]:dialog.accept()
    done_btn.clicked.connect(close);header.close_button.clicked.connect(close)
    dialog.reject=lambda:close()
    parent.worker.calibration_progress.connect(message.setText)
    parent.worker.calibration_finished.connect(complete)
    QTimer.singleShot(0,lambda:parent.command.emit('calibrate',True))
    dialog.adjustSize();dialog.move(parent.frameGeometry().center()-dialog.rect().center())
    try:dialog.exec()
    finally:
        parent.worker.calibration_progress.disconnect(message.setText)
        parent.worker.calibration_finished.disconnect(complete)
    return success[0]
