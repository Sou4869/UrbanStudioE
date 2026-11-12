KANNAI ROUTE CHOICE - STEP 2

QUESTION
Do the street attributes overlap enough to complicate their separate interpretation?

MAIN RESULTS
Green-sidewalk Pearson r: physical streets 0.443; pooled chosen routes 0.804; within-OD route averages 0.494.
Within-OD green-sky Pearson r: 0.151.
Within-OD building-green Pearson r: -0.810.
Core additive M3 within-OD VIF range: 1.175-1.335.
Distinct-route sensitivity VIF range (677 routes): 1.220-1.290.
Building exposure VIF is 5.224 when all six visual exposures, sidewalk exposure, distance and crosswalks are included.

MODEL INPUT RECOMMENDATION
Retain distance, sidewalk width, crosswalks, greenery and sky for the first model sequence.
M0: distance. M1: add sidewalk and crosswalks. M2: add greenery. M3: add sky.
Do not remove greenery or sidewalk solely because their pooled route averages correlate strongly.
Evaluate building visibility as a separate sensitivity specification, given its overlap with greenery.
Keep wall, fence and terrain for subsequent hypothesis-led sensitivity checks. No raw variable is deleted.
Wall visibility is zero on 657/1,199 physical segments and averages 0.104%: inspect leverage before adding it.

DATA AND AGGREGATION
Sources: datasets/routechoice/link_kannai.csv, node_kannai.csv, path_kannai.csv.
2,398 directed links; 1,199 paired physical segments; 1,280 synthetic chosen routes; 64 OD pairs.
All 20 choices per OD are retained, including repeated routes. No missing numeric inputs were found.
For physical-street diagnostics only, opposite-direction attributes are averaged and each segment has equal weight.
Two segments have direction-specific sidewalk widths (maximum difference 5 m). Directed diagnostics and all route computations retain these differences.
Visual attributes in physical_segment_attributes.csv use percent units (0-100); source CSV fractions are unchanged.
Physical segment length is a link length; route length is a sum. Crosswalk is a link indicator or a route traversal count.
Route visual percentages and sidewalk widths are length-weighted averages.
Within-OD columns subtract the mean across the 20 choices for that OD, separately for each attribute.
Distinct-route sensitivity gives equal weight to each unique (OD, directed-link sequence), then recomputes OD means.
The six image classes sum to 16.77%-98.60% on directed links; they are not normalized to sum to 100%.

ADDITIVE ATTRIBUTES FOR MODEL PREPARATION
L = sum(length_m / 1000), in km.
Visual exposure = sum((length_m / 1000) * visual_fraction), in km of exposure.
Sidewalk exposure = sum((length_m / 1000) * sidewalk_width_m), in km*m.
Crosswalks = sum(crosswalk indicator), in link traversals.
Within-OD demeaning is a diagnostic transformation; it does not replace link utility attributes in an RL model.

STATISTICS
Pearson measures linear association. Spearman correlates average ranks, including ties.
Within-OD Spearman ranks the demeaned observations; it is not a partial rank-correlation estimator.
VIF = 1/(1-R^2), from auxiliary OLS regressions of each standardized attribute on the remaining attributes (intercept implicit after centering).
Also report the rank and condition number of each standardized design matrix.
Absolute Pearson r >= 0.7 and VIF >= 5 are screening flags, not automatic variable-deletion rules.
No p-values are reported: network directions, overlapping routes and repeated sequences do not form independent observations.
Only chosen routes enter these diagnostics. They do not establish identification or numerical stability of a future choice model over all feasible alternatives.
Rerun diagnostics on the actual estimation design and assess standard errors and held-out prediction in Step 3.

OUTPUTS
kannai_step2.xlsx: summary, all Pearson/Spearman matrices, VIF diagnostics, and variable quality.
correlations.csv: all unordered attribute pairs across eight analytical contexts.
vif_diagnostics.csv: ten core/sensitivity specifications, including M1-M3.
variable_quality.csv: counts, zeros, ranges and dispersion.
route_attributes.csv: all route averages, additive exposures and within-OD deviations.
physical_segment_attributes.csv: paired direction-averaged street attributes.
07_step2_correlations.png and 08_step2_green_sidewalk.png: visual summaries.
The workbook is a snapshot of Python calculations; rerun the scripts to refresh all diagnostics.

REPRODUCE (from the repository root)
python3 work/routechoice/analyze_step2.py
python3 work/routechoice/analyze_step2.py --plot
node work/routechoice/build_step2_workbook.mjs
Analysis requires NumPy; plotting also requires Matplotlib. Workbook authoring uses the Codex @oai/artifact-tool runtime.

METHOD REFERENCES
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html
https://www.statsmodels.org/stable/generated/statsmodels.stats.outliers_influence.variance_inflation_factor.html
