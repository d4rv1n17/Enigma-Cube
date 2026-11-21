import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from enigma_timer import hub_link


class HubLinkTests(unittest.TestCase):
    def test_requires_supported_installed_hub(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / 'EnigmaHub.exe'
            exe.write_bytes(b'test')
            marker = exe.parent / '.enigma-hub-install.json'
            for version, expected in [('1.2.3', False), ('1.3.0', True), ('1.4.0', True), ('bad', False)]:
                marker.write_text(json.dumps({'product': 'Enigma Hub', 'version': version}))
                self.assertEqual(hub_link.supported_hub(exe), expected)

    def test_direct_packaged_launch_routes_to_hub_and_exits(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(hub_link, 'claim_launch', return_value=False), patch.object(hub_link, 'open_hub') as launch:
            self.assertFalse(hub_link.ensure_launch())
            launch.assert_called_once_with('launch')

    def test_authorized_packaged_launch_does_not_open_hub_again(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(hub_link, 'claim_launch', return_value=True), patch.object(hub_link, 'open_hub') as launch:
            self.assertTrue(hub_link.ensure_launch())
            launch.assert_not_called()

    def test_packaged_cube_does_not_check_download_or_restore_old_updates(self):
        from enigma_timer.updates import UpdateService
        from enigma_timer.storage import Store
        with tempfile.TemporaryDirectory() as directory, patch.object(sys, 'frozen', True, create=True):
            service = UpdateService(Store(str(Path(directory) / 'data.json')))
            with patch.object(service, 'fetch') as fetch, patch.object(hub_link, 'open_hub') as launch:
                service.automatic_check()
                service.check(manual=True)
                fetch.assert_not_called()
                launch.assert_called_once_with('updates')
                self.assertFalse(service.can_install)
            service.close()


if __name__ == '__main__':
    unittest.main()
