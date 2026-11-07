import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory_reader import configured_speed,publish

def record(speed,size=8192):
    data=bytearray(0x22);data[0]=17;data[1]=len(data)
    data[0x0c:0x0e]=size.to_bytes(2,'little')
    data[0x20:0x22]=speed.to_bytes(2,'little')
    return bytes(data)+b'\0\0'

class MemoryReaderTests(unittest.TestCase):
    def test_configured_speed_from_populated_slots(self):
        self.assertEqual(configured_speed(record(6400)+record(6400)),6400)
        self.assertEqual(configured_speed(record(7200,0)+record(6400)),6400)
        self.assertEqual(configured_speed(record(6400)+record(5600)),5600)
    def test_missing_or_truncated_data_is_not_guessed(self):
        for data in (b'',record(0),record(65535),record(6400)[:20],b'\x11\x01\0\0'):
            self.assertIsNone(configured_speed(data))
    def test_publish_numeric_only_and_remove_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'DMI';target=Path(folder)/'out/speed_mts'
            source.write_bytes(record(6400));self.assertEqual(publish(source,target),6400)
            self.assertEqual(target.read_text(),'6400\n')
            self.assertEqual(target.stat().st_mode&0o777,0o444)
            source.write_bytes(record(0));self.assertIsNone(publish(source,target))
            self.assertFalse(target.exists())
