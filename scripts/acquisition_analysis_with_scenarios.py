# acquisition_analysis_with_scenarios.py
"""
Acquisition funnel analysis (Visits -> Starts) + scenario simulations + chart output.

This script uses the sample data embedded in the repository README and produces CSV outputs
and chart PNGs that the presentation builder consumes. Replace the sample data with your
CSV files (see README_ACQUISITION.md) for full analysis.

Run:
  pip install pandas numpy matplotlib python-pptx openpyxl
  python scripts/acquisition_analysis_with_scenarios.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(exist_ok=True)

# Parameters / assumptions
AVG_REV = 200.0
APPROVAL_RATE = 0.60
UPLIFT_PP = 0.05

# Sample visits data
visits_rows = [
    {'customer_id':101,'visit_date':'2026-05-01','channel':'App','product':'Rewards Card','device_type':'Mobile','campaign_id':'C001','entry_source':'Push','visit_count':3},
    {'customer_id':102,'visit_date':'2026-05-01','channel':'Public','product':'Rewards Card','device_type':'Desktop','campaign_id':'C010','entry_source':'Paid Search','visit_count':1},
    {'customer_id':103,'visit_date':'2026-05-01','channel':'OLB','product':'Balance Transfer','device_type':'Desktop','campaign_id':'C015','entry_source':'Internal Banner','visit_count':2},
    {'customer_id':104,'visit_date':'2026-05-02','channel':'App','product':'Rewards Card','device_type':'Mobile','campaign_id':'C001','entry_source':'Push','visit_count':5},
    {'customer_id':105,'visit_date':'2026-05-02','channel':'Public','product':'Cashback Card','device_type':'Mobile','campaign_id':'C021','entry_source':'Aggregator','visit_count':1},
]
visits_df = pd.DataFrame(visits_rows)
visits_df['visit_date'] = pd.to_datetime(visits_df['visit_date'])

# Sample starts data
starts_rows = [
    {'customer_id':101,'application_id':'A001','start_date':'2026-05-01','product':'Rewards Card','channel':'App','entry_source':'Push','pre_approved_flag':'Y','application_status':'Started'},
    {'customer_id':104,'application_id':'A002','start_date':'2026-05-02','product':'Rewards Card','channel':'App','entry_source':'Push','pre_approved_flag':'N','application_status':'Started'},
    {'customer_id':105,'application_id':'A003','start_date':'2026-05-02','product':'Cashback Card','channel':'Public','entry_source':'Aggregator','pre_approved_flag':'N','application_status':'Started'},
]
starts_df = pd.DataFrame(starts_rows)
starts_df['start_date'] = pd.to_datetime(starts_df['start_date'])

# Attribute starts to visits using customer_id (for sample)
starts_mapped = starts_df.merge(visits_df[['customer_id','campaign_id','channel','product','visit_date']], on='customer_id', how='left')

# Normalize overlapping columns created by the merge (pandas creates _x/_y if both frames had same column names).
# Prefer the visit-side attribution (the visit's channel/campaign/product) when available.
for col in ['channel', 'campaign_id', 'product']:
    col_x = f"{col}_x"
    col_y = f"{col}_y"
    if col_y in starts_mapped.columns and col_x in starts_mapped.columns:
        starts_mapped[col] = starts_mapped[col_y].fillna(starts_mapped[col_x])
        starts_mapped = starts_mapped.drop(columns=[col_x, col_y])
    elif col_y in starts_mapped.columns:
        starts_mapped[col] = starts_mapped[col_y]
        starts_mapped = starts_mapped.drop(columns=[col_y])
    elif col_x in starts_mapped.columns:
        starts_mapped[col] = starts_mapped[col_x]
        starts_mapped = starts_mapped.drop(columns=[col_x])
# If neither _x/_y exist but 'channel' already exists, nothing to do.

# Funnel aggregations
visits_by_channel = visits_df.groupby('channel', as_index=False)['visit_count'].sum().rename(columns={'visit_count':'visits'})
starts_by_channel = starts_mapped.groupby('channel', as_index=False)['application_id'].nunique().rename(columns={'application_id':'starts'})

funnel_channel = visits_by_channel.merge(starts_by_channel, on='channel', how='left').fillna(0)
funnel_channel['start_rate'] = funnel_channel['starts'] / funnel_channel['visits'].replace(0, np.nan)

# Save CSVs
OUTPUT_DIR.joinpath('funnel_by_channel.csv').write_text(funnel_channel.to_csv(index=False))

# Lost revenue estimate
f = funnel_channel.copy()
f['abandoned'] = f['visits'] - f['starts']
f['expected_lost_approvals'] = f['abandoned'] * APPROVAL_RATE
f['lost_revenue'] = f['expected_lost_approvals'] * AVG_REV
f.to_csv(OUTPUT_DIR/'lost_estimates_by_channel.csv', index=False)

# 5pp uplift simulation
s = f.copy()
s['current_start_rate'] = s['starts'] / s['visits'].replace(0, np.nan)
s['new_start_rate'] = (s['current_start_rate'].fillna(0) + UPLIFT_PP).clip(upper=1.0)
s['new_starts'] = (s['visits'] * s['new_start_rate']).round().astype(int)
s['incremental_starts'] = s['new_starts'] - s['starts']
s['incremental_approvals'] = s['incremental_starts'] * APPROVAL_RATE
s['incremental_revenue'] = s['incremental_approvals'] * AVG_REV
s.to_csv(OUTPUT_DIR/'5pp_uplift_sim_by_channel.csv', index=False)

# Charts
plt.style.use('seaborn-v0_8')
fig, ax = plt.subplots(figsize=(8,3))
plot_df = funnel_channel.set_index('channel')[['visits','starts']]
plot_df.plot(kind='bar', ax=ax)
ax.set_ylabel('Count')
ax.set_title('Visits and Starts by Channel')
plt.tight_layout()
chart_path = OUTPUT_DIR/'funnel_chart.png'
fig.savefig(chart_path, dpi=150)
plt.close(fig)

# Channel performance placeholder chart (revenue not present in sample — use starts as proxy)
fig, ax = plt.subplots(figsize=(8,3))
(funnel_channel.set_index('channel')['starts']).plot(kind='bar', color='#6BAED6', ax=ax)
ax.set_ylabel('Starts')
ax.set_title('Starts by Channel')
plt.tight_layout()
chart2_path = OUTPUT_DIR/'channel_starts.png'
fig.savefig(chart2_path, dpi=150)
plt.close(fig)

print('Analysis complete — outputs saved to', OUTPUT_DIR.resolve())
