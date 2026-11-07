"""Lighting changes use the real application's command builder, no hardware writes."""
import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,Signal,QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication,QWidget,QDialog,QSlider,QComboBox,QPushButton,QLabel,QCheckBox
from PySide6.QtTest import QTest
from lighting_ui import build_lighting_window,ZONE_PRESETS,LOGO_PRESETS
from preysense import Window
class Worker(QWidget):lighting_frame=Signal(list)
class Owner(QWidget):
    def __init__(self):
        super().__init__();self.temp=tempfile.TemporaryDirectory();self.settings=QSettings(str(Path(self.temp.name)/'prefs.ini'),QSettings.IniFormat)
        self.dialogs={'Lighting':QDialog(self)};self.worker=Worker();self.commands=[]
        self.colors=[QColor('#28d8ca') for _ in range(4)];self.color_buttons=[QPushButton() for _ in range(4)]
        self.brightness=QSlider(Qt.Horizontal);self.brightness.setRange(0,100);self.brightness.setValue(80)
        self.speed=QSlider(Qt.Horizontal);self.speed.setRange(0,10);self.speed.setValue(5)
        self.effect=QComboBox();self.effect.addItems(['Static','Breathing']);self.rgb_apply=QPushButton('Apply');self.rgb_status=QLabel('ENEK connected')
        self.original_timeout=QSlider(Qt.Horizontal);self.original_timeout.setRange(0,120);self.original_timeout.setValue(30)
        self.sync_logo_checkbox=QCheckBox();self.sync_logo=False;self.lighting_target='Keyboard'
        self.sync_logo_checkbox.toggled.connect(self.set_sync_logo)
        self.lighting_target_states={'Keyboard':dict(colors=self.colors[:],brightness=80,effect='Static',speed=5),'Logo':dict(colors=[QColor('#ffffff')]*4,brightness=60,effect='Neon',speed=3)}
    def set_sync_logo(self,value):self.sync_logo=value;self.settings.setValue('sync_logo',value)
    def apply(self,name,args):self.commands.append((name,args))
    def apply_lighting(self):Window.apply_lighting(self)
    def paint_colors(self):
        for item,color in zip(self.color_buttons,self.colors):item.setStyleSheet('background:'+color.name()+';min-height:64px;')
class LightingUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.app.setStyleSheet('')
        self.owner=Owner();self.dialog=build_lighting_window(self.owner);self.dialog.show();self.app.processEvents();self.ui=self.owner.lighting_ui
    def tearDown(self):self.ui['apply_timer'].stop();self.dialog.close();self.owner.close();self.app.processEvents();self.owner.temp.cleanup()
    def settle(self):QTest.qWait(110)
    def test_build_and_target_navigation_do_not_apply_or_offer_apply_status(self):
        self.assertEqual(self.dialog.width(),500)
        self.ui['select_target']('Logo');self.assertEqual(self.owner.effect.currentText(),'Neon')
        self.ui['select_target']('Keyboard');self.assertEqual(self.owner.effect.currentText(),'Static')
        self.settle();self.assertEqual(self.owner.commands,[])
        self.assertFalse(any(b.text()=='Apply' for b in self.dialog.findChildren(QPushButton)))
        self.assertFalse(any('ENEK' in v.text() for v in self.dialog.findChildren(QLabel)))
    def test_windows_control_geometry_without_changing_live_behavior(self):
        from window_chrome import WindowTitleBar
        self.assertEqual(len(self.dialog.findChildren(WindowTitleBar)),1)
        self.assertEqual(self.dialog.header.height(),30)
        self.assertEqual((self.ui['wheel'].width(),self.ui['wheel'].height()),(140,140))
        self.assertEqual(self.ui['mode'].width(),154)
        self.assertEqual(self.ui['preset'].width(),210)
        self.assertEqual((self.ui['hex'].width(),self.ui['hex'].height()),(80,26))
        self.assertEqual(self.owner.commands,[])

    def test_zone_preset_applies_original_colors_without_button(self):
        self.ui['sync'].setChecked(False);self.ui['preset'].setCurrentIndex(self.ui['preset'].findData('Cyberpunk'))
        self.settle();self.assertEqual(len(self.owner.commands),1)
        name,payload=self.owner.commands[-1];self.assertEqual(name,'lighting')
        self.assertEqual([QColor(*c).name().upper() for c in payload['colors']],ZONE_PRESETS['cyberpunk'])
    def test_mode_effect_and_speed_coalesce(self):
        self.ui['mode'].setCurrentText('Dynamic');combo=self.ui['effect']
        self.assertFalse(combo.model().item(combo.findText('Ripple')).isEnabled())
        combo.setCurrentIndex(combo.findText('Neon Wave'));self.ui['speed'].setValue(80)
        self.settle();self.assertEqual(len(self.owner.commands),1)
        self.assertEqual(self.owner.commands[-1][1]['effect'],'Neon');self.assertEqual(self.owner.commands[-1][1]['speed'],8)
    def test_wheel_hex_brightness_and_sync_apply_live_debounced(self):
        for i in range(12):self.ui['wheel'].changed.emit(QColor(100+i,80,60))
        self.owner.brightness.setValue(70);self.settle();self.assertEqual(len(self.owner.commands),1)
        self.assertEqual(self.owner.commands[-1][1]['brightness'],70)
        self.ui['hex'].setText('#123456');self.ui['hex'].editingFinished.emit();self.settle()
        self.assertEqual(self.owner.commands[-1][1]['colors'],[(18,52,86)]*4)
        self.ui['sync'].setChecked(False);self.settle();self.assertEqual(len(self.owner.commands),3)
    def test_logo_preset_power_and_sync_use_real_api(self):
        self.ui['select_target']('Logo');combo=self.ui['logo_preset'];combo.setCurrentIndex(combo.findData('Fire'));self.settle()
        self.assertEqual(self.owner.commands[-1][0],'logo_lighting')
        self.assertEqual(self.owner.commands[-1][1]['color'],(255,0,51))
        self.ui['sync_logo'].setChecked(True);self.settle()
        self.assertEqual(self.owner.commands[-1][0],'lighting');self.assertTrue(self.owner.commands[-1][1]['sync_logo'])
        self.assertTrue(self.ui['sync_logo'].isChecked());self.assertFalse(self.owner.brightness.isEnabled())
        self.ui['logo_power'].setChecked(False);self.settle()
        self.assertEqual(self.owner.commands[-1][1]['effect'],'Off');self.assertFalse(self.ui['sync_logo'].isChecked())
    def test_invalid_hex_never_applies_and_navigation_flushes_correct_target(self):
        before=[c.name() for c in self.owner.colors];self.ui['hex'].setText('invalid');self.ui['hex'].editingFinished.emit();self.settle()
        self.assertEqual([c.name() for c in self.owner.colors],before);self.assertEqual(self.owner.commands,[])
        self.owner.brightness.setValue(20);self.ui['select_target']('Logo');self.settle()
        self.assertEqual(len(self.owner.commands),1);self.assertEqual(self.owner.commands[-1][0],'lighting');self.assertEqual(self.owner.commands[-1][1]['brightness'],20)
    def test_logo_panels_follow_windows_mode_and_sync(self):
        self.dialog.show();self.ui['select_target']('Logo');self.ui['sync_logo'].setChecked(False)
        self.ui['logo_mode'].setCurrentText('Static');self.app.processEvents();self.app.processEvents()
        self.assertTrue(self.ui['logo_wheel'].isVisible());height=self.dialog.height()
        self.ui['logo_mode'].setCurrentText('Breathing');self.app.processEvents();self.app.processEvents()
        self.assertFalse(self.ui['logo_wheel'].isVisible());self.assertLess(self.dialog.height(),height)
        self.ui['sync_logo'].setChecked(True);self.app.processEvents();self.app.processEvents()
        self.assertFalse(self.ui['logo_mode'].isVisible())

    def test_auto_height_has_no_scroll_container(self):
        from PySide6.QtWidgets import QScrollArea
        self.dialog.show();self.app.processEvents()
        static_height=self.dialog.height()
        self.ui['mode'].setCurrentText('Dynamic');self.app.processEvents();self.app.processEvents()
        self.assertLess(self.dialog.height(),static_height)
        self.assertEqual(self.dialog.width(),500)
        self.assertEqual(self.dialog.findChildren(QScrollArea),[])
        self.ui['mode'].setCurrentText('Static');self.app.processEvents();self.app.processEvents()
        self.assertEqual(self.dialog.height(),static_height)

    def test_timeout_commit_uses_one_actual_value(self):
        self.owner.original_timeout.setValue(60);self.owner.original_timeout.sliderReleased.emit()
        self.assertEqual(self.owner.commands,[('led_timeout',60)])
if __name__=='__main__':unittest.main()
