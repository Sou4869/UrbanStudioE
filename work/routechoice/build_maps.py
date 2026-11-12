"""Build reproducible Kannai visibility maps and a separate QGIS project."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/routechoice'
WORK = ROOT / 'work/routechoice'
APP = Path('/Applications/QGIS-LTR.app/Contents')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('PROJ_DATA', str(APP / 'Resources/qgis/proj'))
os.environ.setdefault('MPLCONFIGDIR', str(WORK / 'mpl'))
os.environ.setdefault('GDAL_DATA', str(APP / 'Resources/qgis/gdal'))
os.environ.setdefault('OGR_SQLITE_JOURNAL', 'DELETE')
os.environ.setdefault('SQLITE_TMPDIR', str(WORK))
OUT.mkdir(parents=True, exist_ok=True)

import ast
import collections
import csv
import heapq
import json
import math
import statistics
import sqlite3
import numpy as np
from qgis.core import (
    QgsApplication, QgsProject, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsVectorLayer,
    QgsField, QgsFeature, QgsVectorFileWriter, QgsLineSymbol,
    QgsRendererRange, QgsGraduatedSymbolRenderer, QgsMarkerSymbol,
    QgsSingleSymbolRenderer, QgsLayerTreeModel, QgsMapThemeCollection,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QVariant

app = QgsApplication([], False)
app.setPrefixPath(str(APP / 'MacOS'), True)
app.setPkgDataPath(str(APP / 'Resources/qgis'))
app.setPluginPath(str(APP / 'PlugIns/qgis'))
app.initQgis()
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.titleweight': 'bold', 'savefig.facecolor': '#fafbf8'})

DATA = ROOT / 'datasets/routechoice'
def read_csv(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

links = read_csv('link_kannai.csv')
nodes = read_csv('node_kannai.csv')
paths = read_csv('path_kannai.csv')
by = {int(r['fid']): r for r in links}
assert len(by) == len(links) == 2398
project = QgsProject.instance()
crs_geo = QgsCoordinateReferenceSystem('EPSG:4326')
crs_map = QgsCoordinateReferenceSystem('EPSG:6677')
assert crs_geo.isValid() and crs_map.isValid()
transform = QgsCoordinateTransform(crs_geo, crs_map, project)
node_points = {int(r['fid']): QgsGeometry.fromWkt(r['WKT']).asPoint() for r in nodes}
coords = {}
xy = {}
for fid, r in by.items():
    points = QgsGeometry.fromWkt(r['WKT']).asPolyline()
    origin = node_points[int(r['O'])]
    if points[0].sqrDist(origin) > points[-1].sqrDist(origin):
        points = points[::-1]
    coords[fid] = [(float(p.x()), float(p.y())) for p in points]
    xy[fid] = [(q.x(), q.y()) for q in (transform.transform(p) for p in points)]

adj = collections.defaultdict(list)
for fid, r in by.items():
    adj[int(r['O'])].append((int(r['D']), float(r['length']), fid))
for edges in adj.values():
    edges.sort()

def shortest_from(origin):
    dist, prev, queue = {origin: 0.}, {}, [(0., origin)]
    while queue:
        length, u = heapq.heappop(queue)
        if length > dist[u]:
            continue
        for v, cost, fid in adj[u]:
            candidate = length + cost
            if candidate < dist.get(v, math.inf) - 1e-10:
                dist[v], prev[v] = candidate, (u, fid)
                heapq.heappush(queue, (candidate, v))
    return dist, prev

cache, od_shortest = {}, {}
usage = collections.Counter()
route_rows = []
route_sequences = {}
groups = collections.defaultdict(list)

def metrics(seq):
    length = sum(float(by[f]['length']) for f in seq)
    result = {'length_m': length}
    for column, name, scale in [('vegetation', 'green_pct', 100),
                                 ('sky', 'sky_pct', 100),
                                 ('sidewalk_width', 'sidewalk_m', 1)]:
        result[name] = sum(float(by[f]['length']) * float(by[f][column])
                           for f in seq) / length * scale
    result['crosswalk_links'] = sum(int(float(by[f]['crosswalk'])) for f in seq)
    return result

for row in paths:
    pid, oid = int(row['path_id']), int(row['od_id'])
    o, d = int(row['origin']), int(row['destination'])
    seq = ast.literal_eval(row['path by link'])
    ns = ast.literal_eval(row['path by node'])
    assert len(ns) == len(seq) + 1 and ns[0] == o and ns[-1] == d
    assert all(int(by[f]['O']) == ns[j] and int(by[f]['D']) == ns[j+1]
               for j, f in enumerate(seq))
    if o not in cache:
        cache[o] = shortest_from(o)
    if oid not in od_shortest:
        dist, prev = cache[o]
        assert d in dist
        u, reverse = d, []
        while u != o:
            u, fid = prev[u]
            reverse.append(fid)
        od_shortest[oid] = reverse[::-1]
        assert abs(metrics(reverse)['length_m'] - dist[d]) < 1e-7
    a, b = metrics(seq), metrics(od_shortest[oid])
    assert a['length_m'] >= b['length_m'] - 1e-6
    result = {'path_id': pid, 'od_id': oid, 'origin': o, 'destination': d, **a,
              'shortest_m': b['length_m'], 'detour_m': a['length_m'] - b['length_m'],
              'green_diff_pp': a['green_pct'] - b['green_pct'],
              'sky_diff_pp': a['sky_pct'] - b['sky_pct']}
    route_rows.append(result)
    route_sequences[pid] = seq
    groups[oid].append(result)
    usage.update(seq)
assert len(groups) == 64 and all(len(rows) == 20 for rows in groups.values())

# A transparent illustrative case: OD 56; the unique modal route is used.
selected_od = 56
counter = collections.Counter(tuple(route_sequences[r['path_id']]) for r in groups[selected_od])
modal_seq, modal_count = counter.most_common(1)[0]
assert modal_count == 13 and sum(v == modal_count for v in counter.values()) == 1
selected = min((r for r in groups[selected_od]
                if tuple(route_sequences[r['path_id']]) == modal_seq), key=lambda r: r['path_id'])
chosen_seq = list(modal_seq)
short_seq = od_shortest[selected_od]
chosen_metrics, short_metrics = metrics(chosen_seq), metrics(short_seq)

# Display each physical geometry once, averaging opposite-direction attributes.
physical = collections.defaultdict(list)
for fid in by:
    p = tuple(coords[fid])
    physical[min(p, p[::-1])].append(fid)
assert len(physical) == 1199 and all(len(v) == 2 for v in physical.values())
display = []
for segment_id, (points, fids) in enumerate(sorted(physical.items())):
    first = fids[0]
    display.append({'segment_id': segment_id, 'link_ids': ','.join(map(str, fids)),
                    'green_pct': statistics.mean(float(by[f]['vegetation']) * 100 for f in fids),
                    'sky_pct': statistics.mean(float(by[f]['sky']) * 100 for f in fids),
                    'n_directions': len(fids), 'chosen_traversals': sum(usage[f] for f in fids),
                    'points': list(points), 'xy': xy[first]})

def path_points(seq):
    result = []
    for fid in seq:
        points = coords[fid]
        if result:
            assert abs(result[-1][0]-points[0][0]) < 1e-6
            assert abs(result[-1][1]-points[0][1]) < 1e-6
            result.extend(points[1:])
        else:
            result.extend(points)
    return result

def feature(geometry_type, points, properties):
    return {'type': 'Feature', 'geometry': {'type': geometry_type, 'coordinates': points},
            'properties': properties}

def write_geojson(name, features):
    path = WORK / (name + '.geojson')
    path.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}), encoding='utf-8')
    return path

display_file = write_geojson('display_roads', [feature('LineString', r['points'],
                         {k:v for k,v in r.items() if k not in ['points', 'xy']}) for r in display])
links_file = write_geojson('directed_links', [feature('LineString', coords[f],
             {'link_id': f, 'from_node': int(r['O']), 'to_node': int(r['D']),
              'length_m': float(r['length']), 'green_pct': float(r['vegetation'])*100,
              'sky_pct': float(r['sky'])*100, 'sidewalk_m': float(r['sidewalk_width']),
              'crosswalk': int(float(r['crosswalk']))}) for f,r in by.items()])
chosen_file = write_geojson('chosen_routes', [feature('LineString', path_points(route_sequences[r['path_id']]), r)
                                            for r in route_rows])
shortest_file = write_geojson('shortest_routes', [feature('LineString', path_points(seq),
                 {'od_id': oid, 'origin': groups[oid][0]['origin'], 'destination': groups[oid][0]['destination'],
                  **metrics(seq)}) for oid,seq in od_shortest.items()])
endpoints_file = write_geojson('example_endpoints', [feature('Point', [node_points[n].x(), node_points[n].y()],
                 {'label': label, 'node_id': n, 'od_id': selected_od})
                 for label,n in [('O',selected['origin']),('D',selected['destination'])]])

# Save persistent map layers in one GeoPackage.
gpkg = OUT / 'kannai_analysis.gpkg'
if gpkg.exists():
    gpkg.unlink()
input_layers = [('display_roads', display_file), ('directed_links', links_file),
                ('chosen_routes', chosen_file), ('shortest_routes', shortest_file),
                ('example_endpoints', endpoints_file)]
for index, (name, source) in enumerate(input_layers):
    layer = QgsVectorLayer(str(source), name, 'ogr')
    assert layer.isValid(), name
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName, options.layerName = 'GPKG', name
    options.actionOnExistingFile = (QgsVectorFileWriter.CreateOrOverwriteFile if index == 0
                                   else QgsVectorFileWriter.CreateOrOverwriteLayer)
    result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(gpkg), project.transformContext(), options)
    assert result[0] == QgsVectorFileWriter.NoError, result

# Use one portable database file instead of relying on transient WAL sidecars.
with sqlite3.connect(gpkg) as connection:
    connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchall()
    connection.execute('PRAGMA journal_mode=DELETE').fetchall()

green_bins = [0, 5, 10, 20, 30, 60]
sky_bins = [0, 2, 4, 6, 10, 40]
green_colors = ['#d0e1c9', '#a1ce91', '#65af63', '#2d8649', '#0d5330']
sky_colors = ['#d5e5f0', '#a4c9df', '#6aa7cb', '#347cac', '#124f7b']

def layer_from_gpkg(table, name):
    layer = QgsVectorLayer(str(gpkg) + '|layername=' + table, name, 'ogr')
    assert layer.isValid(), name
    return layer

def graduated(layer, field, bins, colors):
    ranges = []
    for low, high, color in zip(bins[:-1], bins[1:], colors):
        symbol = QgsLineSymbol.createSimple({'line_color': color, 'line_width': '0.65'})
        ranges.append(QgsRendererRange(low, high, symbol, f'{low}-{high}%'))
    layer.setRenderer(QgsGraduatedSymbolRenderer(field, ranges))

project.clear()
project.setTitle('Kannai: green view, sky view and route comparison')
project.setCrs(crs_map)
green_layer = layer_from_gpkg('display_roads', 'Green view (%) - opposite directions averaged')
graduated(green_layer, 'green_pct', green_bins, green_colors)
sky_layer = layer_from_gpkg('display_roads', 'Sky view (%) - opposite directions averaged')
graduated(sky_layer, 'sky_pct', sky_bins, sky_colors)
base_layer = layer_from_gpkg('display_roads', 'Road network')
base_layer.renderer().setSymbol(QgsLineSymbol.createSimple({'line_color':'#cbd1cd','line_width':'0.28'}))
directed_layer = layer_from_gpkg('directed_links', 'Directed links (2398) - analysis attributes')
all_routes_layer = layer_from_gpkg('chosen_routes', 'All chosen routes (1280) - filter by od_id')
all_shortest_layer = layer_from_gpkg('shortest_routes', 'Shortest routes for all 64 OD pairs')
selected_layer = layer_from_gpkg('chosen_routes', 'OD 56: modal chosen route (13/20)')
selected_layer.setSubsetString('"path_id" = ' + str(selected['path_id']))
selected_layer.renderer().setSymbol(QgsLineSymbol.createSimple({'line_color':'#1565ae','line_width':'1.1'}))
short_layer = layer_from_gpkg('shortest_routes', 'OD 56: shortest-distance route')
short_layer.setSubsetString('"od_id" = 56')
short_layer.renderer().setSymbol(QgsLineSymbol.createSimple({'line_color':'#d96c25','line_width':'1.8','line_style':'dash'}))
points_layer = layer_from_gpkg('example_endpoints', 'OD 56 endpoints (O=369, D=447)')
points_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({'name':'circle','color':'#293d40','size':'3.0','outline_color':'white'}))
layers = [green_layer, sky_layer, base_layer, directed_layer, all_routes_layer,
          all_shortest_layer, short_layer, selected_layer, points_layer]
for layer in layers:
    project.addMapLayer(layer)
tree = project.layerTreeRoot()
model = QgsLayerTreeModel(tree)
def theme(name, visible):
    for layer in layers:
        tree.findLayer(layer.id()).setItemVisibilityChecked(layer in visible)
    project.mapThemeCollection().insert(name, QgsMapThemeCollection.createThemeFromCurrentState(tree, model))
theme('01 Green view', [green_layer])
theme('02 Sky view', [sky_layer])
theme('03 OD 56 comparison', [base_layer, short_layer, selected_layer, points_layer])
theme('04 All chosen routes', [base_layer, all_routes_layer])
# Default view: full green-view map. Switch themes using the Layers panel.
for layer in layers:
    tree.findLayer(layer.id()).setItemVisibilityChecked(layer == green_layer)
extent = QgsRectangle(base_layer.extent())
extent_transform = QgsCoordinateTransform(crs_geo, crs_map, project)
project.viewSettings().setDefaultViewExtent(__import__('qgis.core', fromlist=['QgsReferencedRectangle']).QgsReferencedRectangle(
    extent_transform.transformBoundingBox(extent), crs_map))
project_path = OUT / 'Kannai_visibility_analysis.qgz'
project.setFileName(str(project_path))
assert project.write()

# Static figures use actual transformed coordinates; route distances use CSV lengths.
all_xy = np.array([p for r in display for p in r['xy']])
full_extent = [all_xy[:,0].min()-45, all_xy[:,0].max()+45,
               all_xy[:,1].min()-45, all_xy[:,1].max()+45]

def setup_map(ax, extent, scale=200):
    ax.set_facecolor('#f1f3ef')
    ax.set_xlim(extent[:2]); ax.set_ylim(extent[2:]); ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color('#d4dbd5')
    x0, x1, y0, y1 = extent
    x = x0 + (x1-x0)*.065; y = y0 + (y1-y0)*.055
    ax.plot([x,x+scale],[y,y], color='#233b38', lw=3, solid_capstyle='butt', zorder=20)
    ax.text(x+scale/2,y+(y1-y0)*.017,f'{scale} m',ha='center',fontsize=8,color='#233b38')
    ax.annotate('Grid N',xy=(.93,.94),xytext=(.93,.83),xycoords='axes fraction',
                ha='center',va='bottom',fontsize=8,color='#233b38',
                arrowprops={'arrowstyle':'-|>','color':'#233b38','lw':1.3})

def thematic(field, bins, colors, title, subtitle, filename):
    values = np.array([r[field] for r in display])
    fig = plt.figure(figsize=(9,10), facecolor='#fafbf8')
    fig.text(.075,.943,title,fontsize=24,weight='bold',color='#183a31')
    fig.text(.075,.913,subtitle,fontsize=10.5,color='#52665d')
    fig.text(.075,.877,f'Mean {values.mean():.2f}%     Median {np.median(values):.2f}%     Maximum {values.max():.2f}%',
             fontsize=11,color='#294c40')
    ax = fig.add_axes([.075,.19,.85,.66])
    cmap = ListedColormap(colors); norm = BoundaryNorm(bins,cmap.N)
    collection = LineCollection([r['xy'] for r in display], array=values,
                                cmap=cmap,norm=norm,linewidths=1.8,capstyle='round')
    ax.add_collection(collection);setup_map(ax,full_extent)
    cax = fig.add_axes([.16,.129,.68,.019])
    bar = fig.colorbar(collection,cax=cax,orientation='horizontal',spacing='uniform',ticks=bins)
    bar.ax.tick_params(labelsize=9);bar.set_label('Visible image fraction (%)',fontsize=10,labelpad=7)
    fig.text(.075,.065,'Display: 1,199 road segments; opposite-direction values averaged.',fontsize=8.5,color='#52665d')
    fig.text(.075,.045,'Both visibility maps use the same extent. Color scales differ between maps.',fontsize=8.5,color='#52665d')
    fig.text(.075,.025,'Source: class routechoice dataset | Map CRS: EPSG:6677 | No basemap',fontsize=8,color='#52665d')
    fig.savefig(OUT/filename,dpi=220);plt.close(fig)

thematic('green_pct',green_bins,green_colors,'Green view in Kannai',
         'Vegetation visible in street images | Yokohama, Japan','01_green_view.png')
thematic('sky_pct',sky_bins,sky_colors,'Sky view in Kannai',
         'Sky visible in street images | Image fraction, not geometric sky view factor','02_sky_view.png')

def route_collection(seq, color, linewidth=3, linestyle='solid', **kwargs):
    return LineCollection([xy[f] for f in seq],colors=color,linewidths=linewidth,
                          linestyles=linestyle,capstyle='round',joinstyle='round',**kwargs)

route_xy = np.array([p for fid in set(chosen_seq+short_seq) for p in xy[fid]])
x0,x1=route_xy[:,0].min(),route_xy[:,0].max();y0,y1=route_xy[:,1].min(),route_xy[:,1].max()
pad=max(x1-x0,y1-y0)*.18
route_extent=[x0-pad,x1+pad,y0-pad,y1+pad]
fig=plt.figure(figsize=(12,9),facecolor='#fafbf8')
fig.text(.055,.949,'Chosen route versus shortest route',fontsize=24,weight='bold',color='#183a31')
fig.text(.055,.914,f'Illustrative OD {selected_od}: origin node {selected["origin"]} to destination node {selected["destination"]}',
         fontsize=11,color='#52665d')
fig.text(.055,.884,f'Chosen route: the unique most frequent path, selected {modal_count}/20 times (65%); path_id {selected["path_id"]}.',
         fontsize=10,color='#52665d')
for rect,seq,other,color,title in [([.055,.345,.425,.49],chosen_seq,short_seq,'#1565ae','Chosen route'),
                                   ([.52,.345,.425,.49],short_seq,chosen_seq,'#d96c25','Shortest-distance route')]:
    ax=fig.add_axes(rect)
    ax.add_collection(LineCollection([r['xy'] for r in display],colors='#d5dcd6',linewidths=1.0))
    ax.add_collection(route_collection(other,'#83918a',1.8,'dashed',zorder=3))
    ax.add_collection(route_collection(seq,'white',7,zorder=4))
    ax.add_collection(route_collection(seq,color,4.0,zorder=5))
    setup_map(ax,route_extent,100)
    ax.set_title(title,fontsize=14,color=color,pad=10)
    for label,n,marker,pointcolor in [('O',selected['origin'],'o','#256850'),('D',selected['destination'],'D','#923e49')]:
        p=transform.transform(node_points[n]);ax.scatter([p.x()],[p.y()],s=100,marker=marker,c=pointcolor,
                                                        edgecolors='white',linewidths=1.4,zorder=10)
        ax.annotate(label,(p.x(),p.y()),xytext=(9,7),textcoords='offset points',fontsize=11,weight='bold',
                    color=pointcolor,zorder=11,bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1})
fig.text(.055,.308,'O = origin; D = destination. Dashed grey shows the other route. Both panels use the same extent.',fontsize=9,color='#52665d')
tax=fig.add_axes([.055,.124,.89,.15]);tax.axis('off')
keys=['length_m','green_pct','sky_pct','sidewalk_m','crosswalk_links']
cells=[]
for label,values in [('Chosen',chosen_metrics),('Shortest',short_metrics),
                     ('Difference',{k:chosen_metrics[k]-short_metrics[k] for k in keys})]:
    cells.append([label]+[(f'{values[k]:+.2f}' if label=='Difference' else f'{values[k]:.2f}')
                         if k!='crosswalk_links' else f'{int(values[k]):+d}' if label=='Difference' else str(int(values[k]))
                         for k in keys])
table=tax.table(cellText=cells,colLabels=['Route','Distance (m)','Green (%)','Sky (%)','Sidewalk (m)','Crosswalk links'],
                colWidths=[.15,.18,.16,.16,.17,.18],cellLoc='center',loc='center',bbox=[0,0,1,1])
table.auto_set_font_size(False);table.set_fontsize(10)
for (row,col),cell in table.get_celld().items():
    cell.set_edgecolor('#d9e1d9');cell.set_linewidth(.6)
    cell.set_facecolor('#e6ede5' if row==0 else '#ffffff' if row%2 else '#f1f5ef')
    if row==0:cell.get_text().set_weight('bold')
fig.text(.055,.087,'Visibility and sidewalk width are length-weighted route averages; visibility differences are percentage points.',fontsize=8.5,color='#52665d')
fig.text(.055,.063,'This example was selected to illustrate visible route differences; it is not a representative average of all OD pairs.',fontsize=8.5,color='#52665d')
fig.text(.055,.039,'Source: synthetic classroom paths. Shortest paths minimize supplied link lengths on the directed network.',fontsize=8.5,color='#52665d')
fig.savefig(OUT/'03_route_comparison_OD56.png',dpi=220);plt.close(fig)

# All 1,280 observations remain visible in a companion paired-comparison chart.
fig,axes=plt.subplots(1,2,figsize=(12,5.6),facecolor='#fafbf8')
for ax,field,color,label in [(axes[0],'green_diff_pp','#2d8649','Green view difference (percentage points)'),
                             (axes[1],'sky_diff_pp','#347cac','Sky view difference (percentage points)')]:
    ax.set_facecolor('#f1f3ef')
    ax.scatter([r['detour_m'] for r in route_rows],[r[field] for r in route_rows],
               s=14,c=color,alpha=.23,edgecolors='none',label='Each recorded path')
    ax.axhline(0,color='#87948a',lw=.8);ax.axvline(0,color='#87948a',lw=.8)
    ax.scatter([selected['detour_m']],[selected[field]],s=110,c='#ce6e29',marker='D',
               edgecolors='white',linewidths=1.1,zorder=5,label='OD 56 modal route')
    ax.set_xlabel('Additional distance versus shortest route (m)');ax.set_ylabel(label)
    ax.spines[['top','right']].set_visible(False)
    ax.legend(frameon=False,fontsize=8,loc='upper right')
fig.suptitle('Paired comparison across all chosen paths',fontsize=20,weight='bold',color='#183a31',x=.08,ha='left')
fig.subplots_adjust(left=.08,right=.98,top=.82,bottom=.21,wspace=.25)
fig.text(.08,.89,'1,280 choices across 64 OD pairs; each choice is compared with its own OD shortest route.',fontsize=10,color='#52665d')
fig.text(.08,.08,'Positive values indicate higher visibility on the chosen route. Repeated paths overlap in this plot.',fontsize=9,color='#52665d')
fig.text(.08,.045,'Descriptive comparison of synthetic choices; these differences do not identify causal effects.',fontsize=9,color='#52665d')
fig.savefig(OUT/'04_all_paths_comparison.png',dpi=220);plt.close(fig)

summary={'selected_od':selected_od,'selected_path_id':selected['path_id'],'selected_count':modal_count,
         'chosen':chosen_metrics,'shortest':short_metrics,'n_paths':len(paths),'n_od_pairs':len(groups),
         'n_directed_links':len(links),'n_display_segments':len(display),
         'all_choices_mean':{key:statistics.mean(r[key] for r in route_rows)
                              for key in ['length_m','detour_m','green_pct','sky_pct','green_diff_pp','sky_diff_pp']},
         'mean_detour_m_by_od':{str(oid):statistics.mean(r['detour_m'] for r in rows) for oid,rows in groups.items()},
         'sources':['link_kannai.csv','node_kannai.csv','path_kannai.csv']}
(WORK/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

# Reopen the native project and verify every layer and source count.
verify=QgsProject()
assert verify.read(str(project_path))
assert len(verify.mapLayers())==9
for layer in verify.mapLayers().values():
    assert layer.isValid(), layer.name()
expected={'display_roads':1199,'directed_links':2398,'chosen_routes':1280,'shortest_routes':64,'example_endpoints':2}
for name,count in expected.items():
    check=QgsVectorLayer(str(gpkg)+'|layername='+name,name,'ogr')
    assert check.isValid() and check.featureCount()==count,(name,check.featureCount())
print(json.dumps(summary,indent=2))
print('Validated project:',project_path)
print('Generated PNG figures:',[p.name for p in OUT.glob('*.png')])
# QGIS objects are cleaned up at process exit; avoid plugin unload ordering issues.
