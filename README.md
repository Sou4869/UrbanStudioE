# UrbanStudioE

Kannai route-choice data, QGIS projects, and reproducible analyses for Transportation and Urban Studio E.

## Project structure

- `datasets/routechoice/`: source CSVs, dataset descriptions, and GIS layers for the Kannai route-choice case study.
- `TU_StudioE_QGISProject.qgz`: the original QGIS project.
- `work/routechoice/`: route-choice analysis scripts and intermediate data.
- `outputs/routechoice/`: Kannai visibility maps, route comparisons, a GeoPackage, and a QGIS project.
- `outputs/routechoice/step1/`: comparisons of all chosen routes with their corresponding shortest routes, summarized by OD pair.
- `outputs/routechoice/step2/`: Pearson/Spearman correlations, variable-quality checks, and collinearity diagnostics.

## Kannai route-choice analysis

The dataset contains 1,280 synthetic choices across 64 origin-destination pairs, with 20 choices per pair and 677 distinct route sequences. Repeated routes retain their choice frequencies.

Step 1 recomputes shortest-distance routes on the directed network using the supplied link lengths. It compares distance, visible vegetation, visible sky, sidewalk width, and crosswalk-link traversals. Visibility and sidewalk width are length-weighted route averages. Every difference is chosen minus shortest.

| Measure | Mean difference | Median difference |
| --- | ---: | ---: |
| Distance | +19.90 m | +6.90 m |
| Distance relative to shortest | +3.26% | +0.68% |
| Green visibility | +0.94 percentage points | +0.24 percentage points |
| Sky visibility | +0.29 percentage points | +0.10 percentage points |
| Sidewalk width | +0.28 m | +0.05 m |
| Crosswalk-link count | +0.15 | 0 |

Of all choices, 57.5% have higher greenery than the shortest route, 31.1% have lower greenery, and 11.4% have equal greenery. Mean greenery is higher for 42 of 64 OD pairs. These are descriptive results from synthetic choices, not estimates of causal effects or pedestrian preferences.

## Reproduce Step 1

Run from the repository root with Python 3, NumPy, and Matplotlib:

```sh
python3 work/routechoice/analyze_step1.py
python3 work/routechoice/analyze_step1.py --plot
```

The first command reads the source CSVs and exports the detailed comparison tables and analysis JSON. The second creates the overview and OD comparison figures. Methods, units, tolerances, and output definitions are documented in `outputs/routechoice/step1/README.txt`.

The optional Excel workbook builder uses Node.js and `@oai/artifact-tool`, supplied through the Codex bundled runtime:

```sh
node work/routechoice/build_step1_workbook.mjs
```

Make that package available to Node before running the builder. The local `node_modules` link is machine-specific and is excluded from Git. The exported workbook is included in the repository and can be opened without the authoring runtime.

`work/routechoice/build_maps.py` creates the map and QGIS outputs and requires the QGIS Python environment. Its QGIS application location is configured for macOS QGIS-LTR; adjust it for another installation.

## Step 2: variable overlap

Step 2 compares street attributes across 1,199 physical segments, 2,398 directed links, all 1,280 chosen routes, and variation within each OD pair. It also checks link-additive exposures for model preparation and repeats the core collinearity check with equal weights on the 677 distinct routes.

Greenery and sidewalk width correlate strongly across pooled chosen routes (Pearson r = 0.804), but less strongly after removing each OD mean (r = 0.494). Green and sky visibility have a within-OD correlation of 0.151. Building visibility overlaps strongly with greenery (within-OD r = -0.810).

For the five core additive attributes (distance, sidewalk exposure, crosswalk count, green exposure, and sky exposure), within-OD VIFs range from 1.175 to 1.335. The distinct-route sensitivity yields VIFs from 1.220 to 1.290. Retain these five attributes for the first model sequence and test building visibility in a separate sensitivity specification. No raw variables are removed.

These are descriptive diagnostics on chosen routes. They do not establish preference, causation, or identification of a future model over all feasible alternatives. Inspect the actual estimation design again in Step 3.

```sh
python3 work/routechoice/analyze_step2.py
python3 work/routechoice/analyze_step2.py --plot
node work/routechoice/build_step2_workbook.mjs
```

Dependencies are the same as for Step 1. Methods, exposure units, screening flags, and source references are documented in `outputs/routechoice/step2/README.txt`. The Excel workbook is a snapshot of the Python calculations.

## Source material

Consult the dataset description in `datasets/routechoice/` for provenance and interpretation. Referenced papers and datasets retain their original authorship and applicable terms.

Local dependencies, caches, temporary inspection files, and operating-system metadata are excluded through `.gitignore`. Analysis results are tracked alongside the code.
