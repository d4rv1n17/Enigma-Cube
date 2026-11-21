"""Enigma ecosystem launch hand-off; no account or internet required."""
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


def hub_executable():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Uninstall\EnigmaHub') as key:
            folder = winreg.QueryValueEx(key, 'InstallLocation')[0]
        exe = Path(folder) / 'EnigmaHub.exe'
        if supported_hub(exe):
            return exe
    except OSError:
        pass
    exe = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Enigma Hub/EnigmaHub.exe'
    return exe if supported_hub(exe) else None


def supported_hub(exe):
    try:
        marker = json.loads((exe.parent / '.enigma-hub-install.json').read_text(encoding='utf-8'))
        parts = tuple(int(v) for v in marker['version'].split('.'))
        return exe.is_file() and marker.get('product') == 'Enigma Hub' and parts >= (1, 3, 0)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def open_hub(action='open'):
    exe = hub_executable()
    if exe is None:
        raise FileNotFoundError('Install or update Enigma Hub (1.3.0 or newer): https://enigmastudioo.com')
    subprocess.Popen([str(exe), '--product', 'cube', '--action', action,
                      '--product-exe', str(Path(sys.executable).resolve())], cwd=str(exe.parent))


def claim_launch():
    endpoint = os.environ.pop('ENIGMA_HUB_ENDPOINT', '')
    ticket = os.environ.pop('ENIGMA_HUB_TICKET', '')
    try:
        parsed = urlsplit(endpoint)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or
                not parsed.port or parsed.path != '/claim' or parsed.query or
                parsed.fragment or parsed.username or parsed.password or not ticket):
            return False
        request = Request(endpoint, data=json.dumps({'product': 'cube', 'ticket': ticket}).encode(),
                          headers={'Content-Type': 'application/json'}, method='POST')
        # A proxy must never receive a local launch ticket.
        with build_opener(ProxyHandler({})).open(request, timeout=3) as response:
            return response.status == 200
    except (ValueError, OSError):
        return False


def ensure_launch():
    if not getattr(sys, 'frozen', False):
        return True  # Source development and tests don't depend on an installed Hub.
    if claim_launch():
        return True
    try:
        open_hub('launch')
    except OSError:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,
            'Enigma Cube is part of Enigma Hub.\nInstall or restore Enigma Hub, then launch Cube again.\n\nhttps://enigmastudioo.com',
            'Enigma Hub required', 0x40)
    return False
