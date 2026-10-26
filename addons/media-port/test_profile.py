"""Regression for EmulationStation's multi-root XML settings format."""
import unittest,tempfile,sys,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent));import media_port
class ProfileTests(unittest.TestCase):
 def test_fragment_preferences_copied_without_changing_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);real=home/'.emulationstation';real.mkdir();settings=b'<?xml version="1.0"?>\n<bool name="Fullscreen" value="true" />\n<string name="UIMode" value="Kiosk" />\n<int name="MaxVRAM" value="100" />\n';(real/'es_settings.cfg').write_bytes(settings);(real/'es_input.cfg').write_text('<inputList/>')
   # Stop at lock open: profile creation must succeed before any runtime hardware action.
   original=os.open
   def stop(path,*a,**kw):
    if str(path)=='/run/snes-updater/game.lock':raise RuntimeError('profile created')
    return original(path,*a,**kw)
   with patch.object(media_port,'HOME',home),patch.object(media_port,'UI',home/'private/ui'),patch.object(media_port.os,'listdir',return_value=[]),patch.object(media_port.os,'open',side_effect=stop):
    with self.assertRaisesRegex(RuntimeError,'profile created'):media_port.main()
   result=(home/'private/ui/.emulationstation/es_settings.cfg').read_text();self.assertIn('UIMode',result);self.assertIn('Kiosk',result);self.assertIn('value="32"',result);self.assertNotIn('<settings>',result);self.assertEqual((real/'es_settings.cfg').read_bytes(),settings);self.assertEqual((home/'private/ui/.emulationstation/es_settings.cfg').stat().st_mode&0o777,0o600)
if __name__=='__main__':unittest.main()
