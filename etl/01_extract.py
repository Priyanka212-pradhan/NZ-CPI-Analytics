import pandas as pd
import numpy as np
import os

# CONFIG
INPUT_FILE = 'data/raw/consumers-price-index-march-2026-quarter.xlsx'
OUTPUT_DIR = 'data/processed'

os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_value(val):
    """
    Convert a raw cell to a float or NaN.
    Stats NZ uses '..' to mean 'data not available'.
    We convert that to np.nan — Pandas standard for missing numbers.
    """
    if val == '..':
        return np.nan
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan


def parse_quarter(quarter_str):
    """
    Turn 'Mar-25' into a proper Python date: 2025-03-31
    Dates as strings sort alphabetically (wrong).
    Real dates sort chronologically (correct).
    """
    if pd.isna(quarter_str):
        return pd.NaT

    month_to_end = {
        'Mar': '03-31',
        'Jun': '06-30',
        'Sep': '09-30',
        'Dec': '12-31'
    }

    parts = str(quarter_str).strip().split('-')
    if len(parts) != 2:
        return pd.NaT

    month_abbr = parts[0]
    year_short = parts[1]

    if month_abbr not in month_to_end:
        return pd.NaT

    year_full = '20' + year_short
    date_str  = f'{year_full}-{month_to_end[month_abbr]}'
    return pd.to_datetime(date_str, format='%Y-%m-%d')


# ── THIS FUNCTION WAS MISSING FROM YOUR SCRIPT ─────────────────────────────
def extract_allgroups(filepath):
    """
    Extract Sheet 1 — the 8-year time series (2018–2026).
    One row per quarter. 33 rows total.
    Columns: tradeables, non-tradeables, all groups — index + QoQ + YoY.
    """
    print('[Table 1] Extracting all-groups time series...')

    df_raw = pd.read_excel(filepath, sheet_name='1', header=None)

    # Data starts at row 9
    data_rows = df_raw.iloc[9:].copy().reset_index(drop=True)

    records     = []
    current_year = None

    for _, row in data_rows.iterrows():
        # Column 0: year (written only on first quarter of each year)
        if not pd.isna(row[0]) and str(row[0]).strip().isdigit():
            current_year = int(row[0])

        # Column 1: quarter name
        quarter_name = str(row[1]).strip() if not pd.isna(row[1]) else None

        if quarter_name not in ['Mar', 'Jun', 'Sep', 'Dec']:
            continue
        if current_year is None:
            continue

        year_short  = str(current_year)[2:]
        quarter_str = f'{quarter_name}-{year_short}'
        period_date = parse_quarter(quarter_str)

        records.append({
            'period':                  quarter_str,
            'period_date':             period_date,
            'year':                    current_year,
            'quarter':                 quarter_name,
            'tradeables_index':        clean_value(row[2]),
            'tradeables_qoq_pct':      clean_value(row[4]),
            'tradeables_yoy_pct':      clean_value(row[6]),
            'nontradeables_index':     clean_value(row[8]),
            'nontradeables_qoq_pct':   clean_value(row[10]),
            'nontradeables_yoy_pct':   clean_value(row[12]),
            'allgroups_index':         clean_value(row[14]),
            'allgroups_qoq_pct':       clean_value(row[16]),
            'allgroups_yoy_pct':       clean_value(row[18]),
        })

    df = pd.DataFrame(records)
    df = df.sort_values('period_date').reset_index(drop=True)
    print(f'  Rows: {len(df)}, Range: {df.period.iloc[0]} to {df.period.iloc[-1]}')
    return df


def extract_groups_sheet(filepath, sheet_name, value_label):
    """Read one of the group sheets (2.01, 2.02, or 2.03)"""
    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)

    quarter_row = df_raw.iloc[6]
    quarters = []
    for col_idx, val in enumerate(quarter_row):
        if not pd.isna(val) and str(val).strip() not in ['', 'NaN']:
            quarters.append((col_idx, str(val).strip()))

    data_rows = df_raw.iloc[7:].copy().reset_index(drop=True)
    records = []

    for _, row in data_rows.iterrows():
        group_name = row[0]
        series_ref = row[1]

        if pd.isna(group_name) or str(group_name).strip() == '':
            continue
        if str(group_name).strip().lower().startswith('source'):
            break

        group_clean = str(group_name).strip()
        ref_clean   = str(series_ref).strip() if not pd.isna(series_ref) else ''

        for col_idx, quarter_str in quarters:
            records.append({
                'period':      quarter_str,
                'period_date': parse_quarter(quarter_str),
                'group_name':  group_clean,
                'series_ref':  ref_clean,
                value_label:   clean_value(row[col_idx]),
            })

    return pd.DataFrame(records)


