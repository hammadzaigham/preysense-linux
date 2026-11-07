"""Unit tests for compact base UI components (AudioSwitch, AudioDialog, button, row)."""
import os
from pathlib import Path
import sys
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from audio_ui import AudioSwitch, AudioDialog, button, row

class AudioUiComponentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_audio_switch_toggle(self):
        switch = AudioSwitch()
        self.assertFalse(switch.isChecked())
        switch.setChecked(True)
        self.assertTrue(switch.isChecked())
        self.assertEqual(switch.width(), 56)
        self.assertEqual(switch.height(), 28)

    def test_button_helper(self):
        clicked = []
        btn = button("Test Button", lambda: clicked.append(True))
        self.assertEqual(btn.text(), "Test Button")
        self.assertEqual(btn.height(), 30)
        btn.click()
        self.assertEqual(clicked, [True])

    def test_row_helper(self):
        parent = QWidget()
        layout = QVBoxLayout(parent)
        btn = QPushButton("Action")
        label = row(layout, "Row Title", btn, bold=True)
        self.assertEqual(label.text(), "Row Title")
        self.assertIn("font-weight:600", label.styleSheet())
        self.assertEqual(btn.height(), 28)

    def test_audio_dialog_geometry_and_structure(self):
        parent = QWidget()
        dialog = AudioDialog(parent, "Test Dialog", 400)
        self.assertEqual(dialog.width(), 400)
        self.assertIn("Test Dialog", dialog.windowTitle())
        self.assertIsNotNone(dialog.header)
        self.assertIsNotNone(dialog.body)
        footer = dialog.add_footer(QPushButton("OK"), QPushButton("Cancel"))
        self.assertEqual(footer.count(), 2)
        dialog.close()
        parent.close()

if __name__ == '__main__':
    unittest.main()
