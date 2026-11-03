import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from enigma_timer.storage import Store
from enigma_timer.updates import (Release,UpdateError,UpdateService,parse_release,
    newer,version_key,download_release,verify_package,install_command,fetch_latest,
    REPOSITORY,MAX_METADATA)

_APP=QApplication.instance() or QApplication([])
PAYLOAD=b'MZ'+bytes(range(256))*24
SHA=hashlib.sha256(PAYLOAD).hexdigest()
URL='https://github.com/'+REPOSITORY+'/releases/download/v99.0/EnigmaCube-Setup-99.0.exe'
RELEASE=Release('99.0',URL,SHA,len(PAYLOAD))


def metadata(version='99.0'):
    return {'tag_name':'v'+version,'draft':False,'prerelease':False,'assets':[{
        'name':'EnigmaCube-Setup-'+version+'.exe','state':'uploaded','size':len(PAYLOAD),
        'digest':'sha256:'+SHA,'browser_download_url':URL.replace('99.0',version)}]}


class UpdateTests(unittest.TestCase):
    def test_numeric_versions_do_not_downgrade_or_mix_prereleases(self):
        self.assertTrue(newer('3.10','3.9'))
        self.assertFalse(newer('3.1.0','3.1'))
        self.assertFalse(newer('3.0','3.1'))
        for value in ('3.2-beta','../3','3;evil','v3.2.0.0.0'):
            with self.assertRaises(UpdateError):version_key(value)
        self.assertIsNone(parse_release(metadata('3.0'),current='3.1'))

    def test_only_exact_project_asset_with_sha256_is_accepted(self):
        self.assertEqual(parse_release(metadata()),RELEASE)
        for mutation in ({'digest':None},{'digest':'sha256:bad'},
                         {'browser_download_url':URL.replace('github.com','evil.test')},
                         {'browser_download_url':URL.replace('/v99.0/','/v1.0/')},
                         {'size':True},{'size':300*1024*1024}):
            data=metadata()
            data['assets'][0].update(mutation)
            with self.subTest(mutation=mutation):
                with self.assertRaises(UpdateError):parse_release(data)
        for key in ('draft','prerelease'):
            data=metadata();data[key]=True
            with self.assertRaises(UpdateError):parse_release(data)

    def test_bounded_metadata_and_offline_failures(self):
        release=fetch_latest(opener=lambda url:io.BytesIO(json.dumps(metadata()).encode()))
        self.assertEqual(release,RELEASE)
        for body in (b'x'*(MAX_METADATA+1),b'not json',b'[]'):
            with self.assertRaises(UpdateError):fetch_latest(opener=lambda url:io.BytesIO(body))
        with self.assertRaises(UpdateError):
            fetch_latest(opener=lambda url:(_ for _ in ()).throw(OSError('offline')))

    def test_download_is_verified_before_atomic_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            progress=[]
            path=download_release(RELEASE,folder,threading.Event(),progress.append,lambda url:io.BytesIO(PAYLOAD))
            self.assertEqual(path.read_bytes(),PAYLOAD)
            self.assertTrue(verify_package(path,RELEASE))
            self.assertFalse(path.with_suffix('.exe.part').exists())
            self.assertEqual(progress[-1],100)
            # Cached verified packages avoid another network transfer.
            self.assertEqual(download_release(RELEASE,folder,threading.Event(),opener=lambda url:self.fail('network')),path)

    def test_corruption_truncation_and_cancellation_leave_no_installer(self):
        for content in (PAYLOAD[:-1],PAYLOAD+b'X',b'X'*len(PAYLOAD)):
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(UpdateError):
                    download_release(RELEASE,folder,threading.Event(),opener=lambda url:io.BytesIO(content))
                self.assertFalse(list(Path(folder).iterdir()))
        with tempfile.TemporaryDirectory() as folder:
            cancel=threading.Event();cancel.set()
            with self.assertRaises(UpdateError):
                download_release(RELEASE,folder,cancel,opener=lambda url:io.BytesIO(PAYLOAD))
            self.assertFalse(list(Path(folder).iterdir()))

    def test_installer_hand_off_quotes_paths_and_waits_for_saved_app_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/"test's folder $value"
            base.mkdir()
            package=base/RELEASE.filename
            package.write_bytes(PAYLOAD)
            executable=base/'EnigmaCube.exe'
            command=install_command(package,RELEASE,executable,1234,base/'result.txt')
            script=base64.b64decode(command[-1]).decode('utf-16-le')
            self.assertIn('Wait-Process -Id 1234',script)
            self.assertIn('Get-FileHash -LiteralPath',script)
            self.assertIn("test''s folder $value",script)
            self.assertIn("'--update'",script)
            self.assertIn('-WindowStyle Hidden',script)
            self.assertNotIn('taskkill',script)
            package.write_bytes(b'corrupt')
            with self.assertRaises(UpdateError):install_command(package,RELEASE,executable,1234,base/'result.txt')

    def test_service_download_persists_and_restores_verified_pending_update(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(str(Path(folder)/'data.json'))
            def download(release,target,cancel,progress):
                return download_release(release,target,cancel,progress,opener=lambda url:io.BytesIO(PAYLOAD))
            service=UpdateService(store,fetch=lambda:RELEASE,download=download)
            with patch.object(UpdateService,'can_install',new_callable=lambda:property(lambda self:True)):
                service.check(manual=True)
                service._thread.join(2)
                self.assertFalse(service._thread.is_alive())
                QTest.qWait(20)
                self.assertEqual(service.state,'ready')
                self.assertFalse(service.busy)
                self.assertTrue(verify_package(service.package,RELEASE))
                restored=UpdateService(store)
                self.assertEqual(restored.state,'ready')
                self.assertEqual(restored.release,RELEASE)
                restored.close()
            service.close()

    def test_offline_check_keeps_the_application_usable(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(str(Path(folder)/'data.json'))
            def fail():raise UpdateError('network')
            service=UpdateService(store,fetch=fail)
            service.check(manual=True)
            service._thread.join(2)
            QTest.qWait(20)
            self.assertEqual(service.state,'error')
            self.assertFalse(service.busy)
            self.assertIsNone(service.package)
            service.close()

    def test_invalid_saved_check_time_does_not_break_automatic_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(str(Path(folder)/'data.json'))
            service=UpdateService(store)
            with patch.object(UpdateService,'can_install',property(lambda self:True)):
                for value in ('invalid',{},float('nan')):
                    store.settings['update_last_check']=value
                    with patch.object(service,'check') as check:
                        service.automatic_check()
                        check.assert_called_once()
            service.close()


if __name__=='__main__':unittest.main()
