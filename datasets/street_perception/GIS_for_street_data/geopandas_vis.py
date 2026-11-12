import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
%matplotlib inline
from copy import deepcopy

# %%
areas = ['kiba'] #'kiyosumi',

# %%
# read file
nodes = {area: gpd.read_file(f'data/network/{area}_shp/nodes.shp') for area in areas}
edges = {area: gpd.read_file(f'data/network/{area}_shp/edges_new.shp') for area in areas}
len(edges[areas[0]])

# %%
# read attributes
attributes = {area: pd.read_csv(f'data/network/street_data_{area}.csv') for area in areas}

# %%
# integrate
vis_att_keys = ['incl_prob', 'euclid_dist', 'cos_simil',
                'tree', 'cluster', 'cluster_type',
                'inner_area', 'inner_river_0', 'inner_avenue_0']
vis_atts = {key:[] for key in vis_att_keys}
add_atts = {area: deepcopy(vis_atts) for area in areas}

# %%
for area in areas:
    for i in edges[area].index:
        data = edges[area].loc[i]
        attribute = attributes[area]
        if data['number'] in attribute['street']:
            for key in vis_att_keys:
                add_atts[area][key].append(
                    attribute[attribute['street'] == data['number']][key].values[0]
                )
        else:
            for key in vis_att_keys:
                add_atts[area][key].append(np.nan)

# %%
# check
for key in vis_att_keys:
    print(len(add_atts['kiba'][key]))

# %%
# integrate
for area, edge in edges.items():
    for key in vis_att_keys:
        edge[key] = add_atts[area][key]

# %%
def saveplot(area, key, figsize):
    fig, ax = plt.subplots(figsize=figsize)
    edges[area].plot(column=key, ax=ax, legend=True)
    plt.savefig(f'analysis/figures/{area}_{key}.png')

# %%
sizes = [(8,6), (9,12)]
for key in vis_att_keys:
    for area, size in zip(areas, sizes):
        saveplot(area, key, size)
