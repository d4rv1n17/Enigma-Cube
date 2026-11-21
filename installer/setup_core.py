# -*- coding: utf-8 -*-
"""Install / update / uninstall logic for the Enigma Cube setup (no GUI).

Windows-only parts (registry, shortcuts, closing the running app) are no-ops
elsewhere, so the file logic can be tested on any OS.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

APP_NAME = "Enigma Cube"
APP_EXE = "EnigmaCube.exe"
PUBLISHER = "Enigma Studio"
MANIFEST = "install_manifest.txt"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\EnigmaCube"
# Inno Setup installer used by version 2.2 (removed silently when updating)
OLD_INNO_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{80FBE274-847C-44D6-992B-830503FB751A}_is1"
DATA_DIR_NAME = "EnigmaTimer"

IS_WIN = sys.platform.startswith("win")
NO_WINDOW = 0x08000000 if IS_WIN else 0


def resource(name):
    """Path of a file bundled with the setup (PyInstaller) or next to this script."""
    base = getattr(sys, "_MEIPASS", None)
    if base and os.path.exists(os.path.join(base, name)):
        return os.path.join(base, name)
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, name), os.path.join(here, "build", name),
                 os.path.join(here, "..", "assets", name)):
        if os.path.exists(cand):
            return cand
    return os.path.join(here, name)


def payload_info(path=None):
    """(version, total_uncompressed_bytes) of the bundled program."""
    path = path or resource("payload.zip")
    version = "?"
    total = 0
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            total += info.file_size
        if "payload.json" in z.namelist():
            version = json.loads(z.read("payload.json").decode("utf-8")).get("version", "?")
    return version, total


def default_install_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", APP_NAME)


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, DATA_DIR_NAME)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def _winreg():
    if not IS_WIN:
        return None
    import winreg  # noqa: WPS433 - Windows only
    return winreg


def _registered_installs():
    """Read each registration independently; never mix different copies."""
    wr = _winreg()
    if wr is None:
        return []
    results = []
    for key in (REG_KEY, OLD_INNO_KEY):
        for hive in (wr.HKEY_CURRENT_USER, wr.HKEY_LOCAL_MACHINE):
            for view in dict.fromkeys((0, getattr(wr, "KEY_WOW64_32KEY", 0), getattr(wr, "KEY_WOW64_64KEY", 0))):
                try:
                    with wr.OpenKey(hive, key, 0, wr.KEY_READ | view) as handle:
                        location = wr.QueryValueEx(handle, "InstallLocation")[0]
                        if not isinstance(location, str) or not location.strip():
                            continue
                        found = {"dir": os.path.abspath(location.rstrip("\\/")), "version": ""}
                        try:
                            found["version"] = wr.QueryValueEx(handle, "DisplayVersion")[0]
                        except OSError:
                            pass
                        if key == OLD_INNO_KEY:
                            try:
                                found["inno_uninstall"] = wr.QueryValueEx(handle, "UninstallString")[0]
                            except OSError:
                                pass
                        results.append(found)
                except OSError:
                    continue
    return results


def existing_install(install_dir=None):
    """Recognise the selected app folder even if its registration is missing.

    Registry metadata belongs only to that exact path. Choosing a different
    folder must never invoke another installation's legacy uninstaller.
    """
    registered = _registered_installs()
    if install_dir is not None:
        if not str(install_dir).strip():
            return None
        target = normalise_dir(str(install_dir))
        if not os.path.isfile(os.path.join(target, APP_EXE)):
            return None
        for record in registered:
            if os.path.normcase(os.path.realpath(record["dir"])) == os.path.normcase(os.path.realpath(target)):
                return dict(record, dir=target)
        return {"dir": target, "version": ""}
    for record in registered:
        if os.path.isfile(os.path.join(record["dir"], APP_EXE)):
            return record
    target = default_install_dir()
    if os.path.isfile(os.path.join(target, APP_EXE)):
        return {"dir": target, "version": ""}
    return None


def write_registry(install_dir, version, size_bytes):
    wr = _winreg()
    if wr is None:
        return
    with wr.CreateKey(wr.HKEY_CURRENT_USER, REG_KEY) as k:
        app = os.path.join(install_dir, APP_EXE)
        values = {
            "DisplayName": APP_NAME,
            "DisplayVersion": version,
            "Publisher": PUBLISHER,
            "DisplayIcon": os.path.join(install_dir, APP_EXE),
            "InstallLocation": install_dir,
            "UninstallString": '"%s" --uninstall' % app,
            "QuietUninstallString": '"%s" --uninstall --quiet' % app,
        }
        for name, val in values.items():
            wr.SetValueEx(k, name, 0, wr.REG_SZ, val)
        wr.SetValueEx(k, "EstimatedSize", 0, wr.REG_DWORD, int(size_bytes // 1024))
        wr.SetValueEx(k, "NoModify", 0, wr.REG_DWORD, 1)
        wr.SetValueEx(k, "NoRepair", 0, wr.REG_DWORD, 1)


def remove_registry():
    wr = _winreg()
    if wr is None:
        return
    try:
        wr.DeleteKey(wr.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Shortcuts and processes
# ---------------------------------------------------------------------------

def _powershell(script):
    if not IS_WIN:
        return
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                   creationflags=NO_WINDOW, check=False)


def _ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def create_shortcuts(install_dir, desktop):
    target = os.path.join(install_dir, APP_EXE)
    lines = [
        "$sh = New-Object -ComObject WScript.Shell",
        "$targets = @([Environment]::GetFolderPath('Programs'))",
    ]
    if desktop:
        lines.append("$targets += [Environment]::GetFolderPath('Desktop')")
    lines += [
        "foreach ($d in $targets) {",
        "  $s = $sh.CreateShortcut((Join-Path $d %s))" % _ps_quote(APP_NAME + ".lnk"),
        "  $s.TargetPath = %s" % _ps_quote(target),
        "  $s.WorkingDirectory = %s" % _ps_quote(install_dir),
        "  $s.IconLocation = %s" % _ps_quote(target + ",0"),
        "  $s.Save()",
        "}",
    ]
    _powershell("; ".join(lines))


def remove_shortcuts():
    script = ("foreach ($d in @([Environment]::GetFolderPath('Programs'), "
              "[Environment]::GetFolderPath('Desktop'))) { "
              "$p = Join-Path $d %s; if (Test-Path $p) { Remove-Item $p -Force } }"
              % _ps_quote(APP_NAME + ".lnk"))
    _powershell(script)


def close_running_app():
    """Require an explicit close. Never kill a running timer or solver."""
    if not IS_WIN:
        return
    import csv
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + APP_EXE,
                             '/FO', 'CSV', '/NH'], creationflags=NO_WINDOW,
                            capture_output=True, text=True, check=True)
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) >= 2 and row[0].casefold() == APP_EXE.casefold() and int(row[1]) != os.getpid():
            raise RuntimeError('Close Enigma Cube before changing its installation. Your work has not been interrupted.')


def run_old_uninstaller(cmd):
    """Silently remove the old Inno Setup installation (keeps user data)."""
    if not IS_WIN or not cmd:
        return
    exe = cmd.strip().strip('"')
    if not os.path.exists(exe):
        return
    subprocess.run([exe, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                   creationflags=NO_WINDOW, check=False)


def launch_app(install_dir):
    exe = os.path.join(install_dir, APP_EXE)
    if os.path.exists(exe):
        subprocess.Popen([exe], cwd=install_dir, close_fds=True)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def normalise_dir(path):
    """Never install straight into a shared folder: add "Enigma Cube" to it."""
    path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
    if os.path.basename(path.rstrip("\\/")).lower() != APP_NAME.lower():
        if os.path.isdir(path) and os.listdir(path) and not os.path.exists(
                os.path.join(path, APP_EXE)):
            path = os.path.join(path, APP_NAME)
    return path


def read_manifest(install_dir):
    p = os.path.join(install_dir, MANIFEST)
    if not os.path.exists(p):
        return []
    with io.open(p, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _inside_path(root,relative):
    """Resolve only package-relative paths, including through existing links."""
    relative=relative.replace("\\","/")
    if relative.startswith("/") or ":" in relative or any(p in ("..","") for p in relative.split("/")):
        return None
    root=os.path.realpath(root)
    target=os.path.realpath(os.path.join(root,*relative.split("/")))
    try:
        return target if target!=root and os.path.commonpath((root,target))==root else None
    except ValueError:
        return None


def remove_installed_files(install_dir, progress=None):
    """Delete only files this setup installed (listed in the manifest)."""
    files = [r for r in read_manifest(install_dir) if _inside_path(install_dir,r)]
    total = max(1, len(files))
    for i, rel in enumerate(files):
        p = _inside_path(install_dir,rel)
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
        if progress:
            progress(i + 1, total, rel)
    # remove now-empty folders, deepest first
    dirs = sorted(set(os.path.dirname(os.path.join(install_dir, r)) for r in files),
                  key=len, reverse=True)
    for d in dirs:
        root=os.path.realpath(install_dir)
        while os.path.commonpath((root,os.path.realpath(d)))==root and os.path.realpath(d)!=root:
            try:
                os.rmdir(d)
            except OSError:
                break
            d = os.path.dirname(d)
    try:
        os.remove(os.path.join(install_dir, MANIFEST))
    except OSError:
        pass


def install_files(payload_path, install_dir, progress=None):
    """Stage the complete payload before changing files; roll back on failure."""
    install_dir=os.path.realpath(install_dir)
    parent=os.path.dirname(install_dir)
    os.makedirs(parent,exist_ok=True)
    stage=tempfile.mkdtemp(prefix=".EnigmaCube-update-",dir=parent)
    fresh=os.path.join(stage,"new")
    backup=os.path.join(stage,"backup")
    os.makedirs(fresh)
    os.makedirs(backup)
    preserve_backup=False
    written=[]
    try:
        # CRC/decompression/disk-space failures here leave the old app intact.
        with zipfile.ZipFile(payload_path) as archive:
            members=[m for m in archive.infolist() if not m.is_dir() and m.filename not in ("payload.json",MANIFEST)]
            total=max(1,len(members))
            for index,member in enumerate(members):
                rel=member.filename.replace("\\","/")
                destination=_inside_path(fresh,rel)
                if destination is None:
                    continue
                if rel in written:
                    raise ValueError("Duplicate file in installer payload")
                os.makedirs(os.path.dirname(destination),exist_ok=True)
                with archive.open(member) as source,open(destination,"wb") as output:
                    shutil.copyfileobj(source,output)
                written.append(rel)
                if progress:
                    progress(index+1,total,rel)
        if APP_EXE not in written:
            raise ValueError("Installer payload does not contain the application")
        with io.open(os.path.join(fresh,MANIFEST),"w",encoding="utf-8") as manifest:
            manifest.write("\n".join(written)+"\n")
        old=read_manifest(install_dir)
        backed_up=[]
        deployed=[]
        os.makedirs(install_dir,exist_ok=True)
        try:
            for rel in dict.fromkeys(old+written+[MANIFEST]):
                source=_inside_path(install_dir,rel)
                destination=_inside_path(backup,rel)
                if source is None or destination is None:
                    if rel in written:
                        raise ValueError("Install path points outside the application folder")
                    continue
                if os.path.isfile(source):
                    os.makedirs(os.path.dirname(destination),exist_ok=True)
                    os.replace(source,destination)
                    backed_up.append(rel)
            for rel in written+[MANIFEST]:
                destination=_inside_path(install_dir,rel)
                if destination is None:
                    raise ValueError("Unsafe installer destination")
                os.makedirs(os.path.dirname(destination),exist_ok=True)
                os.replace(_inside_path(fresh,rel),destination)
                deployed.append(rel)
        except Exception:
            # Restore only the paths touched by this transaction. User files
            # outside the manifest remain in place throughout the update.
            try:
                for rel in deployed:
                    path=_inside_path(install_dir,rel)
                    if path and os.path.isfile(path):
                        os.remove(path)
                for rel in backed_up:
                    destination=_inside_path(install_dir,rel)
                    if destination is None:
                        raise ValueError("Unsafe rollback destination")
                    os.makedirs(os.path.dirname(destination),exist_ok=True)
                    os.replace(_inside_path(backup,rel),destination)
            except Exception:
                preserve_backup=True  # retain recoverable originals on disk
            raise
        return written
    finally:
        # The temporary tree was created by us in this exact parent folder.
        # If rollback itself failed, retain its originals for manual recovery.
        if (not preserve_backup and os.path.dirname(os.path.realpath(stage))==parent
                and os.path.basename(stage).startswith(".EnigmaCube-update-")):
            try:
                shutil.rmtree(stage)
            except OSError:
                pass  # a locked temporary file must not undo a completed update


def install(payload_path, install_dir, desktop_shortcut=True, progress=None, existing=None, close_running=True):
    if getattr(sys, 'frozen', False):
        from enigma_timer.hub_link import hub_executable
        if hub_executable() is None:
            raise RuntimeError('Install or update Enigma Hub (1.3.0 or newer) first: https://enigmastudioo.com')
    version, size = payload_info(payload_path)
    if existing and existing.get("inno_uninstall"):
        run_old_uninstaller(existing["inno_uninstall"])
    if close_running:
        close_running_app()
    install_files(payload_path, install_dir, progress)
    create_shortcuts(install_dir, desktop_shortcut)
    write_registry(install_dir, version, size)
    return version


def uninstall(install_dir, delete_data=False, progress=None):
    close_running_app()
    remove_installed_files(install_dir, progress)
    try:
        os.rmdir(install_dir)
    except OSError:
        pass
    remove_shortcuts()
    remove_registry()
    if delete_data and os.path.isdir(data_dir()):
        shutil.rmtree(data_dir(), ignore_errors=True)
