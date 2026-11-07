"""Scoped compositor ownership, without changing test desktop settings."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
from kwin_integration import install_instant_effect, SOURCE

class KWinIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QCoreApplication.instance() or QCoreApplication([])
    def test_grab_only_exact_app_and_all_four_roles(self):
        engine=QJSEngine()
        engine.evaluate('''var grabs=[]; var connected={};
            function signal(name){return {connect:function(callback){connected[name]=callback;}};}
            var effects={stackingOrder:[{windowClass:'python3 PreySense'},{windowClass:'browser browser'}],
             windowAdded:signal('added'),windowClosed:signal('closed'),windowShown:signal('shown'),
             windowMinimized:signal('min'),windowUnminimized:signal('unmin')};
            var Effect={WindowAddedGrabRole:1,WindowClosedGrabRole:2,WindowMinimizedGrabRole:3,WindowUnminimizedGrabRole:4};
            var effect={grab:function(w,role,force){grabs.push([w.windowClass,role,force]);}};''')
        result=engine.evaluate((SOURCE/'contents/code/main.js').read_text())
        self.assertFalse(result.isError(),result.toString())
        self.assertEqual(engine.evaluate('grabs.length').toInt(),4)
        self.assertTrue(engine.evaluate('grabs.every(function(g){return g[2]===true;})').toBool())
        for name in ('added','closed','shown','min','unmin'):
            self.assertTrue(engine.evaluate(f"typeof connected['{name}']==='function'").toBool())
        for window in ("{windowClass:'preysense-helper helper'}", "{windowClass:'python3 python3',caption:'PreySense'}"):
            engine.evaluate(f'makeInstant({window})')
        self.assertEqual(engine.evaluate('grabs.length').toInt(),4)
        engine.evaluate("connected.shown({windowClass:'PreySense preysense'})")
        self.assertEqual(engine.evaluate('grabs.length').toInt(),8)
    def test_offscreen_never_changes_config(self):
        with patch.dict(os.environ,{'QT_QPA_PLATFORM':'offscreen','XDG_CURRENT_DESKTOP':'KDE'}),patch('kwin_integration.subprocess.run') as run:
            self.assertFalse(install_instant_effect()['available'])
            run.assert_not_called()
    def test_non_kde_never_changes_config(self):
        with patch.dict(os.environ,{'QT_QPA_PLATFORM':'xcb','XDG_CURRENT_DESKTOP':'GNOME'}),patch('kwin_integration.subprocess.run') as run:
            self.assertFalse(install_instant_effect()['available'])
            run.assert_not_called()
