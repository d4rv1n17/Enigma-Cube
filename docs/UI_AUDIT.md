# Desktop UI review

The shared black/yellow/grey/white palette is retained. Common button sizing,
dialog margins, typography roles and bordered 3D stages apply across the app.
Secondary-window headers keep their title separate from fullscreen/pin actions;
toolbars wrap instead of compressing buttons. Restored windows are brought into
the current monitor's work area.

Main-window layouts support 960×640, 1100×710 and 1440×900 logical pixels. At
compact widths the event selector uses the short discipline label with its full
name in a tooltip. Russian notation cards measure their translated captions
again whenever the discipline changes, even without a window resize.

Training uses larger case cards and a complete scrollable inspector on click
when the inline details cannot fit. Achievements adapt their column widths to
the viewport and reserve more room for descriptions. Solve details and physical
cube verification scroll independently of their footer actions. Welcome steps
are resizable and scrollable; orientation setup includes a 3D preview and step
progress. The logo intro's duration and skip policy are unchanged.

`python tools/ui_gallery.py --output .previews/ui-after` renders isolated sample
data without opening or modifying the user's store. On Windows it uses the real
Windows Qt backend so text rendering matches the desktop app. The gallery
contains 100 screen states across English/Russian: main pages at three sizes,
notation disciplines, training/review, settings including updates, welcome
steps, solve details, action search, detached pages, mini timer, live cube,
assistant, move explorer, replay, physical-state verification and orientation.

`report.json` records compressed controls and sibling intersections. The final
run reports zero compressed controls and zero unintended intersections;
notification toasts intentionally overlay the timer. Geometry checks supplement
visual inspection; they cannot establish that every possible OS scale, font,
display arrangement or data set is flawless.

The full suite passes 227 tests. New regressions cover wrapped controls, compact
case inspection, accessible long-scramble actions, small secondary/welcome
windows in both languages and Russian notation captions after puzzle switching.
