"""Point-drag and color-wheel checks with Qt events only, no hardware writes."""
import os
from pathlib import Path
import sys
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication
from controls import ColorWheel, FanGraph
from fan_curve import default_stages, build_graph

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
        indices, temps, duties, lead = build_graph(default_stages(1), gpu=False)
        graph = FanGraph(); graph.set_curve(temps, duties, lead); graph.show(); self.app.processEvents()
        return graph, duties
    def test_blank_area_and_simple_click_never_jump_duty(self):
        graph, duties = self.graph(); before = list(graph.values)
        QTest.mouseClick(graph, Qt.LeftButton, pos=QPoint(220, 20))
        self.assertEqual(graph.values, before)
        point = graph.point(1, graph.values[1]).toPoint()
        QTest.mouseClick(graph, Qt.LeftButton, pos=point)
        self.assertEqual(graph.index, 1); self.assertEqual(graph.values, before)
        graph.close()
    def test_drag_keeps_duty_nondecreasing(self):
        graph, _ = self.graph(); point = graph.point(1, graph.values[1]).toPoint()
        QTest.mousePress(graph, Qt.LeftButton, pos=point)
        QTest.mouseMove(graph, point + QPoint(0, -80), delay=10)
        QTest.mouseRelease(graph, Qt.LeftButton, pos=point + QPoint(0, -80))
        self.assertEqual(graph.index, 1)
        self.assertTrue(all(a <= b for a, b in zip(graph.values, graph.values[1:])))
        self.assertIsNone(graph.origin); graph.close()
    def test_keyboard_point_selection_and_edit_are_bounded(self):
        graph, _ = self.graph(); graph.setFocus(); graph.index = 0; graph.selected.emit(0)
        QTest.keyClick(graph, Qt.Key_Right); self.assertEqual(graph.index, 1)
        old = graph.values[1]
        QTest.keyClick(graph, Qt.Key_Down)
        self.assertLessEqual(graph.values[1], old)
        graph.close()

if __name__ == '__main__': unittest.main()
