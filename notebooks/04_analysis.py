import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import warnings
import os
warnings.filterwarnings('ignore')

if os.path.basename(os.getcwd()) == 'notebooks':
    os.chdir('..')

print(f"Active Working Directory: {os.getcwd()}")
 
# ── CONFIG ────────────────────────────────────────────
DATA_DIR   = 'data/processed'
OUTPUT_DIR = 'notebooks/charts'
os.makedirs(OUTPUT_DIR, exist_ok=True)
 
# ── LOAD DATA ──────────────────────────────────────────
# parse_dates converts period_date strings into real Python dates
df_ag = pd.read_csv(f'{DATA_DIR}/cpi_allgroups.csv', parse_dates=['period_date'])
df_gr = pd.read_csv(f'{DATA_DIR}/cpi_groups.csv',    parse_dates=['period_date'])
df_re = pd.read_csv(f'{DATA_DIR}/cpi_regional.csv',  parse_dates=['period_date'])
 
print(f'allgroups: {len(df_ag)} rows')
print(f'groups:    {len(df_gr)} rows')
print(f'regional:  {len(df_re)} rows')

# ── EXPENDITURE WEIGHTS ────────────────────────────────
# Source: Stats NZ CPI Table 5 — December 2024 quarter
# These are the official weights used to calculate the headline rate
# They tell us: Housing is 29.41% of total household spending
weights = {
    'Food group':                              18.45,
    'Alcoholic beverages and tobacco group':    5.31,
    'Clothing and footwear group':              4.45,
    'Housing and household utilities group':   29.41,
    'Household contents and services group':    3.58,
    'Health group':                             3.47,
    'Transport group':                         14.34,
    'Communication group':                      2.69,
    'Recreation and culture group':             9.73,
    'Education group':                          1.43,
    'Miscellaneous goods and services group':   7.15,
}
# Verify weights sum to 100:
print(f'Weights total: {sum(weights.values()):.2f}%')  

# Analysis 1  Inflation Decomposition
# Question: Which spending groups are actually driving NZ's 3.1% annual inflation rate?

print('\n=== ANALYSIS 1: Inflation Decomposition ===')
 
# Get only top-level groups for Mar-26
# Join with dim_group logic: groups end with ' group' or are 'All groups'
groups_mar26 = df_gr[
    (df_gr['period'] == 'Mar-26') &
    (df_gr['group_name'].str.lower().str.endswith(' group') |
     (df_gr['group_name'] == 'All groups'))
    & (df_gr['group_name'] != 'All groups')
].copy()
 
# Add weight column — map from our weights dictionary
groups_mar26['weight'] = groups_mar26['group_name'].map(weights)
 
# Calculate contribution in percentage points
# This is the core formula for inflation decomposition
groups_mar26['contribution_pp'] = (
    groups_mar26['yoy_pct_change'] * groups_mar26['weight'] / 100
).round(2)
 
# Sort by contribution (smallest to largest for horizontal bar chart)
groups_mar26 = groups_mar26.sort_values('contribution_pp', ascending=True)
 
# Shorten group names for chart labels
name_map = {
    'Food group':                              'Food',
    'Alcoholic beverages and tobacco group':   'Alcohol & Tobacco',
    'Clothing and footwear group':             'Clothing',
    'Housing and household utilities group':   'Housing & Utilities',
    'Household contents and services group':   'Household Contents',
    'Health group':                            'Health',
    'Transport group':                         'Transport',
    'Communication group':                     'Communication',
    'Recreation and culture group':            'Recreation & Culture',
    'Education group':                         'Education',
    'Miscellaneous goods and services group':  'Miscellaneous',
}
groups_mar26['label'] = groups_mar26['group_name'].map(name_map)
 
# Print summary table
total = groups_mar26['contribution_pp'].sum()
print(f"{'Group':<30} {'Weight%':>8} {'YoY%':>6} {'Contribution':>13}")
print('-' * 60)
for _, r in groups_mar26.sort_values('contribution_pp', ascending=False).iterrows():
    print(f"{r['label']:<30} {r['weight']:>8.2f} {r['yoy_pct_change']:>6.1f} {r['contribution_pp']:>12.2f}pp")
print(f"{'TOTAL':<30} {'100.00':>8} {'':>6} {total:>12.2f}pp")

# Analysis 1
fig, ax = plt.subplots(figsize=(11, 7))
 
# Red bars = positive contribution, green = negative (deflating)
colors = ['#D32F2F' if x > 0 else '#388E3C' for x in groups_mar26['contribution_pp']]
bars = ax.barh(groups_mar26['label'], groups_mar26['contribution_pp'],
               color=colors, edgecolor='white', linewidth=0.5, height=0.65)
 
