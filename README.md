# UrbanStudioE

関内地区の経路選択データを用いた、交通・都市計画の演習プロジェクトです。授業用の合成データを使い、選択された経路と最短経路の違いや、緑の見え方・歩道幅などの街路属性の関係を、PythonとQGISで分析しています。

## 担当範囲

本澤 聡一郎（[Sou4869](https://github.com/Sou4869)）が、分析方針の検討からコード作成、結果の検証、可視化・資料整理まで全体を担当しています。データセットと元のQGISプロジェクトは提供資料を使用しています。

- **分析方針の検討**：選択経路と最短経路を比較する指標を整理し、経路長、緑・空の可視率、歩道幅、横断歩道の通過数を分析対象にしました。
- **アルゴリズムと分析コードの実装**：道路を有向グラフとして扱う最短経路計算、経路長で重み付けした街路属性の集計、OD（出発地・目的地の組）ごとの比較、相関・多重共線性の診断をPythonで実装しています。
- **データと計算結果の検証**：道路・経路データの接続関係や値の範囲を検査し、集計値の照合や別の計算方法との比較を組み込みました。同じ経路が複数回選ばれた頻度を保持しつつ、経路の重複を除いた場合の結果も確認しています。
- **可視化と再実行手順の整備**：地図・グラフ・CSV・Excel形式で結果を整理し、使用データ、計算方法、単位、実行コマンドを記録しています。

開発には生成AIの支援も利用しています。分析方針の決定と、コードの内容・出力結果の確認は自身で行っています。

## 使用技術と主な成果物

Python（NumPy、Matplotlib）、QGIS、JavaScript／Node.jsを使用しています。

- [選択経路と最短経路の比較](work/routechoice/analyze_step1.py)
- [街路属性の相関・多重共線性の分析](work/routechoice/analyze_step2.py)
- [地図・QGIS出力の作成](work/routechoice/build_maps.py)
- [分析結果と図表](outputs/routechoice/)

現時点の成果は、合成データに対する経路比較と記述的な統計分析です。歩行者の選好や因果関係を推定した結果ではありません。以下に、分析結果と再実行方法の詳細を記載します。

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

