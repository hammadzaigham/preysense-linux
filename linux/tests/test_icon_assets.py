"""DPR checks for native source backing, transparency and vector mode assets."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QImage
from PySide6.QtWidgets import QApplication
import appearance
from icon_assets import themed_icon,themed_pixmap,svg_mode_pixmap,svg_icon_pixmap,FRONTEND_ROOT

class IconAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_icon_retains_native_raster_source_before_target_request(self):
        with tempfile.TemporaryDirectory() as directory:
            source=QImage(64,64,QImage.Format_ARGB32);source.fill(Qt.transparent)
            for x in range(8,56):
                for y in range(8,56):source.setPixelColor(x,y,QColor('white'))
            source.save(str(Path(directory)/'test.png'))
            with patch('icon_assets.RESOURCE_ROOT',Path(directory)):
                icon=themed_icon('test.png',16)
                self.assertEqual([(v.width(),v.height()) for v in icon.availableSizes()],[(64,64)])
                for dpr,physical in ((1,16),(1.25,20),(2,32)):
                    result=themed_pixmap('test.png',16,dpr)
                    self.assertEqual((result.width(),result.height()),(physical,physical))
                    self.assertEqual(result.devicePixelRatio(),dpr)
                    self.assertEqual(result.toImage().pixelColor(0,0).alpha(),0)
    def test_original_svg_renders_at_ceil_physical_size_and_stays_transparent(self):
        for dpr,physical in ((1,18),(1.25,23),(2,36)):
            result=svg_mode_pixmap('Balanced',18,dpr)
            self.assertEqual((result.width(),result.height()),(physical,physical))
            self.assertEqual(result.devicePixelRatio(),dpr)
            self.assertEqual(result.toImage().pixelColor(0,0).alpha(),0)
            self.assertTrue(any(result.toImage().pixelColor(x,y).alpha()>0 for x in range(physical) for y in range(physical)))
    def test_theme_resolves_lazily_without_changing_source_alpha(self):
        with patch.object(appearance,'CURRENT_THEME','Dark'):dark=svg_mode_pixmap('Balanced',18,2).toImage()
        with patch.object(appearance,'CURRENT_THEME','Light'):light=svg_mode_pixmap('Balanced',18,2).toImage()
        self.assertEqual(dark.size(),light.size())
        for y in range(dark.height()):
            for x in range(dark.width()):
                self.assertEqual(dark.pixelColor(x,y).alpha(),light.pixelColor(x,y).alpha())
                if dark.pixelColor(x,y).alpha()>200:
                    self.assertEqual(dark.pixelColor(x,y).red(),255)
                    self.assertEqual(light.pixelColor(x,y).red(),0)
    def test_original_brand_svg_preserves_density_and_missing_assets_are_null(self):
        brand=svg_icon_pixmap(FRONTEND_ROOT/'appicon.svg',16,2)
        self.assertEqual((brand.width(),brand.height()),(32,32));self.assertEqual(brand.devicePixelRatio(),2)
        self.assertTrue(svg_mode_pixmap('missing-icon',18,2).isNull())
        self.assertTrue(themed_icon('missing-icon.png').isNull())
    def test_invalid_density_is_not_silently_rendered_at_wrong_scale(self):
        for dpr in (0,-1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):svg_mode_pixmap('Balanced',18,dpr)

if __name__=='__main__':unittest.main()
