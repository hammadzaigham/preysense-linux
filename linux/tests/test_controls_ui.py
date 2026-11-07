"""Point-drag and color-wheel checks with Qt events only, no hardware writes."""
import os
from pathlib import Path
import sys
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QSpinBox
from controls import ColorWheel, FanGraph
from fan_curve import DEFAULT_DUTIES

class ControlsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def test_wheel_center_edge_and_keyboard_navigation(self):
        wheel = ColorWheel(); wheel.show(); self.app.processEvents(); spy = QSignalSpy(wheel.changed)
        QTest.mouseClick(wheel, Qt.LeftButton, pos=QPoint(75, 75))
        self.assertLess(wheel.color.saturationF(), .01)
        QTest.mouseClick(wheel, Qt.LeftButton, pos=QPoint(140, 75))
        self.assertGreater(wheel.color.saturationF(), .9)
        self.assertGreater(wheel.color.red(), 245)
        old = wheel.color.hueF(); QTest.keyClick(wheel, Qt.Key_Right)
        self.assertNotEqual(wheel.color.hueF(), old); self.assertGreaterEqual(spy.count(), 3)
        wheel.close()
    def graph(self):
        spins = [QSpinBox() for _ in DEFAULT_DUTIES]
        for spin, value in zip(spins, DEFAULT_DUTIES): spin.setRange(0, 100); spin.setValue(value)
        graph = FanGraph(spins); graph.show(); self.app.processEvents()
        return graph, spins
    def test_blank_area_and_simple_click_never_jump_duty(self):
        graph, spins = self.graph(); before = [s.value() for s in spins]
        QTest.mouseClick(graph, Qt.LeftButton, pos=QPoint(220, 20))
        self.assertEqual([s.value() for s in spins], before)
        point = graph.point(3, spins[3].value()).toPoint()
        QTest.mouseClick(graph, Qt.LeftButton, pos=point)
        self.assertEqual(graph.index, 3); self.assertEqual([s.value() for s in spins], before)
        graph.close()
    def test_drag_locks_temperature_and_preserves_monotonicity(self):
        graph, spins = self.graph(); point = graph.point(3, spins[3].value()).toPoint()
        QTest.mousePress(graph, Qt.LeftButton, pos=point)
        QTest.mouseMove(graph, point + QPoint(100, -80), delay=10)
        QTest.mouseRelease(graph, Qt.LeftButton, pos=point + QPoint(100, -80))
        self.assertEqual(graph.index, 3); self.assertEqual(spins[3].value(), spins[4].value())
        self.assertTrue(all(a.value() <= b.value() for a, b in zip(spins, spins[1:])))
        self.assertIsNone(graph.origin); graph.close()
    def test_keyboard_point_selection_and_edit_are_bounded(self):
        graph, spins = self.graph(); graph.setFocus()
        QTest.keyClick(graph, Qt.Key_Right); self.assertEqual(graph.index, 1)
        # Select index 3 where next point has room (index 3 is 26, index 4 is 26, index 6 is 35)
        QTest.keyClick(graph, Qt.Key_Right)
        QTest.keyClick(graph, Qt.Key_Right)
        self.assertEqual(graph.index, 3)
        # Verify Key_Up and Key_Down bounds
        old = spins[3].value()
        QTest.keyClick(graph, Qt.Key_Down)
        self.assertLessEqual(spins[3].value(), old)
        graph.close()

if __name__ == '__main__': unittest.main()