def extract_groups(filepath):
    """Merge sheets 2.01 + 2.02 + 2.03 into one combined table"""
    print('[Groups] Merging sheets 2.01 + 2.02 + 2.03...')

    df_index = extract_groups_sheet(filepath, '2.01', 'index_value')
    df_qoq   = extract_groups_sheet(filepath, '2.02', 'qoq_pct_change')
    df_yoy   = extract_groups_sheet(filepath, '2.03', 'yoy_pct_change')

    df = df_index.merge(
        df_qoq[['group_name', 'period', 'qoq_pct_change']],
        on=['group_name', 'period'], how='left'
    ).merge(
        df_yoy[['group_name', 'period', 'yoy_pct_change']],
        on=['group_name', 'period'], how='left'
    )

    df['group_name'] = df['group_name'].str.strip()
    df = df.sort_values(['group_name', 'period_date']).reset_index(drop=True)
    print(f'  {len(df)} rows, {df.group_name.nunique()} unique groups')
    return df


def extract_regional(filepath):
    print('[Table 17] Extracting regional CPI...')
    df_raw = pd.read_excel(filepath, sheet_name='17', header=None)

    region_row = df_raw.iloc[5]
    regions = []
    for col_idx, val in enumerate(region_row):
        if not pd.isna(val) and str(val).strip() not in ['', 'NaN']:
            regions.append((col_idx, str(val).strip()))

    records       = []
    current_metric = None
    current_year   = None

    for row_idx, row in df_raw.iterrows():
        cell0 = str(row[0]).strip() if not pd.isna(row[0]) else ''

        if 'All groups' in cell0 and not any(c.isdigit() for c in cell0):
            current_metric = 'index'
            continue
        if 'Percentage change from previous quarter' in cell0:
            current_metric = 'qoq_pct'
            continue
        if 'Percentage change from same quarter' in cell0:
            current_metric = 'yoy_pct'
            continue
        if 'Source' in cell0:
            break
        if current_metric is None:
            continue

        if str(cell0).isdigit() and len(cell0) == 4:
            current_year = int(cell0)

        cell1 = str(row[1]).strip() if not pd.isna(row[1]) else ''
        if cell1 not in ['Mar', 'Jun', 'Sep', 'Dec']:
            continue
        if current_year is None:
            continue

        year_short  = str(current_year)[2:]
        quarter_str = f'{cell1}-{year_short}'

        for col_idx, region_name in regions:
            records.append({
                'period':      quarter_str,
                'period_date': parse_quarter(quarter_str),
                'year':        current_year,
                'quarter':     cell1,
                'region':      region_name,
                'metric':      current_metric,
                'value':       clean_value(row[col_idx]),
            })

    df_long = pd.DataFrame(records)

    df = df_long.pivot_table(
        index=['period', 'period_date', 'year', 'quarter', 'region'],
        columns='metric', values='value', aggfunc='first'
    ).reset_index()
    df.columns.name = None

    df = df.rename(columns={
        'index':   'cpi_index',
        'qoq_pct': 'qoq_pct_change',
        'yoy_pct': 'yoy_pct_change'
    })

    df = df.sort_values(['region', 'period_date']).reset_index(drop=True)
    print(f'  {len(df)} rows, {df.region.nunique()} regions')
    return df


def profile(df, name):
    print(f'\n{"="*50}')
    print(f'PROFILE: {name}')
    print(f'{"="*50}')
    print(f'Shape: {df.shape[0]} rows x {df.shape[1]} columns')
    nulls = df.isnull().sum()
    if nulls.any():
        print('Missing values:')
        print(nulls[nulls > 0])
    else:
        print('Missing values: None — clean!')
    print('First 3 rows:')
    print(df.head(3).to_string())


if __name__ == '__main__':
    print('=' * 50)
    print('NZ CPI Analytics — Day 1: Extract & Transform')
    print('=' * 50)

    # ── FIX: extract_allgroups() for the time series ──────────
    # Your original script called extract_groups() for both —
    # that is why cpi_allgroups.csv had groups data, not time series.
    df_allgroups = extract_allgroups(INPUT_FILE)   # ← Sheet 1 (8-year series)
    df_groups    = extract_groups(INPUT_FILE)       # ← Sheets 2.01/2.02/2.03
    df_regional  = extract_regional(INPUT_FILE)    # ← Sheet 17

    profile(df_allgroups, 'cpi_allgroups')
    profile(df_groups,    'cpi_groups')
    profile(df_regional,  'cpi_regional')

    df_allgroups.to_csv(f'{OUTPUT_DIR}/cpi_allgroups.csv', index=False)
    df_groups.to_csv(f'{OUTPUT_DIR}/cpi_groups.csv',       index=False)
    df_regional.to_csv(f'{OUTPUT_DIR}/cpi_regional.csv',   index=False)

    print('\nDONE — 3 clean CSVs saved to', OUTPUT_DIR)
    print(f'  cpi_allgroups.csv — {len(df_allgroups)} rows  (should be 33)')
    print(f'  cpi_groups.csv    — {len(df_groups)} rows (should be 280)')
    print(f'  cpi_regional.csv  — {len(df_regional)} rows  (should be 40)')
