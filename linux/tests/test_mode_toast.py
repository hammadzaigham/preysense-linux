"""No hardware: lifecycle and source layout contract for confirmed mode toasts."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QApplication,QWidget
from mode_toast import ModeToast,toast_position

class ToastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def test_modes_geometry_restart_and_click_through(self):
        owner=QWidget();toast=ModeToast(owner)
        self.assertTrue(toast.show_mode(4))
        self.assertEqual(toast.mode_name,'Performance')
        self.assertTrue(160 <= toast.width() <= 220)
        self.assertEqual(toast.height(),40)
        self.assertEqual(toast.animation.duration(),150)
        toast.animation.stop();toast.set_opacity(1);toast._animation_finished()
        self.assertTrue(toast.windowFlags() & Qt.WindowTransparentForInput)
        self.assertTrue(toast.testAttribute(Qt.WA_ShowWithoutActivating))

        self.assertTrue(toast.hide_timer.isActive())
        self.assertEqual(toast.hide_timer.interval(),1800)
        toast.hide_timer.timeout.emit();self.assertEqual(toast.animation.duration(),250)
        toast.animation.stop();toast.set_opacity(0);toast._animation_finished();self.assertFalse(toast.isVisible())
        toast.show_mode('Eco');self.assertTrue(toast.isVisible())
        self.assertFalse(toast.hide_timer.isActive())
        self.assertFalse(toast.show_mode('requested Turbo'))
        self.assertFalse(toast.show_mode(True))
        toast.fade_out();toast.animation.stop();toast.set_opacity(0);toast._animation_finished()
        self.assertFalse(toast.isVisible());toast.close();owner.close()
    def test_physical_bottom_offset(self):
        self.assertEqual(toast_position(QRect(100,200,1000,800),160,40,2),(520,924))
        self.assertEqual(toast_position(QRect(0,0,1000,800),160,40,1),(420,688))
    def test_render_has_transparent_corners_and_visible_content(self):
        toast=ModeToast();toast.show_mode('Balanced');toast.animation.stop();toast.set_opacity(1)
        image=toast.grab().toImage()
        self.assertEqual(image.pixelColor(0,0).alpha(),0)
        self.assertGreater(image.pixelColor(80,20).alpha(),0)
        toast.close()
if __name__=='__main__':unittest.main()
