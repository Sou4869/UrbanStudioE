"""Descriptive correlation and collinearity diagnostics for Kannai route choice.

Run analysis with NumPy, then use --plot with NumPy and Matplotlib.
No route-choice model or preference coefficient is estimated here.
"""
from pathlib import Path
import ast
import collections
import csv
import json
import math
import os
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'datasets/routechoice'
WORK = Path(__file__).resolve().parent
OUT = ROOT / 'outputs/routechoice/step2'
VISUAL = ['building', 'wall', 'fence', 'vegetation', 'terrain', 'sky']
RAW = ['length', 'sidewalk_width', *VISUAL, 'crosswalk']
AVG = ['length_m', 'sidewalk_m', *[k+'_pct' for k in VISUAL], 'crosswalk_links']
CORE_AVG = ['length_m', 'sidewalk_m', 'crosswalk_links', 'vegetation_pct', 'sky_pct']
ADDITIVE = ['length_km', 'sidewalk_exposure_km_m', 'crosswalk_links', 'vegetation_exposure_km', 'sky_exposure_km']
ALL_ADDITIVE = ['length_km', 'sidewalk_exposure_km_m', 'crosswalk_links', *[k+'_exposure_km' for k in VISUAL]]
TITLES = {
    'physical_links': 'Physical street segments',
    'directed_links': 'Directed network links',
    'routes_pooled': 'Chosen routes: pooled',
    'routes_within_od': 'Chosen routes: within OD',
    'additive_pooled': 'Additive route attributes: pooled',
    'additive_within_od': 'Additive route attributes: within OD',
    'additive_unique_within_od': 'Additive attributes: distinct routes within OD',
    'all_additive_within_od': 'All additive streetscape attributes: within OD',
}
LABELS = dict(zip(RAW, ['Length (m)', 'Sidewalk (m)', 'Building (%)', 'Wall (%)', 'Fence (%)',
                        'Green (%)', 'Terrain (%)', 'Sky (%)', 'Crosswalk']))
LABELS.update(dict(zip(AVG, ['Distance (m)', 'Sidewalk (m)', 'Building (%)', 'Wall (%)', 'Fence (%)',
                             'Green (%)', 'Terrain (%)', 'Sky (%)', 'Crosswalk links'])))
LABELS.update({'length_km': 'Distance (km)', 'sidewalk_exposure_km_m': 'Sidewalk exposure',
               'vegetation_exposure_km': 'Green exposure', 'sky_exposure_km': 'Sky exposure'})
LABELS.update({k+'_exposure_km': ('Green' if k=='vegetation' else k.title())+' exposure' for k in VISUAL})

def read_csv(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def ranks(values):
    """One-based average ranks, including exact ties."""
    order = np.argsort(values, kind='stable')
    sorted_values = values[order]
    boundaries = np.r_[0, np.flatnonzero(sorted_values[1:] != sorted_values[:-1]) + 1, len(values)]
    result = np.empty(len(values), dtype=float)
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        result[order[start:end]] = (start + end + 1) / 2
    return result

def demean(matrix, groups):
    result = matrix.copy()
    for group in sorted(set(groups)):
        mask = groups == group
        result[mask] -= result[mask].mean(axis=0)
        assert np.max(abs(result[mask].mean(axis=0))) < 1e-9
    return result

def correlations(matrix):
    assert np.isfinite(matrix).all()
    assert np.all(matrix.std(axis=0) > 1e-12), 'Constant column: correlation is undefined'
    pearson = np.corrcoef(matrix, rowvar=False)
    spearman = np.corrcoef(np.column_stack([ranks(matrix[:, j]) for j in range(matrix.shape[1])]), rowvar=False)
    # Independent normalized dot-product check of Pearson correlations.
    centered = matrix - matrix.mean(axis=0)
    unit = centered / np.linalg.norm(centered, axis=0)
    assert np.allclose(pearson, unit.T @ unit, atol=1e-10)
    for corr in [pearson, spearman]:
        assert np.allclose(corr, corr.T) and np.allclose(np.diag(corr), 1)
        assert abs(corr).max() <= 1 + 1e-10
    return pearson, spearman

def vif_rows(context, specification, matrix, variables):
    """VIF from centered/standardized auxiliary OLS regressions (intercept implicit)."""
    z = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0)
    rank = int(np.linalg.matrix_rank(z))
    condition = float(np.linalg.cond(z))
    gram = z.T @ z
    inverse = np.linalg.inv(gram) if rank == len(variables) else None
    rows = []
    for j, name in enumerate(variables):
        y = z[:, j]
        x = np.delete(z, j, axis=1)
        residual = y - x @ np.linalg.lstsq(x, y, rcond=None)[0]
        sse, sst = float(residual @ residual), float(y @ y)
        vif = None if sse / sst < 1e-12 else sst / sse
        if inverse is not None and vif is not None:
            assert abs(vif - gram[j, j] * inverse[j, j]) < 1e-7
        rows.append({'context': context, 'specification': specification, 'variable': name,
                     'n_rows': len(matrix), 'n_predictors': len(variables),
                     'vif': vif, 'r_squared_auxiliary': 1 - sse/sst,
                     'screen_vif_ge_5': int(vif is None or vif >= 5),
                     'standardized_design_rank': rank, 'standardized_condition_number': condition})
    return rows