# Add value labels to the right of each bar
for bar, val in zip(bars, groups_mar26['contribution_pp']):
    xpos = bar.get_width() + 0.01 if val >= 0 else bar.get_width() - 0.01
    ha   = 'left' if val >= 0 else 'right'
    ax.text(xpos, bar.get_y() + bar.get_height()/2,
            f'{val:+.2f}pp', va='center', ha=ha, fontsize=9, fontweight='bold')
 
# Zero reference line
ax.axvline(x=0, color='black', linewidth=0.8, alpha=0.4)
 
ax.set_xlabel('Contribution to annual inflation (percentage points)', fontsize=11)
ax.set_title('What is driving NZ\'s 3.1% annual inflation?\n'
             'Contribution by spending group — March 2026 quarter',
             fontsize=13, fontweight='bold', pad=15)
ax.set_xlim(-0.25, 1.25)
 
# Annotation box in bottom right
ax.text(0.98, 0.02, f'Total: {total:.2f}pp\nHeadline CPI: 3.1% YoY',
        transform=ax.transAxes, ha='right', va='bottom', fontsize=9,
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#f0f4f8', edgecolor='#cccccc'))
 
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/chart1_decomposition.png', dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved: {OUTPUT_DIR}/chart1_decomposition.png')

# Analysis 2  Tradeable vs Non-tradeable Divergence
# Question: When did NZ inflation shift from being globally driven (imports) to domestically driven?
print('\n=== ANALYSIS 2: The Great Reversal ===')
 
# Sort chronologically — essential for line charts
df_ag = df_ag.sort_values('period_date')
 
# Calculate the gap between domestic and imported inflation
# Positive = domestic higher than imports (current situation)
# Negative = imports higher than domestic (2022 situation)
df_ag['gap'] = df_ag['nontradeables_yoy_pct'] - df_ag['tradeables_yoy_pct']
 
# Find the exact reversal point
# The first row where domestic exceeded imports
reversal = df_ag[df_ag['gap'] > 0].iloc[0]
print(f'Reversal point: {reversal["period"]} — domestic first exceeded imports')
print(f'  Tradeables:     {reversal["tradeables_yoy_pct"]:.1f}%')
print(f'  Non-tradeables: {reversal["nontradeables_yoy_pct"]:.1f}%')
 
# Latest quarter summary
latest = df_ag.iloc[-1]
print(f'\nLatest (Mar-26):')
print(f'  Tradeables:     {latest["tradeables_yoy_pct"]:.1f}%')
print(f'  Non-tradeables: {latest["nontradeables_yoy_pct"]:.1f}%')
print(f'  Gap:            +{latest["gap"]:.1f}pp')

# Two panels stacked: top = the two inflation lines, bottom = the gap
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9),
                                gridspec_kw={'height_ratios': [3, 1.2]},
                                sharex=True)
 
# ── TOP PANEL: the two lines ──────────────────────────
ax1.plot(df_ag['period_date'], df_ag['tradeables_yoy_pct'],
         color='#1565C0', linewidth=2.5, label='Tradeables (imports)', zorder=3)
ax1.plot(df_ag['period_date'], df_ag['nontradeables_yoy_pct'],
         color='#C62828', linewidth=2.5, label='Non-tradeables (domestic)', zorder=3)
ax1.plot(df_ag['period_date'], df_ag['allgroups_yoy_pct'],
         color='#555555', linewidth=1.5, linestyle='--',
         label='All groups (headline)', alpha=0.7, zorder=2)
 
# Shaded fill between the lines
# Blue shading = import-led period (tradeables above domestic)
# Red shading = domestic-led period (domestic above tradeables)
ax1.fill_between(df_ag['period_date'],
                 df_ag['tradeables_yoy_pct'],
                 df_ag['nontradeables_yoy_pct'],
                 where=df_ag['tradeables_yoy_pct'] >= df_ag['nontradeables_yoy_pct'],
                 alpha=0.12, color='#1565C0')
ax1.fill_between(df_ag['period_date'],
                 df_ag['tradeables_yoy_pct'],
                 df_ag['nontradeables_yoy_pct'],
                 where=df_ag['tradeables_yoy_pct'] < df_ag['nontradeables_yoy_pct'],
                 alpha=0.12, color='#C62828')
 
# Vertical annotation line at the reversal point
ax1.axvline(x=reversal['period_date'], color='#FF8F00',
            linewidth=1.5, linestyle=':', alpha=0.8)
