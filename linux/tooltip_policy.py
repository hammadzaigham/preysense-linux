"""Disable application tooltips, including widgets created after startup."""
from PySide6.QtCore import QObject,QEvent
from PySide6.QtWidgets import QToolTip
class NoTooltips(QObject):
    def eventFilter(self,obj,event):
        if event.type()==QEvent.ToolTip:
            QToolTip.hideText();return True
        if event.type()==QEvent.ToolTipChange and hasattr(obj,'toolTip') and obj.toolTip():obj.setToolTip('')
        return False

def install_no_tooltips(app):
    if not hasattr(app,'_preysense_no_tooltips'):
        app._preysense_no_tooltips=NoTooltips(app);app.installEventFilter(app._preysense_no_tooltips)
