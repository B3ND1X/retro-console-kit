import importlib.util,unittest,io,contextlib,subprocess
from pathlib import Path
from unittest.mock import patch
file=Path(__file__).resolve().parents[1]/'runtime/system_settings.py';spec=importlib.util.spec_from_file_location('settings',file);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
A='AA:BB:CC:DD:EE:FF'
class Tests(unittest.TestCase):
 def test_resolved_name(self):
  name,state,details=s.bt_identity(A,A,' Name: Xbox Wireless Controller\n Appearance: 0x03c4\n RSSI: -48\n Paired: yes\n Modalias: usb:v045Ep0B13d0001\n')
  self.assertEqual(name,'Xbox Wireless Controller');self.assertEqual(state,'Paired');self.assertIn('Gamepad',details);self.assertIn('Signal -48 dBm',details)
 def test_alias(self):self.assertEqual(s.bt_identity(A,A,' Alias: My controller\n')[0],'My controller')
 def test_unnamed(self):self.assertEqual(s.bt_identity(A,A,' Alias: AA-BB-CC-DD-EE-FF\n')[0],'Unnamed Bluetooth device')
 def test_connected(self):self.assertEqual(s.bt_identity(A,'Pad',' Connected: yes\n Paired: yes\n')[1],'Connected')
 def test_no_vendor_guess(self):self.assertEqual(s.bt_identity('98:7A:14:00:00:00','','')[0],'Unnamed Bluetooth device')
 def test_class(self):self.assertIn('Gamepad',s.bt_identity(A,'Pad',' Class: 0x000508\n')[2])
 def test_bad_properties(self):self.assertEqual(s.bt_identity(A,'Pad',' Class: bogus\n Appearance: no\n RSSI: injected\n')[2],[])
 def test_output_address(self):
  def bt(cmd,timeout=8):return 'Powered: yes' if cmd==['show'] else 'Device '+A+' '+A if cmd==['devices'] else ' Name: Xbox Wireless Controller\n'
  with patch.object(s,'bt',bt),contextlib.redirect_stdout(io.StringIO()) as out:s.bt_list()
  self.assertIn('Xbox Wireless Controller ['+A+']',out.getvalue())
 def test_info_timeout_keeps_address(self):
  def bt(cmd,timeout=8):
   if cmd[0]=='info':raise subprocess.TimeoutExpired(cmd,timeout)
   return 'Powered: yes' if cmd==['show'] else 'Device '+A+' '+A
  with patch.object(s,'bt',bt),contextlib.redirect_stdout(io.StringIO()) as out:s.bt_list()
  self.assertIn('Unnamed Bluetooth device ['+A+']',out.getvalue())
 def test_pair_reports_mapping_target(self):
  def bt(cmd,timeout=8):return ' Name: Xbox Wireless Controller\n Paired: yes\n Connected: yes\n' if cmd[0]=='info' else ''
  with patch.object(s,'bt',bt),contextlib.redirect_stdout(io.StringIO()) as out:s.bt_pair({'address':A})
  self.assertIn('MAPPING_DEVICE\tXbox Wireless Controller',out.getvalue())
 def test_no_mapping_prompt_on_failed_connection(self):
  with patch.object(s,'bt',return_value=' Paired: yes\n Connected: no\n'),contextlib.redirect_stdout(io.StringIO()) as out:
   with self.assertRaises(s.Error):s.bt_pair({'address':A})
  self.assertNotIn('MAPPING_DEVICE',out.getvalue())
 def test_address_validation(self):
  with self.assertRaises(s.Error):s.bt_pair({'address':'invalid; command'})
if __name__=='__main__':unittest.main()