ax1.text(reversal['period_date'], 8.8,
         f'Reversal\n{reversal["period"]}',
         ha='center', fontsize=8.5, color='#E65100', fontweight='bold')
 
# RBNZ target reference line
ax1.axhline(y=2, color='gray', linewidth=0.8, linestyle='--', alpha=0.5)
ax1.text(df_ag['period_date'].iloc[0], 2.2,
         'RBNZ target midpoint 2%', fontsize=8, color='gray', alpha=0.8)
 
ax1.set_ylabel('Year-on-year % change', fontsize=11)
ax1.set_title('NZ Inflation: The Great Reversal\n'
              'Import-led (2022) → Domestic-led (2025–26)',
              fontsize=13, fontweight='bold', pad=12)
ax1.legend(loc='upper left', fontsize=9.5, framealpha=0.9)
ax1.set_ylim(-1, 10)
ax1.grid(True, alpha=0.25, linestyle='--')
 
# ── BOTTOM PANEL: the gap ─────────────────────────────
gap_colors = ['#C62828' if g > 0 else '#1565C0' for g in df_ag['gap']]
ax2.bar(df_ag['period_date'], df_ag['gap'],
        color=gap_colors, alpha=0.75, width=60)
ax2.axhline(y=0, color='black', linewidth=1)
ax2.set_ylabel('Gap (pp)', fontsize=10)
ax2.set_xlabel('Quarter', fontsize=10)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[3, 9]))
ax2.grid(True, alpha=0.2, linestyle='--')
 
# Legend for the gap panel
blue_patch = mpatches.Patch(color='#1565C0', alpha=0.75,
                             label='Import-led')
red_patch  = mpatches.Patch(color='#C62828', alpha=0.75,
                             label='Domestic-led')
ax2.legend(handles=[blue_patch, red_patch], fontsize=8,
           loc='upper left', framealpha=0.9)
 
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/chart2_reversal.png', dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved: {OUTPUT_DIR}/chart2_reversal.png')

# Analysis 3  Regional Comparison
# Question: Which NZ regions have the highest inflation and how does Auckland compare?
print('\n=== ANALYSIS 3: Regional Comparison ===')
 
# Filter to March 2026 and sort highest to lowest
re_mar26 = df_re[df_re['period'] == 'Mar-26'].copy()
re_mar26 = re_mar26.sort_values('yoy_pct_change', ascending=False)
 
# Get reference values
national = re_mar26[re_mar26['region'] == 'New Zealand']['yoy_pct_change'].values[0]
auckland = re_mar26[re_mar26['region'] == 'Auckland']['yoy_pct_change'].values[0]
 
# Print summary
print(f"{'Region':<25} {'YoY%':>7} {'vs NZ':>8} {'vs AKL':>8}")
print('-' * 52)
for _, r in re_mar26.iterrows():
    print(f"{r['region']:<25} {r['yoy_pct_change']:>6.1f}% ",
          f"{r['yoy_pct_change']-national:>+7.2f}pp ",
          f"{r['yoy_pct_change']-auckland:>+7.2f}pp")
 
# Pivot for the trend line chart
re_pivot = df_re.pivot_table(
    index='period_date',
    columns='region',
    values='yoy_pct_change'
).sort_index()

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
 
# ── LEFT: bar chart ──────────────────────────────────
regions    = re_mar26['region'].tolist()
yoy_values = re_mar26['yoy_pct_change'].tolist()
 
# Colour bars: red if above national, blue if below
bar_colors = ['#C62828' if y > national else
              '#1565C0' if y < national else '#546E7A'
              for y in yoy_values]
 
bars = ax1.barh(regions, yoy_values, color=bar_colors,
                edgecolor='white', linewidth=0.5, height=0.65)
 
# Value labels on bars
for bar, val in zip(bars, yoy_values):
    ax1.text(bar.get_width() + 0.04,
             bar.get_y() + bar.get_height()/2,
             f'{val:.1f}%', va='center', ha='left',
             fontsize=10, fontweight='bold')
 
# National average reference line
ax1.axvline(x=national, color='#FF8F00', linewidth=2,
            linestyle='--', label=f'National average: {national:.1f}%')
ax1.set_xlabel('Annual % change (YoY)', fontsize=11)
ax1.set_title('NZ Regional Inflation\nMarch 2026 Quarter',
              fontsize=12, fontweight='bold')
ax1.set_xlim(0, max(yoy_values) + 0.8)
ax1.legend(fontsize=9, loc='lower right')
ax1.grid(True, alpha=0.2, axis='x', linestyle='--')
 
