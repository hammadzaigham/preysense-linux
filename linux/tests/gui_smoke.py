"""Run separately from unit tests; renders the real GUI and reads live hardware.

QT_QPA_PLATFORM=offscreen python3 linux/tests/gui_smoke.py
Exits through normal cleanup, which returns fans to automatic mode.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QPushButton,QComboBox
from PySide6.QtCore import QTimer
from preysense import Window
import design

app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(design.STYLE)
window=Window();window.show();failures=[]
def check():
    try:
        assert window.width()==500
        assert len(window.mode_tiles)==5
        for name,dialog in window.dialogs.items():
            dialog.show();app.processEvents()
            assert dialog.layout().count()>=2,f'{name}: empty dialog'
            dialog.hide()
        tuning=window.dialogs['Tuning'];tuning.show();app.processEvents()
        assert all(any(b.text()==name and b.isVisible() for b in tuning.findChildren(QPushButton)) for name in ('Reset','Apply','Save')), 'Tuning footer changed after telemetry'
        tuning.hide()
        window.overlay_dialog.show();app.processEvents()
        original=window.overlay_toggle.isChecked()
        window.hotkeys.overlay.emit();app.processEvents()
        assert window.overlay_enabled_row.isChecked()==(not original), 'Shortcut state did not reach overlay toggle'
        window.hotkeys.overlay.emit();app.processEvents()
        assert window.overlay_enabled_row.isChecked()==original
        assert window.overlay_dialog.isVisible()
        window.overlay_dialog.hide()
        window.dialogs['Lighting'].show();app.processEvents();window.toggle_window();assert not window.isVisible() and not window.dialogs['Lighting'].isVisible();window.toggle_window();app.processEvents();assert window.isVisible() and window.dialogs['Lighting'].isVisible();window.dialogs['Lighting'].hide()
        assert not hasattr(window,'defaults_dialog'), 'Manual defaults UI must be absent'
        window.documentation.show();app.processEvents();assert 'PreySense for Linux documentation' in window.documentation.browser.toPlainText();window.documentation.hide()
        assert not hasattr(window,"game_table") and "Games" not in window.dialogs
        assert window.power_apply.parentWidget() is not None
        print('GUI smoke passed: original shell and all control windows have visible content')
    except Exception as exc:
        import traceback;traceback.print_exc()
        failures.append(str(exc));print('GUI smoke failed:',exc)
    finally:window.quit_app()
QTimer.singleShot(3500,check)
app.exec()
sys.exit(bool(failures))
