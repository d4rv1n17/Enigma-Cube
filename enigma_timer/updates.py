"""Verified GitHub-release downloads and an isolated Windows update hand-off.

Network work runs outside the GUI thread. Downloading never executes code;
only an explicit restart action starts the verified installer after saving
the workspace. All release URLs stay pinned to this project's repository.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict,dataclass
from urllib.parse import urlparse
from urllib.request import Request,urlopen,HTTPRedirectHandler,build_opener
from PyQt5.QtCore import QObject,pyqtSignal
from . import VERSION
from .i18n import tr

REPOSITORY="d4rv1n17/Enigma-Cube"
RELEASE_API="https://api.github.com/repos/"+REPOSITORY+"/releases/latest"
MAX_PACKAGE=250*1024*1024
MAX_METADATA=1024*1024


class UpdateError(Exception):
    pass


def version_key(version):
    value=str(version).removeprefix("v")
    if not re.fullmatch(r"\d{1,4}(?:\.\d{1,4}){0,3}",value):
        raise UpdateError("invalid")
    parts=tuple(map(int,value.split(".")))
    return parts+(0,)*(4-len(parts))


def newer(version,current=VERSION):
    return version_key(version)>version_key(current)


def trusted_asset_url(url):
    parsed=urlparse(url)
    return (parsed.scheme=="https" and parsed.netloc=="github.com" and
            parsed.path.startswith("/"+REPOSITORY+"/releases/download/") and
            not parsed.query and not parsed.fragment)


def valid_release(release):
    version_key(release.version)
    urls={"https://github.com/"+REPOSITORY+"/releases/download/"+tag+"/"+release.filename
          for tag in (release.version,"v"+release.version)}
    return (release.url in urls and type(release.size) is int and 0<release.size<=MAX_PACKAGE and
            isinstance(release.sha256,str) and re.fullmatch(r"[0-9a-f]{64}",release.sha256) is not None)


class _HttpsRedirects(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,url):
        parsed=urlparse(url)
        allowed=("github.com","api.github.com","release-assets.githubusercontent.com","objects.githubusercontent.com")
        if parsed.scheme!="https" or parsed.hostname not in allowed:
            raise UpdateError("invalid")
        return super().redirect_request(request,fp,code,message,headers,url)


def _open(url):
    request=Request(url,headers={"User-Agent":"EnigmaCube/"+VERSION,"Accept":"application/vnd.github+json"})
    return build_opener(_HttpsRedirects()).open(request,timeout=12)


@dataclass(frozen=True)
class Release:
    version:str
    url:str
    sha256:str
    size:int

    @property
    def filename(self):
        return "EnigmaCube-Setup-"+self.version+".exe"


def parse_release(data,current=VERSION):
    if not isinstance(data,dict) or data.get("draft") or data.get("prerelease"):
        raise UpdateError("invalid")
    version=str(data.get("tag_name","")).removeprefix("v")
    if not newer(version,current):
        return None
    expected="EnigmaCube-Setup-"+version+".exe"
    assets=data.get("assets",[])
    if not isinstance(assets,list):
        raise UpdateError("invalid")
    for asset in assets:
        if not isinstance(asset,dict):
            raise UpdateError("invalid")
        if asset.get("name")!=expected or asset.get("state","uploaded")!="uploaded":
            continue
        url=asset.get("browser_download_url","")
        digest=asset.get("digest") or ""
        size=asset.get("size")
        if not trusted_asset_url(url) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}",digest):
            raise UpdateError("integrity")
        if type(size) is not int or not 0<size<=MAX_PACKAGE:
            raise UpdateError("invalid")
        release=Release(version,url,digest[7:].lower(),size)
        if not valid_release(release):
            raise UpdateError("invalid")
        return release
    raise UpdateError("missing")


def fetch_latest(current=VERSION,opener=_open):
    try:
        with opener(RELEASE_API) as response:
            raw=response.read(MAX_METADATA+1)
        if len(raw)>MAX_METADATA:
            raise UpdateError("invalid")
        return parse_release(json.loads(raw.decode("utf-8")),current)
    except UpdateError:
        raise
    except (ValueError,UnicodeError,TypeError):
        raise UpdateError("invalid") from None
    except Exception:
        raise UpdateError("network") from None


def file_digest(path):
    digest=hashlib.sha256()
    with open(path,"rb") as stream:
        for chunk in iter(lambda:stream.read(256*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_package(path,release):
    path=Path(path)
    try:
        return path.is_file() and path.stat().st_size==release.size and file_digest(path)==release.sha256
    except OSError:
        return False


def download_release(release,folder,cancel,progress=lambda value:None,opener=_open):
    if not valid_release(release):
        raise UpdateError("integrity")
    folder=Path(folder).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/release.filename
    partial=target.with_suffix(".exe.part")
    if verify_package(target,release):
        return target
    try:
        digest=hashlib.sha256()
        total=0
        with opener(release.url) as response,open(partial,"wb") as output:
            while True:
                if cancel.is_set():
                    raise UpdateError("cancelled")
                chunk=response.read(64*1024)
                if not chunk:
                    break
                total+=len(chunk)
                if total>release.size or total>MAX_PACKAGE:
                    raise UpdateError("integrity")
                digest.update(chunk)
                output.write(chunk)
                progress(min(100,int(total*100/release.size)))
        if total!=release.size or digest.hexdigest()!=release.sha256 or cancel.is_set():
            raise UpdateError("cancelled" if cancel.is_set() else "integrity")
        os.replace(partial,target)
        return target
    except UpdateError:
        raise
    except Exception:
        raise UpdateError("network") from None
    finally:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass


def _ps_string(value):
    return "'"+str(value).replace("'","''")+"'"


def install_command(path,release,executable,pid,result_file):
    """An out-of-process helper survives replacement of the installed EXE."""
    executable=Path(executable).resolve()
    installer=Path(path).resolve()
    if executable.name.lower()!="enigmacube.exe" or not valid_release(release) or not verify_package(installer,release):
        raise UpdateError("integrity")
    folder=executable.parent
    # Values are PowerShell literals; no shell-built file operations are used.
    script="\n".join((
        "$ErrorActionPreference = 'Stop'",
        "$installer = "+_ps_string(installer),
        "$target = "+_ps_string(folder),
        "$app = "+_ps_string(executable),
        "$result = "+_ps_string(Path(result_file).resolve()),
        "$expected = "+_ps_string(release.sha256),
        "try {",
        "  Wait-Process -Id "+str(int(pid))+" -Timeout 90 -ErrorAction SilentlyContinue",
        "  if (Get-Process -Id "+str(int(pid))+" -ErrorAction SilentlyContinue) { exit 2 }",
        "  if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'integrity' }",
        "  $quotedTarget = '\"' + $target + '\"'",
        "  $setup = Start-Process -FilePath $installer -ArgumentList @('--quiet','--update','--dir',$quotedTarget) -WindowStyle Hidden -Wait -PassThru",
        "  if ($setup.ExitCode -ne 0) { throw 'install' }",
        "  [IO.File]::WriteAllText($result, 'ok')",
        "} catch { [IO.File]::WriteAllText($result, 'failed') }",
        "if (Test-Path -LiteralPath $app) { Start-Process -FilePath $app -WorkingDirectory $target }",
    ))
    encoded=base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe","-NoProfile","-NonInteractive","-WindowStyle","Hidden","-EncodedCommand",encoded]


class UpdateService(QObject):
    changed=pyqtSignal()
    ready=pyqtSignal()
    _event=pyqtSignal(object)

    def __init__(self,store,parent=None,fetch=fetch_latest,download=download_release):
        super().__init__(parent)
        self.store=store
        self.folder=Path(store.path).resolve().parent/"updates"
        self.fetch,self.download=fetch,download
        self.state="idle"
        self.release=None
        self.package=None
        self.percent=0
        self.error=""
        self._cancel=threading.Event()
        self._closed=False
        self._busy=False
        self._thread=None
        self.manual=False
        self._event.connect(self._receive)
        self._restore()

    def _emit(self,event):
        try:
            if not self._closed:
                self._event.emit(event)
        except RuntimeError:
            pass  # Window was closed while the daemon was returning a reply.

    def _restore(self):
        try:
            record=self.folder/"pending.json"
            if not record.is_file() or record.stat().st_size>8192:
                return
            release=Release(**json.loads(record.read_text(encoding="utf-8")))
            if not valid_release(release):
                return
            path=self.folder/release.filename
            if not newer(release.version):
                path.unlink(missing_ok=True)
                record.unlink(missing_ok=True)
                return
            if verify_package(path,release):
                self.release,self.package,self.state=release,path,"ready"
                result=self.folder/"apply-result.txt"
                if result.is_file() and result.stat().st_size<32 and result.read_text(encoding="utf-8").strip()=="failed":
                    self.error="install"
        except (OSError,ValueError,TypeError,UpdateError):
            return

    @property
    def can_install(self):
        return sys.platform.startswith("win") and bool(getattr(sys,"frozen",False))

    @property
    def busy(self):
        return self._busy

    def automatic_check(self):
        if self.can_install and self.store.settings.get("auto_update",True) and self.state!="ready":
            now=time.time()
            try:
                last=float(self.store.settings.get("update_last_check",0) or 0)
            except (TypeError,ValueError):
                last=0
            if not 0<=last<=now:
                last=0
            if now-last>12*3600:
                self.check()

    def check(self,manual=False):
        if self._busy or self._closed or self.state=="ready":
            return
        self.manual=manual
        self.state,self.error="checking",""
        self._busy=True
        self._cancel.clear()
        self.changed.emit()
        auto_download=self.can_install and self.store.settings.get("auto_update",True)
        def work():
            try:
                release=self.fetch()
                if self._cancel.is_set():
                    return
                self._emit(("checked",release))
                if release and auto_download:
                    self._download_in_worker(release)
            except UpdateError as error:
                self._emit(("error",str(error)))
            except Exception:
                self._emit(("error","network"))
            finally:
                self._emit(("done",None))
        self._thread=threading.Thread(target=work,daemon=True,name="EnigmaUpdate")
        self._thread.start()

    def start_download(self):
        if self._busy or self._closed or self.release is None or not self.can_install:
            return
        self._busy=True
        self._cancel.clear()
        def work():
            try:
                self._download_in_worker(self.release)
            except UpdateError as error:
                self._emit(("error",str(error)))
            except Exception:
                self._emit(("error","network"))
            finally:
                self._emit(("done",None))
        self._thread=threading.Thread(target=work,daemon=True,name="EnigmaUpdateDownload")
        self._thread.start()

    def _download_in_worker(self,release):
        self._emit(("downloading",None))
        path=self.download(release,self.folder,self._cancel,lambda p:self._emit(("progress",p)))
        self.folder.mkdir(parents=True,exist_ok=True)
        temporary=self.folder/"pending.json.tmp"
        temporary.write_text(json.dumps(asdict(release)),encoding="utf-8")
        os.replace(temporary,self.folder/"pending.json")
        self._emit(("ready",(release,path)))

    def _receive(self,event):
        if self._closed:
            return
        kind,value=event
        if kind=="checked":
            self.release=value
            self.state="available" if value else "current"
            self.store.settings["update_last_check"]=time.time()
            try:
                self.store.save()
            except OSError:
                pass
        elif kind=="downloading":
            self.state,self.percent="downloading",0
        elif kind=="progress":
            self.percent=value
        elif kind=="ready":
            self.release,self.package=value
            self.state="ready"
            self.ready.emit()
        elif kind=="error":
            self.state,self.error=("idle","" ) if value=="cancelled" else ("error",value)
        elif kind=="done":
            self._busy=False
        self.changed.emit()

    def description(self):
        if self.error=="install":
            return tr("update_apply_failed")
        if self.state in ("available","ready"):
            return tr("update_"+self.state)%self.release.version
        if self.state=="downloading":
            return tr("update_downloading")%self.percent
        if self.state=="error":
            return tr("update_integrity_error" if self.error in ("integrity","invalid","missing") else "update_network_error")
        return tr("update_"+self.state)

    def apply(self):
        if self.state!="ready" or not self.can_install:
            raise UpdateError("source")
        command=install_command(self.package,self.release,sys.executable,os.getpid(),self.folder/"apply-result.txt")
        subprocess.Popen(command,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),close_fds=True)

    def close(self):
        self._closed=True
        self._cancel.set()

    def cancel(self):
        self._cancel.set()