def write_report(payload):
    def pair(context, a, b):
        m=payload['matrices'][context]
        i,j=m['variables'].index(a),m['variables'].index(b)
        return m['pearson'][i][j]
    core=[r for r in payload['vifs'] if r['context']=='additive_within_od' and r['specification']=='M3']
    unique=[r for r in payload['vifs'] if r['context']=='additive_unique_within_od']
    text=(
        'KANNAI ROUTE CHOICE - STEP 2\n\n'
        'QUESTION\nDo the street attributes overlap enough to complicate their separate interpretation?\n\n'
        'MAIN RESULTS\n'
        f"Green-sidewalk Pearson r: physical streets {pair('physical_links','vegetation','sidewalk_width'):.3f}; "
        f"pooled chosen routes {pair('routes_pooled','vegetation_pct','sidewalk_m'):.3f}; "
        f"within-OD route averages {pair('routes_within_od','vegetation_pct','sidewalk_m'):.3f}.\n"
        f"Within-OD green-sky Pearson r: {pair('routes_within_od','vegetation_pct','sky_pct'):.3f}.\n"
        f"Within-OD building-green Pearson r: {pair('routes_within_od','building_pct','vegetation_pct'):.3f}.\n"
        f"Core additive M3 within-OD VIF range: {min(r['vif'] for r in core):.3f}-{max(r['vif'] for r in core):.3f}.\n"
        f"Distinct-route sensitivity VIF range (677 routes): {min(r['vif'] for r in unique):.3f}-{max(r['vif'] for r in unique):.3f}.\n"
        'Building exposure VIF is 5.224 when all six visual exposures, sidewalk exposure, distance and crosswalks are included.\n\n'
        'MODEL INPUT RECOMMENDATION\n'
        'Retain distance, sidewalk width, crosswalks, greenery and sky for the first model sequence.\n'
        'M0: distance. M1: add sidewalk and crosswalks. M2: add greenery. M3: add sky.\n'
        'Do not remove greenery or sidewalk solely because their pooled route averages correlate strongly.\n'
        'Evaluate building visibility as a separate sensitivity specification, given its overlap with greenery.\n'
        'Keep wall, fence and terrain for subsequent hypothesis-led sensitivity checks. No raw variable is deleted.\n'
        'Wall visibility is zero on 657/1,199 physical segments and averages 0.104%: inspect leverage before adding it.\n\n'
        'DATA AND AGGREGATION\n'
        'Sources: datasets/routechoice/link_kannai.csv, node_kannai.csv, path_kannai.csv.\n'
        '2,398 directed links; 1,199 paired physical segments; 1,280 synthetic chosen routes; 64 OD pairs.\n'
        'All 20 choices per OD are retained, including repeated routes. No missing numeric inputs were found.\n'
        'For physical-street diagnostics only, opposite-direction attributes are averaged and each segment has equal weight.\n'
        'Two segments have direction-specific sidewalk widths (maximum difference 5 m). Directed diagnostics and all route computations retain these differences.\n'
        'Visual attributes in physical_segment_attributes.csv use percent units (0-100); source CSV fractions are unchanged.\n'
        'Physical segment length is a link length; route length is a sum. Crosswalk is a link indicator or a route traversal count.\n'
        'Route visual percentages and sidewalk widths are length-weighted averages.\n'
        'Within-OD columns subtract the mean across the 20 choices for that OD, separately for each attribute.\n'
        'Distinct-route sensitivity gives equal weight to each unique (OD, directed-link sequence), then recomputes OD means.\n'
        'The six image classes sum to 16.77%-98.60% on directed links; they are not normalized to sum to 100%.\n\n'
        'ADDITIVE ATTRIBUTES FOR MODEL PREPARATION\n'
        'L = sum(length_m / 1000), in km.\n'
        'Visual exposure = sum((length_m / 1000) * visual_fraction), in km of exposure.\n'
        'Sidewalk exposure = sum((length_m / 1000) * sidewalk_width_m), in km*m.\n'
        'Crosswalks = sum(crosswalk indicator), in link traversals.\n'
        'Within-OD demeaning is a diagnostic transformation; it does not replace link utility attributes in an RL model.\n\n'
        'STATISTICS\n'
        'Pearson measures linear association. Spearman correlates average ranks, including ties.\n'
        'Within-OD Spearman ranks the demeaned observations; it is not a partial rank-correlation estimator.\n'
        'VIF = 1/(1-R^2), from auxiliary OLS regressions of each standardized attribute on the remaining attributes (intercept implicit after centering).\n'
        'Also report the rank and condition number of each standardized design matrix.\n'
        'Absolute Pearson r >= 0.7 and VIF >= 5 are screening flags, not automatic variable-deletion rules.\n'
        'No p-values are reported: network directions, overlapping routes and repeated sequences do not form independent observations.\n'
        'Only chosen routes enter these diagnostics. They do not establish identification or numerical stability of a future choice model over all feasible alternatives.\n'
        'Rerun diagnostics on the actual estimation design and assess standard errors and held-out prediction in Step 3.\n\n'
        'OUTPUTS\n'
        'kannai_step2.xlsx: summary, all Pearson/Spearman matrices, VIF diagnostics, and variable quality.\n'
        'correlations.csv: all unordered attribute pairs across eight analytical contexts.\n'
        'vif_diagnostics.csv: ten core/sensitivity specifications, including M1-M3.\n'
        'variable_quality.csv: counts, zeros, ranges and dispersion.\n'
        'route_attributes.csv: all route averages, additive exposures and within-OD deviations.\n'
        'physical_segment_attributes.csv: paired direction-averaged street attributes.\n'
        '07_step2_correlations.png and 08_step2_green_sidewalk.png: visual summaries.\n'
        'The workbook is a snapshot of Python calculations; rerun the scripts to refresh all diagnostics.\n\n'
        'REPRODUCE (from the repository root)\n'
        'python3 work/routechoice/analyze_step2.py\n'
        'python3 work/routechoice/analyze_step2.py --plot\n'
        'node work/routechoice/build_step2_workbook.mjs\n'
        'Analysis requires NumPy; plotting also requires Matplotlib. Workbook authoring uses the Codex @oai/artifact-tool runtime.\n\n'
        'METHOD REFERENCES\n'
        'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html\n'
        'https://www.statsmodels.org/stable/generated/statsmodels.stats.outliers_influence.variance_inflation_factor.html\n'
    )
    (OUT/'README.txt').write_text(text,encoding='utf-8')

