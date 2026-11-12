KANNAI VISIBILITY MAPS AND ROUTE COMPARISON
Prepared for the classroom route-choice project, 12 November 2026.

FILES
01_green_view.png: map of vegetation visible in street images.
02_sky_view.png: map of sky visible in street images.
03_route_comparison_OD56.png: modal chosen route versus shortest route.
04_all_paths_comparison.png: paired comparison of all 1,280 choices.
00_visibility_maps.png: side-by-side preview of the two visibility maps.
Kannai_visibility_analysis.qgz: native QGIS project.
kannai_analysis.gpkg: all persistent layers used by the QGIS project.

QGIS
Keep the .qgz and .gpkg files in the same directory, then open the .qgz.
The project uses relative paths and does not require the original data folder.
Choose a map theme in the Layers panel:
  01 Green view
  02 Sky view
  03 OD 56 comparison
  04 All chosen routes
For a close-up of OD 56, use Zoom to Layer on its selected-route layer.
The all-chosen-routes layer contains route characteristics and paired differences;
filter on od_id to explore any of the 64 OD pairs.

METHOD
Inputs: datasets/routechoice/link_kannai.csv, node_kannai.csv and path_kannai.csv.
Links were matched using fid; paths retain their original path_id and od_id.
All recorded link directions and path connectivity were checked.
Shortest paths minimize the supplied length field on the directed network,
using Dijkstra's algorithm. There are 64 OD pairs, each with 20 choices.
Route visibility and sidewalk width are weighted by supplied link length.
Crosswalk links are counted, rather than counting unique physical crossings.
Repeated chosen paths retain their observation frequencies.

MAP DISPLAY
The two visibility maps use the same extent and EPSG:6677 coordinates.
The 2,398 directed links form 1,199 coincident opposite-direction pairs.
Only for the thematic maps, each physical segment is drawn once and its
opposite-direction visibility values are averaged. Route calculations retain
the directed attributes and do not use these display averages.
The mean, median and maximum above each map describe the 1,199 displayed
segments without length weighting. Green and sky maps use different scales.
Sky visibility is an image fraction, not a geometric sky view factor.
No external basemap or street-name data were used in the static figures.

ILLUSTRATIVE EXAMPLE
OD 56: origin node 369 to destination node 447.
The selected chosen path is path_id 1122, the unique modal sequence, recorded
13 out of 20 times (65%) for this OD. This is a frequency of synthetic choices,
not a count of 13 surveyed individuals.

                           Chosen       Shortest       Difference
Distance (m)               780.004       695.486        +84.518
Green view (%)              15.5846        7.5461        +8.0385 pp
Sky view (%)                 7.9755        6.9392        +1.0364 pp
Sidewalk width (m)           4.2216        1.3079        +2.9138
Crosswalk links              0             0             0

This OD was selected as an illustrative case with visible route differences.
It is not a representative average of the 64 OD pairs.

ALL-CHOICE COMPARISON
Across all 1,280 choices, the mean chosen-minus-shortest differences are:
  Additional distance: +19.9040 m
  Green visibility:    +0.9407 percentage points
  Sky visibility:      +0.2880 percentage points
Each observation is paired with its own OD shortest path.
In the scatterplots, repeated identical observations overlap.

INTERPRETATION
The supplied paths are synthetic, generated from a model estimated from real
observations. These descriptive differences do not demonstrate causal effects
or isolate preferences for greenery and sky: sidewalk width and other road
attributes also differ. Choice-model estimation is the next step.
Use the underlying class data and derived layers within the class-use scope
described in the supplied teaching materials.

VALIDATION
The saved QGIS project was reopened successfully. All nine project layers are
valid. GeoPackage counts: 1,199 display segments, 2,398 directed links,
1,280 chosen routes, 64 shortest routes and two example endpoints.
PNG figures were visually inspected for labels, legends and clipping.
