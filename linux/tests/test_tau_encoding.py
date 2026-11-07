import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tau_encoding import decode_us,linux_encode_us,infer_unit_us,windows_endpoint_request_us
class TauEncodingTests(unittest.TestCase):
 def test_observed_factory_window_and_kernel_unit(self):
  self.assertEqual(infer_unit_us(0x6f,55967744),976)
  self.assertEqual(decode_us(0x6f,976),55967744)
 def test_exact_representable_codes_and_fractional_truncation(self):
  for code in [c for c in range(128) if (c&31)>=2 or (c&96)==0]:
   with self.subTest(code=code):self.assertEqual(linux_encode_us(decode_us(code,976),976),code)
  # Linux divides requested microseconds by the unit before calculating F;
  # low-exponent fractional codes therefore lose their sub-unit fraction.
  self.assertEqual(linux_encode_us(decode_us(0x20,976),976),0)
  self.assertEqual(linux_encode_us(decode_us(0x61,976),976),0x41)
 def test_windows_endpoints_are_min_code1_and_finite_max(self):
  self.assertEqual(windows_endpoint_request_us(0,976),1952)
  maximum=windows_endpoint_request_us(449,976)
  self.assertEqual(maximum,3667902070784)
  self.assertEqual(linux_encode_us(maximum,976),127)
 def test_bad_or_inconsistent_unit_is_rejected(self):
  for value in (55967745,0,-1):
   with self.assertRaises(ValueError):infer_unit_us(0x6f,value)
  with self.assertRaises(ValueError):decode_us(128,976)
if __name__=='__main__':unittest.main()