def analyze():
    OUT.mkdir(parents=True, exist_ok=True)
    links, nodes, paths = read_csv('link_kannai.csv'), read_csv('node_kannai.csv'), read_csv('path_kannai.csv')
    by = {int(r['fid']): r for r in links}
    node_ids = {int(r['fid']) for r in nodes}
    assert len(links) == len(by) == 2398 and len(node_ids) == 724 and len(paths) == 1280
    directed = np.array([[float(r[k]) * (100 if k in VISUAL else 1) for k in RAW] for r in links])
    assert np.isfinite(directed).all() and np.all(directed[:, 0] > 0)
    assert np.all((directed[:, 2:8] >= 0) & (directed[:, 2:8] <= 100))
    assert set(directed[:, -1]) == {0, 1}
    physical_groups = collections.defaultdict(list)
    for r in links:
        points = tuple(tuple(map(float, pair.split())) for pair in r['WKT'].removeprefix('LINESTRING (').removesuffix(')').split(','))
        physical_groups[min(points, points[::-1])].append(r)
    assert len(physical_groups) == 1199 and all(len(v) == 2 for v in physical_groups.values())
    segment_rows, physical_values, max_direction_difference = [], [], np.zeros(len(RAW))
    for sid, (_, group) in enumerate(sorted(physical_groups.items())):
        a, b = group
        assert int(a['O']) == int(b['D']) and int(a['D']) == int(b['O'])
        vals = np.array([[float(r[k])*(100 if k in VISUAL else 1) for k in RAW] for r in group])
        mean = vals.mean(axis=0)
        max_direction_difference = np.maximum(max_direction_difference, abs(vals[0]-vals[1]))
        physical_values.append(mean)
        segment_rows.append({'segment_id': sid, 'link_id_1': int(a['fid']), 'link_id_2': int(b['fid']),
                             **{k: float(v) for k, v in zip(RAW, mean)}})
    physical = np.array(physical_values)
    route_rows, route_values, additive_values, group_ids, sequences = [], [], [], [], []
    for p in sorted(paths, key=lambda r: int(r['path_id'])):
        seq, ns = ast.literal_eval(p['path by link']), ast.literal_eval(p['path by node'])
        origin, destination = int(p['origin']), int(p['destination'])
        assert len(ns) == len(seq)+1 and ns[0] == origin and ns[-1] == destination
        assert all(n in node_ids for n in ns)
        assert all(int(by[f]['O']) == ns[i] and int(by[f]['D']) == ns[i+1] for i, f in enumerate(seq))
        lengths = np.array([float(by[f]['length']) for f in seq])
        length = math.fsum(lengths)
        vals = [length, float(np.dot(lengths, [float(by[f]['sidewalk_width']) for f in seq])/length)]
        vals += [float(np.dot(lengths, [float(by[f][k]) for f in seq])/length*100) for k in VISUAL]
        vals += [sum(int(by[f]['crosswalk']) for f in seq)]
        additive = [length/1000, vals[1]*length/1000, vals[-1], vals[5]*length/100000, vals[7]*length/100000]
        # Positions 5 and 7 are vegetation and sky in the AVG ordering.
        assert AVG[5] == 'vegetation_pct' and AVG[7] == 'sky_pct'
        row = {k: int(p[k]) for k in ['path_id', 'od_id', 'origin', 'destination']}
        row.update(dict(zip(AVG, vals)))
        row.update(dict(zip(ADDITIVE, additive)))
        row.update({k+'_exposure_km': vals[AVG.index(k+'_pct')]*length/100000 for k in VISUAL})
        route_rows.append(row)
        route_values.append(vals)
        additive_values.append(additive)
        group_ids.append(int(p['od_id']))
        sequences.append(tuple(seq))
    route, additive, groups = np.array(route_values), np.array(additive_values), np.array(group_ids)
    assert len(set(groups)) == 64 and all(np.sum(groups == g) == 20 for g in set(groups))
    assert len(set(sequences)) == 677
    within, additive_within = demean(route, groups), demean(additive, groups)
    all_additive = np.array([[r[k] for k in ALL_ADDITIVE] for r in route_rows])
    all_additive_within = demean(all_additive, groups)
    unique_indices, seen = [], set()
    for i, seq in enumerate(sequences):
        key = (int(groups[i]), seq)
        if key not in seen:
            unique_indices.append(i)
            seen.add(key)
    assert len(unique_indices) == 677
    unique_groups = groups[unique_indices]
    unique_within = demean(additive[unique_indices], unique_groups)
    for i, r in enumerate(route_rows):
        r.update({'within_od_'+k: float(v) for k, v in zip(AVG, within[i])})
        r.update({'within_od_'+k: float(v) for k, v in zip(ADDITIVE, additive_within[i])})
        r.update({'within_od_'+k: float(v) for k, v in zip(ALL_ADDITIVE, all_additive_within[i])})
    # Validate aggregation against Step 1's independently computed paired-comparison data.
    with (ROOT/'outputs/routechoice/step1/route_comparisons.csv').open(encoding='utf-8-sig', newline='') as f:
        previous = {int(r['path_id']): r for r in csv.DictReader(f)}
    for r in route_rows:
        for old, new in [('length_m','length_m'),('green_pct','vegetation_pct'),('sky_pct','sky_pct'),
                         ('sidewalk_m','sidewalk_m'),('crosswalk_links','crosswalk_links')]:
            assert abs(float(previous[r['path_id']][old]) - r[new]) < 1e-8
    contexts = {
        'physical_links': (physical, RAW), 'directed_links': (directed, RAW),
        'routes_pooled': (route, AVG), 'routes_within_od': (within, AVG),
        'additive_pooled': (additive, ADDITIVE), 'additive_within_od': (additive_within, ADDITIVE),
        'additive_unique_within_od': (unique_within, ADDITIVE),
        'all_additive_within_od': (all_additive_within, ALL_ADDITIVE),
    }
    matrices, pairs = {}, []
    for name, (values, variables) in contexts.items():
        pearson, spearman = correlations(values)
        matrices[name] = {'variables': variables, 'n': len(values), 'pearson': pearson.tolist(), 'spearman': spearman.tolist()}
        for j in range(len(variables)):
            for k in range(j+1, len(variables)):
                pairs.append({'context': name, 'n_rows': len(values), 'variable_1': variables[j], 'variable_2': variables[k],
                              'pearson_r': float(pearson[j,k]), 'spearman_rho': float(spearman[j,k]),
                              'screen_abs_pearson_ge_0_7': int(abs(pearson[j,k]) >= .7)})
    vifs = []
    core_idx = [AVG.index(v) for v in CORE_AVG]
    vifs += vif_rows('physical_links', 'Core averages', physical[:, [RAW.index(v) for v in ['length','sidewalk_width','crosswalk','vegetation','sky']]], ['length','sidewalk_width','crosswalk','vegetation','sky'])
    vifs += vif_rows('directed_links', 'Core averages', directed[:, [RAW.index(v) for v in ['length','sidewalk_width','crosswalk','vegetation','sky']]], ['length','sidewalk_width','crosswalk','vegetation','sky'])
    vifs += vif_rows('routes_within_od', 'Core averages', within[:, core_idx], CORE_AVG)
    vifs += vif_rows('routes_within_od', 'All streetscape averages', within, AVG)
    vifs += vif_rows('additive_pooled', 'M3', additive, ADDITIVE)
    for spec, count in [('M1',3),('M2',4),('M3',5)]:
        vifs += vif_rows('additive_within_od', spec, additive_within[:, :count], ADDITIVE[:count])
    vifs += vif_rows('additive_unique_within_od', 'M3 sensitivity', unique_within, ADDITIVE)
    vifs += vif_rows('all_additive_within_od', 'All streetscape exposures', all_additive_within, ALL_ADDITIVE)
    quality = []
    for context in ['physical_links', 'routes_pooled', 'routes_within_od']:
        values, variables = contexts[context]
        for j, name in enumerate(variables):
            v = values[:, j]
            quality.append({'context':context,'variable':name,'n_rows':len(v),'missing_n':int(np.sum(~np.isfinite(v))),
                            'zero_n':int(np.sum(abs(v) < 1e-12)), 'min':float(v.min()), 'max':float(v.max()),
                            'mean':float(v.mean()), 'sample_sd':float(v.std(ddof=1)),
                            'n_distinct':len(set(v))})
    checks = {'n_directed_links':2398,'n_physical_segments':1199,'n_chosen_routes':1280,
              'n_unique_routes':677,'n_od_pairs':64,'missing_numeric_values':0,
              'max_opposite_direction_difference':dict(zip(RAW,map(float,max_direction_difference))),
              'n_physical_segments_with_different_sidewalk_width':sum(float(g[0]['sidewalk_width']) != float(g[1]['sidewalk_width']) for g in physical_groups.values()),
              'six_visual_classes_sum_min_pct':float(directed[:,2:8].sum(axis=1).min()),
              'six_visual_classes_sum_max_pct':float(directed[:,2:8].sum(axis=1).max())}
    payload = {'matrices':matrices,'pairs':pairs,'vifs':vifs,'quality':quality,'checks':checks,
               'route_inputs':route_rows,'physical_inputs':segment_rows,'labels':LABELS,'titles':TITLES}
    (WORK/'step2_analysis.json').write_text(json.dumps(payload,indent=2,allow_nan=False))
    write_csv('correlations.csv',pairs)
    write_csv('vif_diagnostics.csv',vifs)
    write_csv('variable_quality.csv',quality)
    write_csv('route_attributes.csv',route_rows)
    write_csv('physical_segment_attributes.csv',segment_rows)
    write_report(payload)
    print(json.dumps({'checks':checks,'key_pairs':[r for r in pairs if r['context'] in ['physical_links','routes_pooled','routes_within_od','additive_within_od'] and (('vegetation' in r['variable_1'] and 'sky' in r['variable_2']) or ('sidewalk' in r['variable_1'] and 'vegetation' in r['variable_2']) or ('sidewalk' in r['variable_1'] and 'sky' in r['variable_2']))],
                      'within_od_M3_vifs':[r for r in vifs if r['context']=='additive_within_od' and r['specification']=='M3'],
                      'high_vifs':[r for r in vifs if r['screen_vif_ge_5']]},indent=2))

