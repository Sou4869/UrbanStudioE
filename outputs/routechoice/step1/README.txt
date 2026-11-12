KANNAI ROUTE CHOICE - STEP 1

Sources: datasets/routechoice/link_kannai.csv, node_kannai.csv, path_kannai.csv.
Synthetic classroom choices: 1,280 records, 64 OD pairs, 20 choices per OD.
Repeated paths retain their observed frequencies; 677 distinct sequences.

METHOD
Recompute shortest paths on the directed O/D network using supplied link lengths (metres).
The deterministic reference sorts outgoing links by destination, length and link ID.
Shortest-path ties are counted within 1e-9 m; each OD has one stored reference sequence.
Chosen and reference routes use direction-specific link attributes.
Distance is the sum of link lengths. Green, sky and sidewalk are length-weighted averages.
Crosswalk count is the sum of crosswalk indicators: link traversals, not distinct intersections.
Every difference is chosen minus shortest. Green and sky differences use percentage points.
Detour (%) = 100 * (chosen length - shortest length) / shortest length.
Overall detour (%) is the mean of individual ratios, not a ratio of total lengths.
Higher/equal/lower classify differences with tolerance 1e-8; distance equality uses 1e-6 m.
All 20 choices form each OD percentage denominator, including equal/reference choices.
Quantiles use NumPy linear interpolation. Each choice has equal weight.
Because each OD has 20 choices, overall means also equal equally weighted OD means.

FILES
kannai_step1.xlsx: summary, OD comparisons and route-level calculations.
route_comparisons.csv: all 1,280 paired comparisons.
od_summary.csv: all 64 OD summaries, including distribution quantiles and sign counts.
overall_summary.csv: distributions and higher/equal/lower shares across choices.
05_step1_overview.png: distributions and paired-difference shares.
06_step1_by_od.png: all 64 OD pairs; row order is ascending OD ID.

INTERPRETATION
These are descriptive comparisons with a shortest-distance reference, not estimates of preference or causal effects.
OD 56 is illustrative; use the full 64-OD summaries to assess generality.
Raw sources and earlier map/QGIS outputs are unchanged.

REPRODUCE (from the UStudio project directory)
python3 work/routechoice/analyze_step1.py
python3 work/routechoice/analyze_step1.py --plot
node work/routechoice/build_step1_workbook.mjs
Analysis requires NumPy. Plotting additionally requires Matplotlib.
The workbook builder requires @oai/artifact-tool, supplied by the Codex bundled Node runtime.
The script paths resolve sources relative to the project, independent of working directory.
