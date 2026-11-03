import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import os
from installer import setup_core as core


def payload(folder,name,files):
    path=Path(folder)/name
    with zipfile.ZipFile(path,'w') as archive:
        for member,content in files.items():archive.writestr(member,content)
        archive.writestr('payload.json',json.dumps({'version':'99.0'}))
    return str(path)


class TransactionalUpdateTests(unittest.TestCase):
    def test_success_preserves_user_files_and_replaces_old_managed_files(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'Enigma Cube'
            old=payload(folder,'old.zip',{'EnigmaCube.exe':b'old','_internal/old.dll':b'old dll'})
            new=payload(folder,'new.zip',{'EnigmaCube.exe':b'new','_internal/new.dll':b'new dll'})
            core.install_files(old,str(target))
            (target/'notes.txt').write_text('user data')
            core.install_files(new,str(target))
            self.assertEqual((target/'EnigmaCube.exe').read_bytes(),b'new')
            self.assertFalse((target/'_internal/old.dll').exists())
            self.assertEqual((target/'notes.txt').read_text(),'user data')

    def test_extract_failure_leaves_the_entire_old_version_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'Enigma Cube'
            old=payload(folder,'old.zip',{'EnigmaCube.exe':b'old','_internal/a.dll':b'old dll'})
            new=payload(folder,'new.zip',{'EnigmaCube.exe':b'new','_internal/a.dll':b'new dll'})
            core.install_files(old,str(target))
            with patch.object(core.shutil,'copyfileobj',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):core.install_files(new,str(target))
            self.assertEqual((target/'EnigmaCube.exe').read_bytes(),b'old')
            self.assertEqual((target/'_internal/a.dll').read_bytes(),b'old dll')

    def test_mid_install_failure_rolls_back_program_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'Enigma Cube'
            old=payload(folder,'old.zip',{'EnigmaCube.exe':b'old','_internal/a.dll':b'old dll'})
            new=payload(folder,'new.zip',{'EnigmaCube.exe':b'new','_internal/a.dll':b'new dll'})
            core.install_files(old,str(target))
            previous_manifest=(target/core.MANIFEST).read_bytes()
            replace=os.replace
            def fail_once(src,dst):
                if '/new/_internal/' in str(src).replace('\\','/'):
                    raise OSError('file locked')
                return replace(src,dst)
            with patch.object(core.os,'replace',side_effect=fail_once):
                with self.assertRaises(OSError):core.install_files(new,str(target))
            self.assertEqual((target/'EnigmaCube.exe').read_bytes(),b'old')
            self.assertEqual((target/'_internal/a.dll').read_bytes(),b'old dll')
            self.assertEqual((target/core.MANIFEST).read_bytes(),previous_manifest)

    def test_traversal_and_missing_program_cannot_replace_a_working_install(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'app'
            valid=payload(folder,'valid.zip',{'EnigmaCube.exe':b'old'})
            malicious=payload(folder,'malicious.zip',{'EnigmaCube.exe':b'new','../app-evil/pwn':b'bad','..\\other':b'bad'})
            core.install_files(valid,str(target))
            core.install_files(malicious,str(target))
            self.assertFalse((Path(folder)/'app-evil').exists())
            self.assertFalse((Path(folder)/'other').exists())
            invalid=payload(folder,'missing.zip',{'_internal/a.dll':b'no app'})
            with self.assertRaises(ValueError):core.install_files(invalid,str(target))
            self.assertEqual((target/'EnigmaCube.exe').read_bytes(),b'new')

    def test_update_does_not_force_close_other_processes(self):
        with patch.object(core,'payload_info',return_value=('99.0',12)),patch.object(core,'close_running_app') as kill,patch.object(core,'install_files'),patch.object(core,'create_shortcuts'),patch.object(core,'write_registry'):
            self.assertEqual(core.install('fixture.zip','fixture',close_running=False),'99.0')
            kill.assert_not_called()


if __name__=='__main__':unittest.main()