def plot():
    os.environ['MPLCONFIGDIR'] = str(WORK/'mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    p=json.loads((WORK/'step2_analysis.json').read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'savefig.facecolor':'#fafbf8'})
    fig, axes=plt.subplots(1,3,figsize=(16,6.6),facecolor='#fafbf8')
    specs=[('physical_links',['length','sidewalk_width','crosswalk','vegetation','sky'],
            'Physical streets (n = 1,199)', ['Length','Sidewalk','Crosswalk','Green','Sky']),
           ('routes_within_od',CORE_AVG,'Route averages within OD (n = 1,280)',
            ['Distance','Sidewalk','Crosswalks','Green','Sky']),
           ('additive_within_od',ADDITIVE,'Additive attributes within OD (n = 1,280)',
            ['Distance','Sidewalk exp.','Crosswalks','Green exp.','Sky exp.'])]
    for ax,(context,variables,title,labels) in zip(axes,specs):
        m=p['matrices'][context]
        idx=[m['variables'].index(v) for v in variables]
        corr=np.array(m['pearson'])[np.ix_(idx,idx)]
        im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r')
        ax.set_xticks(range(5),labels,rotation=45,ha='right')
        ax.set_yticks(range(5),labels)
        ax.set_title(title,fontsize=11,pad=15,weight='bold')
        for i in range(5):
            for j in range(5):
                ax.text(j,i,f'{corr[i,j]:.2f}',ha='center',va='center',fontsize=10,
                        color='white' if abs(corr[i,j])>.6 else '#24343e')
    fig.suptitle('Kannai route choice: correlation depends on the analytical level',x=.035,ha='left',fontsize=20,weight='bold',color='#183a31',y=.97)
    fig.text(.035,.90,'Pearson correlations; within-OD values subtract the mean for each group of 20 chosen routes.',color='#52665d')
    fig.subplots_adjust(left=.065,right=.93,top=.79,bottom=.23,wspace=.45)
    cax=fig.add_axes([.947,.29,.012,.43]);fig.colorbar(im,cax=cax,label='Pearson r')
    fig.text(.035,.08,'Exposure = sum of link length (km) x link attribute. Crosswalks count link traversals.',fontsize=10,color='#52665d')
    fig.text(.035,.04,'Synthetic chosen routes provide screening diagnostics; these matrices do not identify preference or causation.',fontsize=10,color='#52665d')
    fig.savefig(OUT/'07_step2_correlations.png',dpi=190);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,5.7),facecolor='#fafbf8')
    specs=[('physical_inputs','vegetation','sidewalk_width','Physical streets','Green visibility (%)','Sidewalk width (m)'),
           ('route_inputs','vegetation_pct','sidewalk_m','Chosen routes: pooled','Green visibility (%)','Average sidewalk width (m)'),
           ('route_inputs','within_od_vegetation_pct','within_od_sidewalk_m','Chosen routes: within OD','Green minus OD mean (pp)','Sidewalk minus OD mean (m)')]
    for ax,(key,xkey,ykey,title,xlabel,ylabel) in zip(axes,specs):
        x=np.array([r[xkey] for r in p[key]]);y=np.array([r[ykey] for r in p[key]])
        corr=float(np.corrcoef(x,y)[0,1])
        ax.scatter(x,y,s=13,alpha=.18,color='#34755f',edgecolors='none')
        if 'within_od' in xkey:
            ax.axhline(0,color='#9eaaa3',lw=.7);ax.axvline(0,color='#9eaaa3',lw=.7)
        ax.set(xlabel=xlabel,ylabel=ylabel,title=f'{title}\nPearson r = {corr:.3f}')
    fig.suptitle('Greenery and sidewalk width',x=.07,ha='left',fontsize=21,weight='bold',color='#183a31')
    fig.subplots_adjust(left=.07,right=.98,top=.78,bottom=.22,wspace=.34)
    fig.text(.07,.08,'1,199 physical segments and 1,280 synthetic chosen routes. Repeated routes overlap in the scatterplots.',fontsize=10,color='#52665d')
    fig.savefig(OUT/'08_step2_green_sidewalk.png',dpi=190);plt.close(fig)

if __name__=='__main__':
    plot() if '--plot' in sys.argv else analyze()
