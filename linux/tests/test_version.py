"""The app release label is independent of the installed bridge version."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from version import __version__

class VersionTests(unittest.TestCase):
    def test_application_release_version(self):
        self.assertEqual(__version__,'1.0.0')
