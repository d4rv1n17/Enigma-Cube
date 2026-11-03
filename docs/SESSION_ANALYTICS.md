# Session analytics

The sidebar separates the latest solve and session best into clickable metric
cards. Its average table shows computable windows by default; Show all averages
reveals the remaining windows. The information button explains mo3 and trimmed
averages in the selected language. Session mean remains visible; DNF count and
standard deviation are available in its tooltip. History omits ao5/ao12 columns
until their first complete window, and an unavailable-average cell opens that
solve's details rather than doing nothing.

Click a solve number or time to open its details. Rows are displayed newest
first but retain their original solve index. Click ao5/ao12 to open the
corresponding average breakdown. Right-click penalty and delete actions remain
available. Details show the recorded scramble and its preview, date, raw time,
penalty, comment and replay when telemetry exists. Editing a comment or penalty
is saved with the session; viewing a solve does not generate a new scramble.

The progress chart shows the last 400 solves with their original numbers.
Singles and ao5 use solid lines; ao12 uses a contrasting dashed line. All three
series contribute to the vertical range. Missing averages and DNFs interrupt
lines rather than being plotted as zero. Hover highlights a solve and shows its
times; click opens the same detail card as the history table.

Distribution uses at most eight contiguous, half-open time intervals. Captions
show both endpoints; tooltips explicitly state `start <= time < end`. Counts and
percentages include effective penalized times and exclude DNF. The median and
DNF count are shown separately. Bin count adapts to available height; resizing
does not change the underlying solve values.

Tests cover reversed-row mapping, average actions, comment/penalty persistence,
scramble previews, chart index offsets, ao12 bounds, missing data, DNF exclusion,
bucket coverage and compact render sizes.
