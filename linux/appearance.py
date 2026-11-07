"""Original PreySense light/dark tokens and five UI dictionaries, with stable enum data."""
import json
from pathlib import Path
from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor,QAction
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QAbstractButton,QGroupBox,QComboBox,QStyledItemDelegate

ASSETS=Path(__file__).parent/'assets'
def load(name,default):
    try:return json.loads((ASSETS/name).read_text())
    except (OSError,ValueError):return default
PALETTE=load('palette.json',{})
TRANSLATIONS=load('translations.json',{'en-US':{}})
LANGUAGES={'English':'en-US','Simplified Chinese':'zh-CN','Hindi':'hi-IN','Spanish':'es-ES','French':'fr-FR'}
CURRENT_THEME='Dark'
CURRENT_LANGUAGE='en-US'

def color(key,default='#a8a8a8'):
    return PALETTE.get(key,{}).get(CURRENT_THEME,default)
def icon_color():return '#000000' if CURRENT_THEME=='Light' else '#ffffff'
def translate(text):
    table=TRANSLATIONS.get(CURRENT_LANGUAGE,{})
    if text in table:return table[text]
    if '\n' in text and text.replace('\n',' ') in table:return table[text.replace('\n',' ')]
    aliases={'Automatic':'Auto','Maximum':'Max','Performance mode':'Performance Mode','Apply mode':'Apply','Apply keyboard lighting':'Apply'}
    if text in aliases:return table.get(aliases[text],text)
    for prefix in ('PreySense • ','PreySense · ','☀  '):
        if text.startswith(prefix):return prefix+table.get(text[len(prefix):],text[len(prefix):])
    for key in ('CPU: ','GPU: '):
        if text.startswith(key):return table.get(key,key)+text[len(key):]
    return text

class TranslationDelegate(QStyledItemDelegate):
    def displayText(self,value,locale):return translate(str(value))

class Appearance:
    def __init__(self,owner):
        self.owner=owner
        self.set_theme(owner.settings.value('theme','Dark'),False)
        self.set_language(owner.settings.value('language','en-US'),False)
    def style(self):
        import design
        style=design.STYLE
        if CURRENT_THEME=='Dark':return style
        tokens={'#1c1c1c':'WindowBgColor','#2e2e2e':'ButtonMainColor','#242424':'ButtonSecondColor','#383838':'ButtonHoverColor','#373737':'BorderMainColor','#f0f0f0':'TextPrimaryColor','#a8a8a8':'TextSecondaryColor','#787878':'TextMutedColor','#282b32':'ControlTrackColor','#758197':'ControlThumbHoverColor','#5c6576':'ControlThumbColor','#eaeff5':'ControlThumbBorderColor','#4a5260':'ControlTrackFillColor','#8b97af':'ControlThumbPressedColor','#3e4450':'ControlActiveColor'}
        for original,token in tokens.items():style=style.replace(original,color(token,original))
        style=style.replace('#424242','#C8CED6').replace('#545454','#B9C0C9').replace('#333333','#D8DDE3')
        style=style.replace('chevron-dark.svg','chevron-light.svg')
        return style+'\nQPushButton:checked {background:#E7F3FC;} QGroupBox {background:#FFFFFF;}\n'
    def set_theme(self,name,persist=True):
        global CURRENT_THEME
        if name not in ('Dark','Light'):name='Dark'
        CURRENT_THEME=name
        if persist:self.owner.settings.setValue('theme',name)
        QApplication.instance().setStyleSheet(self.style())
        self.recolor();self.owner.update()
    def set_language(self,code,persist=True):
        global CURRENT_LANGUAGE
        if code not in LANGUAGES.values():code='en-US'
        CURRENT_LANGUAGE=code;QLocale.setDefault(QLocale(code))
        if persist:self.owner.settings.setValue('language',code)
        self.refresh(True)
    def recolor(self):
        import design
        for widget in self.owner.findChildren(QWidget):
            asset=widget.property('assetIcon')
            if asset and isinstance(widget,QAbstractButton):widget.setIcon(design.icon(asset))
            asset=widget.property('assetPixmap')
            if asset and isinstance(widget,QLabel):widget.setPixmap(__import__('icon_assets').themed_pixmap(asset,int(widget.property('assetSize') or 14)))
            mode=widget.property('modeSvg')
            if mode and isinstance(widget,QLabel):widget.setPixmap(design.mode_pixmap(mode,int(widget.property('modeSize') or 18)))
            if widget.objectName()=='status' and widget.styleSheet() and not widget.property('error'):
                widget.setStyleSheet('color:'+color('TextSecondaryColor')+';')
            widget.update()
    def apply_text(self,obj,getter,setter,slot):
        current=getter();last=obj.property('i18n_last_'+slot)
        if obj.property('i18n_original_'+slot) is None or current!=last:obj.setProperty('i18n_original_'+slot,current)
        original=obj.property('i18n_original_'+slot);rendered=translate(original or '')
        if rendered!=current:setter(rendered)
        obj.setProperty('i18n_last_'+slot,rendered)
    def refresh(self,force=False):
        if CURRENT_LANGUAGE=='en-US' and not force:return
        for widget in [self.owner,*self.owner.findChildren(QWidget)]:
            if isinstance(widget,(QLabel,QAbstractButton)):self.apply_text(widget,widget.text,widget.setText,'text')
            if isinstance(widget,QGroupBox):self.apply_text(widget,widget.title,widget.setTitle,'title')
            if widget.isWindow():self.apply_text(widget,widget.windowTitle,widget.setWindowTitle,'window')
            if isinstance(widget,QComboBox) and not widget.property('preserveLanguageNames') and not hasattr(widget,'_translation_delegate'):
                widget._translation_delegate=TranslationDelegate(widget);widget.setItemDelegate(widget._translation_delegate)
                if hasattr(widget,'setLabelDrawingMode'):widget.setLabelDrawingMode(QComboBox.LabelDrawingMode.UseDelegate)
            if isinstance(widget,QComboBox):widget.update()
        for action in self.owner.findChildren(QAction):self.apply_text(action,action.text,action.setText,'action')
