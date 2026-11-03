"""Render the desktop UI with isolated sample data; never uses the user's store.

Run: python tools/ui_gallery.py --output .previews/ui-audit
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")
import argparse
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QLabel, QAbstractButton, QWidget
from main import safe_exit_setup
from enigma_timer import theme, i18n
from enigma_timer.storage import Store
from enigma_timer.stats import Solve
from enigma_timer.window import MainWindow, ASSETS, BleScanDialog
from enigma_timer.dialogs import SettingsDialog, SolveDialog, AboutDialog, WelcomeDialog, TextDialog, CubeFrameDialog
from enigma_timer.sync_dialog import CubeSyncDialog
from enigma_timer.cube_sync import facelets_to_state
from enigma_timer.commands import CommandPalette
from enigma_timer.assistant import SolveAssistantWindow
from enigma_timer.move_explorer import MoveExplorerWindow
from enigma_timer.replay import ReplayDialog
from enigma_timer.fast3 import SOLVED_FACELETS

_KEEP = []


def render_gallery(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    safe_exit_setup()
    app=QApplication.instance() or QApplication([])
    _KEEP.append(app)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())
    app.setProperty("reduceMotion",True)
    report=[]
    def capture(widget,name,size=None):
        if size:
            widget.resize(*size)
        widget.show()
        app.processEvents()
        widget.grab().save(str(output/(name+".png")))
        issues=[]
        for child in widget.findChildren(QAbstractButton):
            if child.isVisibleTo(widget) and child.text() and child.width()+2 < child.minimumSizeHint().width():
                issues.append({"control":child.text(),"width":child.width(),"needed":child.minimumSizeHint().width()})
        overlaps=[]
        children=[c for c in widget.findChildren(QWidget) if c.isVisibleTo(widget) and not c.isWindow()]
        for i, child in enumerate(children):
            for other in children[i+1:]:
                if child.parentWidget() is other.parentWidget() and child.geometry().intersected(other.geometry()).width()>3 and child.geometry().intersected(other.geometry()).height()>3:
                    overlaps.append([type(child).__name__+":"+getattr(child,"text",lambda:child.objectName())()[:50],type(other).__name__+":"+getattr(other,"text",lambda:other.objectName())()[:50]])
        report.append({"screen":name,"size":[widget.width(),widget.height()],"requested":size,"controls":issues,"overlaps":overlaps})
        print(name,widget.width(),widget.height(),"compressed controls",len(issues),flush=True)
    with tempfile.TemporaryDirectory() as folder:
        for language in ("en","ru"):
            i18n.set_language(language)
            store=Store(os.path.join(folder,language+".json"))
            store.settings.update(welcome_seen=True,reduce_motion=True)
            main=MainWindow(store)
            _KEEP.append(main)
            main.session.solves=[Solve(v,scramble="R U R' U' F2 D L2") for v in (62150,3060,2880,45930,30890,40010,35330)]
            main.refresh()
            for size in ((960,640),(1100,710),(1440,900)):
                prefix=language+"_"+str(size[0])+"_"
                for page,name in enumerate(("timer","training","reference","achievements")):
                    main.set_page(page)
                    capture(main,prefix+name,size)
                if size[0] == 1100:
                    main.set_page(2)
                    reference=main.page_widgets[2]
                    for puzzle in ("222","444","777","pyram","skewb","minx","sq1","clock"):
                        reference.show_puzzle("444" if puzzle=="777" else puzzle)
                        if puzzle=="777":
                            reference.cube_notation.set_puzzle("777")
                        capture(main,prefix+"reference_"+puzzle,size)
                main.set_page(1)
                tw=main.training
                tw.select_level("oll")
                tw.content.setCurrentIndex(1)
                tw._update_detail_visibility()
                tw.grid.setCurrentRow(26)
                capture(main,prefix+"training_cases",size)
                tw.train_level()
                tw.trainer.reveal()
                capture(main,prefix+"trainer",size)
                tw.trainer.stop()
                tw._show_overview()
            main.resize(1100,710)
            main.set_page(1)
            tw.select_level("oll")
            tw.content.setCurrentIndex(1)
            tw._update_detail_visibility()
            def inspector(dialog):
                capture(dialog,language+"_case_inspector",(490,650))
                dialog.reject()
                return QDialog.Rejected
            from PyQt5.QtWidgets import QDialog
            with patch.object(QDialog,"exec_",inspector):
                tw._inspect_case(tw.grid.item(26),force=True)
            main.set_page(0)
            settings=SettingsDialog(store.settings,main)
            for tab in range(settings.tabs.count()):
                settings.tabs.setCurrentIndex(tab)
                capture(settings,language+"_settings_"+str(tab),(740,650))
                if tab==2:
                    settings.tabs.widget(tab).verticalScrollBar().setValue(settings.tabs.widget(tab).verticalScrollBar().maximum())
                    capture(settings,language+"_settings_updates")
            settings.close()
            for name,widget in (("solve",SolveDialog(main.session.solves[0],1,2,main)),
                                ("about",AboutDialog(os.path.join(ASSETS,"logo_full.png"),main)),
                                ("commands",CommandPalette(main)),
                                ("welcome",WelcomeDialog(os.path.join(ASSETS,"logo_full.png"),main)),
                                ("average",TextDialog("ao5","1. 12.34\n2. 15.12\n3. 11.24",main))):
                capture(widget,language+"_"+name)
                if name=="welcome":
                    for step in (1,2):
                        widget.pages.setCurrentIndex(step)
                        widget._update_controls()
                        capture(widget,language+"_welcome_"+str(step+1))
                widget.close()
            for kind in ("training","reference","achievements","timer"):
                widget=main.open_window(kind)
                capture(widget,language+"_window_"+kind,(1050,720) if kind!="timer" else (460,330))
                widget.close()
            for name,widget in (("cube",main.open_cube_window()),
                                ("assistant",SolveAssistantWindow(main)),
                                ("move",MoveExplorerWindow(main,"333","R U R'"))):
                capture(widget,language+"_window_"+name,(650,660))
                widget.close()
            solve=Solve(12000)
            solve.telemetry={"initial":SOLVED_FACELETS,"events":[[0,"R"],[500,"R'"]],"verified":True}
            replay=ReplayDialog(solve,main)
            capture(replay,language+"_replay",(650,660))
            replay.close()
            main._raw_ble_state=main.ble_state=facelets_to_state(SOLVED_FACELETS)
            main.ble_profile="std"
            sync=CubeSyncDialog(main)
            capture(sync,language+"_sync",(650,660))
            sync.close()
            frame=CubeFrameDialog(main)
            capture(frame,language+"_orientation",(560,400))
            frame.close()
            class FakeWorker(QObject):
                connected=pyqtSignal(str,str)
                connection_stage=pyqtSignal(str)
                def scan_restart(self): pass
                def scan_stop(self): pass
                def stop(self): pass
                def wait(self,*_): return True
            main.ble=FakeWorker()
            scan=BleScanDialog(main)
            scan.add_device("Gi157084","00:11:22:33:44:55",True)
            capture(scan,language+"_scan")
            scan.close()
            main.ble=None
            main.close()
            app.processEvents()
    (output/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default=".previews/ui-audit")
    args=parser.parse_args()
    try:
        render_gallery(args.output)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)
