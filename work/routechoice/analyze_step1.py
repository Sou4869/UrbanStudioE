"""Recompute paired route comparisons from source CSVs; preserve repeated choices."""
from pathlib import Path
import ast
import collections
import csv
import heapq
import json
import math
import os
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'datasets/routechoice'
OUT = ROOT / 'outputs/routechoice/step1'
WORK = Path(__file__).resolve().parent
EPS = 1e-8
DIST_EPS = 1e-6
METRICS = ['length_m', 'green_pct', 'sky_pct', 'sidewalk_m', 'crosswalk_links']
DIFFS = ['detour_m', 'detour_pct', 'green_diff_pp', 'sky_diff_pp', 'sidewalk_diff_m', 'crosswalk_diff_links']

def read_csv(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def analyze():
    OUT.mkdir(parents=True, exist_ok=True)
    links = {int(r['fid']): r for r in read_csv('link_kannai.csv')}
    nodes = {int(r['fid']) for r in read_csv('node_kannai.csv')}
    paths = read_csv('path_kannai.csv')
    assert len(links) == 2398 and len(nodes) == 724 and len(paths) == 1280
    adj = collections.defaultdict(list)
    for fid, r in links.items():
        o, d, length = int(r['O']), int(r['D']), float(r['length'])
        assert o in nodes and d in nodes and length > 0
        for k in ['vegetation', 'sky']:
            assert 0 <= float(r[k]) <= 1
        assert float(r['sidewalk_width']) >= 0 and int(r['crosswalk']) in (0, 1)
        adj[o].append((d, length, fid))
    for edges in adj.values():
        edges.sort()

    def shortest_from(origin):
        dist, prev, queue = {origin: 0.0}, {}, [(0.0, origin)]
        while queue:
            cost, u = heapq.heappop(queue)
            if cost > dist[u]:
                continue
            for v, length, fid in adj[u]:
                candidate = cost + length
                if candidate < dist.get(v, math.inf) - 1e-10:
                    dist[v], prev[v] = candidate, (u, fid)
                    heapq.heappush(queue, (candidate, v))
        # Positive edge lengths make the shortest-path subgraph acyclic.
        counts = collections.defaultdict(int, {origin: 1})
        for u in sorted(dist, key=dist.get):
            for v, length, _ in adj[u]:
                if abs(dist[u] + length - dist.get(v, math.inf)) <= 1e-9:
                    counts[v] += counts[u]
        return dist, prev, counts

    def metrics(seq):
        length = math.fsum(float(links[f]['length']) for f in seq)
        result = {'length_m': length}
        for source, target, scale in [('vegetation', 'green_pct', 100), ('sky', 'sky_pct', 100),
                                      ('sidewalk_width', 'sidewalk_m', 1)]:
            result[target] = math.fsum(float(links[f]['length']) * float(links[f][source])
                                      for f in seq) / length * scale
        result['crosswalk_links'] = sum(int(links[f]['crosswalk']) for f in seq)
        return result

    cache, baselines, groups, sequences, rows = {}, {}, collections.defaultdict(list), {}, []
    for p in paths:
        pid, oid, origin, destination = (int(p[k]) for k in ['path_id', 'od_id', 'origin', 'destination'])
        assert pid not in sequences
        seq, ns = ast.literal_eval(p['path by link']), ast.literal_eval(p['path by node'])
        assert len(ns) == len(seq) + 1 and ns[0] == origin and ns[-1] == destination
        assert all(int(links[f]['O']) == ns[i] and int(links[f]['D']) == ns[i+1] for i, f in enumerate(seq))
        sequences[pid] = tuple(seq)
        if origin not in cache:
            cache[origin] = shortest_from(origin)
        if oid not in baselines:
            dist, prev, count = cache[origin]
            assert destination in dist
            u, reverse = destination, []
            while u != origin:
                u, fid = prev[u]
                reverse.append(fid)
            short_seq = reverse[::-1]
            b = metrics(short_seq)
            assert abs(b['length_m'] - dist[destination]) < DIST_EPS
            baselines[oid] = {'origin': origin, 'destination': destination, 'seq': short_seq,
                              'shortest_path_count': count[destination], **b}
        b = baselines[oid]
        assert (origin, destination) == (b['origin'], b['destination'])
        a = metrics(seq)
        detour = a['length_m'] - b['length_m']
        assert detour >= -DIST_EPS
        if abs(detour) < DIST_EPS:
            detour = 0.0
        row = {'path_id': pid, 'od_id': oid, 'origin': origin, 'destination': destination,
               'n_links': len(seq), **a, **{'shortest_'+k: b[k] for k in METRICS},
               'detour_m': detour, 'detour_pct': 100 * detour / b['length_m'],
               'green_diff_pp': a['green_pct'] - b['green_pct'],
               'sky_diff_pp': a['sky_pct'] - b['sky_pct'],
               'sidewalk_diff_m': a['sidewalk_m'] - b['sidewalk_m'],
               'crosswalk_diff_links': a['crosswalk_links'] - b['crosswalk_links'],
               'is_minimum_distance': int(detour == 0),
               'same_as_reference_sequence': int(seq == b['seq']),
               'shortest_path_count': b['shortest_path_count']}
        rows.append(row)
        groups[oid].append(row)
    rows.sort(key=lambda r: r['path_id'])
    assert len(groups) == 64 and all(len(g) == 20 for g in groups.values())
    od_rows = []
    for oid, g in sorted(groups.items()):
        b = baselines[oid]
        r = {'od_id': oid, 'origin': b['origin'], 'destination': b['destination'],
             'n_choices': len(g), 'n_unique_routes': len({sequences[p['path_id']] for p in g}),
             **{'shortest_'+k: b[k] for k in METRICS}, 'shortest_path_count': b['shortest_path_count']}
        for k in METRICS:
            r['mean_chosen_'+k] = float(np.mean([p[k] for p in g]))
        for k in DIFFS:
            values = np.array([p[k] for p in g])
            r['mean_'+k] = float(np.mean(values))
            r['median_'+k] = float(np.median(values))
            r['p90_'+k] = float(np.quantile(values, .9))
        for k in ['green_diff_pp', 'sky_diff_pp', 'sidewalk_diff_m', 'crosswalk_diff_links']:
            vals = [p[k] for p in g]
            for label, predicate in [('higher', lambda x: x > EPS), ('equal', lambda x: abs(x) <= EPS),
                                     ('lower', lambda x: x < -EPS)]:
                n = sum(predicate(x) for x in vals)
                r[k+'_'+label+'_n'] = n
                r[k+'_'+label+'_share_pct'] = n / len(g) * 100
        r['minimum_distance_n'] = sum(p['is_minimum_distance'] for p in g)
        r['minimum_distance_share_pct'] = r['minimum_distance_n'] / len(g) * 100
        od_rows.append(r)
    summary = []
    for k in DIFFS:
        vals = np.array([r[k] for r in rows])
        tol = DIST_EPS if k == 'detour_m' else EPS
        summary.append({'metric': k, 'n': len(vals), 'mean': float(vals.mean()),
                        'median': float(np.median(vals)), 'p25': float(np.quantile(vals, .25)),
                        'p75': float(np.quantile(vals, .75)), 'p90': float(np.quantile(vals, .9)),
                        'min': float(vals.min()), 'max': float(vals.max()),
                        'higher_n': int(sum(vals > tol)), 'equal_n': int(sum(abs(vals) <= tol)),
                        'lower_n': int(sum(vals < -tol)),
                        'higher_share_pct': float(np.mean(vals > tol) * 100),
                        'equal_share_pct': float(np.mean(abs(vals) <= tol) * 100),
                        'lower_share_pct': float(np.mean(vals < -tol) * 100)})
    checks = {'n_choices': len(rows), 'n_od_pairs': len(groups),
              'n_unique_sequences': len(set(sequences.values())),
              'n_od_with_tied_shortest': sum(b['shortest_path_count'] > 1 for b in baselines.values()),
              'n_minimum_distance_choices': sum(r['is_minimum_distance'] for r in rows),
              'n_od_positive_mean_green': sum(r['mean_green_diff_pp'] > EPS for r in od_rows),
              'n_od_negative_mean_green': sum(r['mean_green_diff_pp'] < -EPS for r in od_rows),
              'n_od_positive_mean_sky': sum(r['mean_sky_diff_pp'] > EPS for r in od_rows)}
    assert checks['n_unique_sequences'] == 677
    # Reconcile against the independently generated existing map analysis.
    previous = json.loads((WORK / 'summary.json').read_text())['all_choices_mean']
    for k in ['length_m', 'detour_m', 'green_pct', 'sky_pct', 'green_diff_pp', 'sky_diff_pp']:
        assert abs(float(np.mean([r[k] for r in rows])) - previous[k]) < 1e-8, k
    for k in DIFFS:
        assert abs(float(np.mean([r['mean_'+k] for r in od_rows])) -
                   float(np.mean([r[k] for r in rows]))) < 1e-8
    for r in od_rows:
        for k in ['green_diff_pp', 'sky_diff_pp', 'sidewalk_diff_m', 'crosswalk_diff_links']:
            assert sum(r[k+'_'+x+'_n'] for x in ['higher', 'equal', 'lower']) == r['n_choices']
    payload = {'routes': rows, 'ods': od_rows, 'summary': summary, 'checks': checks,
               'shortest_routes': [{'od_id': oid, **b} for oid, b in sorted(baselines.items())]}
    (WORK / 'step1_analysis.json').write_text(json.dumps(payload, indent=2))
    write_csv('route_comparisons.csv', rows)
    write_csv('od_summary.csv', od_rows)
    write_csv('overall_summary.csv', summary)
    (OUT / 'README.txt').write_text(
        'KANNAI ROUTE CHOICE - STEP 1\n\n'
        'Sources: datasets/routechoice/link_kannai.csv, node_kannai.csv, path_kannai.csv.\n'
        'Synthetic classroom choices: 1,280 records, 64 OD pairs, 20 choices per OD.\n'
        'Repeated paths retain their observed frequencies; 677 distinct sequences.\n\n'
        'METHOD\n'
        'Recompute shortest paths on the directed O/D network using supplied link lengths (metres).\n'
        'The deterministic reference sorts outgoing links by destination, length and link ID.\n'
        'Shortest-path ties are counted within 1e-9 m; each OD has one stored reference sequence.\n'
        'Chosen and reference routes use direction-specific link attributes.\n'
        'Distance is the sum of link lengths. Green, sky and sidewalk are length-weighted averages.\n'
        'Crosswalk count is the sum of crosswalk indicators: link traversals, not distinct intersections.\n'
        'Every difference is chosen minus shortest. Green and sky differences use percentage points.\n'
        'Detour (%) = 100 * (chosen length - shortest length) / shortest length.\n'
        'Overall detour (%) is the mean of individual ratios, not a ratio of total lengths.\n'
        'Higher/equal/lower classify differences with tolerance 1e-8; distance equality uses 1e-6 m.\n'
        'All 20 choices form each OD percentage denominator, including equal/reference choices.\n'
        'Quantiles use NumPy linear interpolation. Each choice has equal weight.\n'
        'Because each OD has 20 choices, overall means also equal equally weighted OD means.\n\n'
        'FILES\n'
        'kannai_step1.xlsx: summary, OD comparisons and route-level calculations.\n'
        'route_comparisons.csv: all 1,280 paired comparisons.\n'
        'od_summary.csv: all 64 OD summaries, including distribution quantiles and sign counts.\n'
        'overall_summary.csv: distributions and higher/equal/lower shares across choices.\n'
        '05_step1_overview.png: distributions and paired-difference shares.\n'
        '06_step1_by_od.png: all 64 OD pairs; row order is ascending OD ID.\n\n'
        'INTERPRETATION\n'
        'These are descriptive comparisons with a shortest-distance reference, not estimates of preference or causal effects.\n'
        'OD 56 is illustrative; use the full 64-OD summaries to assess generality.\n'
        'Raw sources and earlier map/QGIS outputs are unchanged.\n\n'
        'REPRODUCE (from the UStudio project directory)\n'
        'python3 work/routechoice/analyze_step1.py\n'
        'python3 work/routechoice/analyze_step1.py --plot\n'
        'node work/routechoice/build_step1_workbook.mjs\n'
        'Analysis requires NumPy. Plotting additionally requires Matplotlib.\n'
        'The workbook builder requires @oai/artifact-tool, supplied by the Codex bundled Node runtime.\n'
        'The script paths resolve sources relative to the project, independent of working directory.\n', encoding='utf-8')
    print(json.dumps({'checks': checks, 'summary': summary}, indent=2))

def plot():
    os.environ['MPLCONFIGDIR'] = str(WORK / 'mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    p = json.loads((WORK / 'step1_analysis.json').read_text())
    rows, ods = p['routes'], p['ods']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'savefig.facecolor': '#fafbf8'})
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), facecolor='#fafbf8')
    for ax, field, label in [(axes[0, 0], 'detour_m', 'Additional distance (m)'),
                             (axes[0, 1], 'detour_pct', 'Additional distance (%)')]:
        v = np.array([r[field] for r in rows])
        ax.hist(v, bins=25, color='#487e9b', edgecolor='#fafbf8')
        ax.axvline(np.mean(v), color='#b96327', label=f'Mean {np.mean(v):.2f}', lw=1.8)
        ax.axvline(np.median(v), color='#233b46', ls='--', label=f'Median {np.median(v):.2f}', lw=1.8)
        ax.set(xlabel=label, ylabel='Number of choices', title=label)
        ax.legend(frameon=False)
    ax = axes[1, 0]
    keys = ['green_diff_pp', 'sky_diff_pp', 'sidewalk_diff_m', 'crosswalk_diff_links']
    labels = ['Green view', 'Sky view', 'Sidewalk width', 'Crosswalk links']
    left = np.zeros(4)
    for category, color in [('lower', '#bd7061'), ('equal', '#d0d6d5'), ('higher', '#397b61')]:
        values = [next(r[category+'_share_pct'] for r in p['summary'] if r['metric'] == key) for key in keys]
        ax.barh(labels, values, left=left, color=color, label=category.title())
        for y, (value, start) in enumerate(zip(values, left)):
            if value >= 10:
                ax.text(start + value/2, y, f'{value:.1f}%', ha='center', va='center',
                        color='white' if category != 'equal' else '#233b46', fontsize=9)
        left += np.array(values)
    ax.invert_yaxis(); ax.set(xlim=(0, 100), xlabel='Share of all 1,280 choices (%)', title='Chosen versus shortest route')
    ax.legend(frameon=False, ncol=3, loc='upper center', bbox_to_anchor=(.5, -.18))
    ax = axes[1, 1]
    bins = np.arange(-12, 18, 1)
    ax.hist([r['green_diff_pp'] for r in rows], bins=bins, color='#397b61', alpha=.65, label='Green view')
    ax.hist([r['sky_diff_pp'] for r in rows], bins=bins, histtype='step', linewidth=2, color='#397caa', label='Sky view')
    ax.axvline(0, color='#233b46', lw=.8)
    ax.set(xlabel='Chosen minus shortest (percentage points)', ylabel='Number of choices', title='Visibility differences')
    ax.legend(frameon=False)
    fig.suptitle('Kannai route choice: paired comparison with shortest routes', x=.07, ha='left', fontsize=19, weight='bold', color='#183a31')
    fig.text(.07, .925, '1,280 synthetic choices across 64 OD pairs; repeated choices retain their frequencies.', color='#52665d')
    fig.subplots_adjust(left=.12, right=.97, top=.85, bottom=.16, hspace=.48, wspace=.3)
    fig.text(.07, .04, 'Visibility and sidewalk width are length-weighted. Comparisons are descriptive; no preference model has been estimated.', fontsize=9, color='#52665d')
    fig.savefig(OUT / '05_step1_overview.png', dpi=190); plt.close(fig)
    fig, axes = plt.subplots(1, 5, figsize=(16, 17), sharey=True, facecolor='#fafbf8')
    y = np.arange(len(ods))
    specs = [('mean_detour_m', 'Mean extra\ndistance (m)', '#487e9b'),
             ('mean_detour_pct', 'Mean extra\ndistance (%)', '#487e9b'),
             ('mean_green_diff_pp', 'Mean green\ndifference (pp)', '#397b61'),
             ('mean_sky_diff_pp', 'Mean sky\ndifference (pp)', '#397caa'),
             ('green_diff_pp_higher_share_pct', 'Choices with\nmore green (%)', '#397b61')]
    for ax, (key, title, color) in zip(axes, specs):
        vals = [r[key] for r in ods]
        ax.barh(y, vals, color=[color if v >= 0 else '#bd7061' for v in vals], height=.72)
        ax.axvline(0, color='#87948a', lw=.8)
        ax.axhspan(55.5, 56.5, color='#d9a75b', alpha=.17, zorder=0)
        ax.set_title(title, fontsize=11, pad=12)
        ax.set_yticks(y)
        ax.grid(axis='x', alpha=.12)
        ax.set_axisbelow(True)
        if key.endswith('share_pct'):
            ax.set_xlim(0, 100)
    axes[0].set_yticklabels([str(r['od_id']) for r in ods], fontsize=8)
    axes[0].set_ylabel('OD pair ID'); axes[0].invert_yaxis()
    fig.suptitle('Every OD pair: distance and visibility differences', x=.06, ha='left', fontsize=21, weight='bold', color='#183a31', y=.98)
    fig.text(.06, .95, '20 choices per OD; differences are chosen minus shortest. Shading marks OD 56.', color='#52665d')
    fig.subplots_adjust(left=.065, right=.985, top=.895, bottom=.065, wspace=.3)
    fig.text(.06, .025, 'Green and sky differences are percentage points (pp). More-green shares include all 20 choices in the denominator.', fontsize=10, color='#52665d')
    fig.savefig(OUT / '06_step1_by_od.png', dpi=170); plt.close(fig)

if __name__ == '__main__':
    plot() if '--plot' in sys.argv else analyze()