# ── RIGHT: trend lines ───────────────────────────────
key_regions = ['Auckland', 'Wellington', 'Canterbury',
               'Rest of South Island', 'New Zealand']
region_colors = {
    'Auckland':            '#1565C0',
    'Wellington':          '#6A1B9A',
    'Canterbury':          '#2E7D32',
    'Rest of South Island':'#C62828',
    'New Zealand':         '#555555',
}
 
for region in key_regions:
    if region in re_pivot.columns:
        style = '--' if region == 'New Zealand' else '-'
        lw    = 1.5 if region == 'New Zealand' else 2.2
        ax2.plot(re_pivot.index, re_pivot[region],
                 color=region_colors[region],
                 linewidth=lw, linestyle=style,
                 label=region, marker='o', markersize=4)
 
ax2.set_ylabel('Annual % change (YoY)', fontsize=11)
ax2.set_title('Regional Inflation Trend\nLast 5 Quarters',
              fontsize=12, fontweight='bold')
ax2.legend(fontsize=9, loc='upper left', framealpha=0.9)
ax2.grid(True, alpha=0.25, linestyle='--')
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha='right')
 
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/chart3_regional.png', dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved: {OUTPUT_DIR}/chart3_regional.png')

# Analysis 4  Inside Housing — What is Really Driving the 3.4% Rise?
# Question: Housing contributes 1.00pp to inflation. Is it rent, energy, or rates?
print('\n=== ANALYSIS 4: Housing Deep Dive ===')
 
# Filter to housing-related subgroups in Mar-26
# Using str.contains with regex=True to match multiple terms
housing_sub = df_gr[
    (df_gr['period'] == 'Mar-26') &
    (df_gr['group_name'].str.contains(
        'ousing|nergy|ates|ent |nsurance|ater|maintenance',
        case=False, regex=True
    ))
    & ~(df_gr['group_name'].str.lower().str.endswith(' group'))
].copy()
 
housing_group_yoy = 3.4   # The group-level headline
 
# Print results
print(f'\nHousing & Utilities group headline: {housing_group_yoy}%')
print(f"{'Subgroup':<45} {'YoY%':>7}")
print('-' * 55)
for _, r in housing_sub.sort_values('yoy_pct_change', ascending=False).iterrows():
    print(f"{r['group_name']:<45} {r['yoy_pct_change']:>7.1f}%")

housing_sub_sorted = housing_sub.sort_values('yoy_pct_change', ascending=True)
 
# Short display names
short_names = {
    'Actual rentals for housing':              'Rent',
    'Household energy':                        'Household Energy',
    'Property rates and related services':     'Property Rates',
    'Insurance':                               'Insurance',
    'Water supply and miscellaneous services': 'Water & Services',
    'Maintenance and repair of dwelling':      'Maintenance',
}
housing_sub_sorted['label'] = housing_sub_sorted['group_name'].map(
    short_names).fillna(housing_sub_sorted['group_name'].str[:35])
 
fig, ax = plt.subplots(figsize=(10, 5))
 
# Red = above group headline, orange = between national and group, green = below national
bar_colors = ['#C62828' if x > housing_group_yoy else
              '#FF8F00' if x > 0 else '#388E3C'
              for x in housing_sub_sorted['yoy_pct_change']]
 
bars = ax.barh(housing_sub_sorted['label'],
               housing_sub_sorted['yoy_pct_change'],
               color=bar_colors, edgecolor='white', height=0.6)
 
for bar, val in zip(bars, housing_sub_sorted['yoy_pct_change']):
    ax.text(bar.get_width() + 0.15,
            bar.get_y() + bar.get_height()/2,
            f'{val:.1f}%', va='center', ha='left',
            fontsize=10, fontweight='bold')
 
# Two reference lines: group headline and national average
ax.axvline(x=housing_group_yoy, color='#555555', linewidth=2,
           linestyle='--', label=f'Group headline: {housing_group_yoy}%')
ax.axvline(x=3.1, color='#29B5E8', linewidth=1.5,
           linestyle=':', label='National average: 3.1%', alpha=0.8)
 
ax.set_xlabel('Year-on-year % change', fontsize=11)
ax.set_title('Inside Housing & Utilities: What is driving the 3.4% rise?\n'
             'Subgroup breakdown — March 2026', fontsize=12, fontweight='bold')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.2, axis='x', linestyle='--')
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/chart4_housing.png', dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved: {OUTPUT_DIR}/chart4_housing.png')
