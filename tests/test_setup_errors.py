import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

from installer import setup_app


class SetupErrorTests(unittest.TestCase):
    def test_windowed_quiet_failure_returns_one_and_preserves_original_error(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, 'stderr', None), \
                patch.object(setup_app.core, 'data_dir', return_value=folder), \
                patch.object(setup_app.core, 'install', side_effect=RuntimeError('Install Enigma Hub first')):
            self.assertEqual(setup_app.main(['--quiet', '--dir', os.path.join(folder, 'app')]), 1)
            message = (Path(folder) / 'setup-error.log').read_text()
            self.assertIn('Install Enigma Hub first', message)
            self.assertNotIn('NoneType', message)

    def test_failed_error_reporting_cannot_crash_setup(self):
        stream = Mock()
        stream.write.side_effect = OSError('closed stream')
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, 'stderr', stream), \
                patch.object(setup_app.core, 'data_dir', return_value=folder), \
                patch('builtins.open', side_effect=PermissionError('read only')):
            setup_app.report_setup_error(RuntimeError('original error'))
