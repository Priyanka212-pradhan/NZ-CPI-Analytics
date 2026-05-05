import sqlite3
import pandas as pd
import os

DB_PATH       = 'data/nz_cpi.db'
CSV_DIR       = 'data/processed'
ALLGROUPS_CSV = f'{CSV_DIR}/cpi_allgroups.csv'
GROUPS_CSV    = f'{CSV_DIR}/cpi_groups.csv'
REGIONAL_CSV  = f'{CSV_DIR}/cpi_regional.csv'


def create_schema(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_period (
            period       TEXT PRIMARY KEY,
            period_date  TEXT NOT NULL,
            year         INTEGER NOT NULL,
            quarter      TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_group (
            group_name  TEXT PRIMARY KEY,
            series_ref  TEXT,
            level       TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_region (
            region  TEXT PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_allgroups (
            period                   TEXT PRIMARY KEY,
            period_date              TEXT,
            year                     INTEGER,
            quarter                  TEXT,
            tradeables_index         REAL,
            tradeables_qoq_pct       REAL,
            tradeables_yoy_pct       REAL,
            nontradeables_index      REAL,
            nontradeables_qoq_pct    REAL,
            nontradeables_yoy_pct    REAL,
            allgroups_index          REAL,
            allgroups_qoq_pct        REAL,
            allgroups_yoy_pct        REAL,
            FOREIGN KEY (period) REFERENCES dim_period(period)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_groups (
            group_name      TEXT NOT NULL,
            period          TEXT NOT NULL,
            period_date     TEXT,
            index_value     REAL,
            qoq_pct_change  REAL,
            yoy_pct_change  REAL,
            PRIMARY KEY (group_name, period),
            FOREIGN KEY (group_name) REFERENCES dim_group(group_name),
            FOREIGN KEY (period)     REFERENCES dim_period(period)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_regional (
            region          TEXT NOT NULL,
            period          TEXT NOT NULL,
            period_date     TEXT,
            year            INTEGER,
            quarter         TEXT,
            cpi_index       REAL,
            qoq_pct_change  REAL,
            yoy_pct_change  REAL,
            PRIMARY KEY (region, period),
            FOREIGN KEY (region) REFERENCES dim_region(region),
            FOREIGN KEY (period) REFERENCES dim_period(period)
        )
    """)
    conn.commit()
    print('Schema created — 5 tables')


def add_level_column(df_groups):
    """
    If cpi_groups.csv does not have a 'level' column, derive it.
    Stats NZ top-level groups end with ' group' in the name.
    Everything else is a subgroup.
    """
    if 'level' not in df_groups.columns:
        print("  'level' column missing — deriving it from group name...")
        df_groups = df_groups.copy()
        df_groups['level'] = df_groups['group_name'].apply(
            lambda x: 'group'
            if str(x).strip().lower().endswith(' group')
            or str(x).strip().lower() == 'all groups'
            else 'subgroup'
        )
        grp_count = (df_groups['level'] == 'group').sum()
        sub_count = (df_groups['level'] == 'subgroup').sum()
        print(f"  Derived: {grp_count} groups, {sub_count} subgroups")
    return df_groups


def load_data(conn):
    # cpi_allgroups.csv is already flat — 33 rows, 13 columns. DO NOT pivot.
    df_allgroups = pd.read_csv(ALLGROUPS_CSV)
    df_groups    = pd.read_csv(GROUPS_CSV)
    df_regional  = pd.read_csv(REGIONAL_CSV)

    print(f'  allgroups rows: {len(df_allgroups)}  (expect 33)')
    print(f'  groups rows:    {len(df_groups)}  (expect 280)')
    print(f'  regional rows:  {len(df_regional)}   (expect 40)')

    # Add level column if missing from extract step
    df_groups = add_level_column(df_groups)

    # DIMENSIONS FIRST
    dim_period = df_allgroups[['period', 'period_date', 'year', 'quarter']].drop_duplicates()
    dim_period.to_sql('dim_period', conn, if_exists='replace', index=False)
    print(f'  dim_period:    {len(dim_period)} rows')

    dim_group = df_groups[['group_name', 'series_ref', 'level']].drop_duplicates('group_name')
    dim_group.to_sql('dim_group', conn, if_exists='replace', index=False)
    print(f'  dim_group:     {len(dim_group)} rows')

    dim_region = df_regional[['region']].drop_duplicates()
    dim_region.to_sql('dim_region', conn, if_exists='replace', index=False)
    print(f'  dim_region:    {len(dim_region)} rows')

    # FACTS AFTER DIMENSIONS
    df_allgroups.to_sql('fact_allgroups', conn, if_exists='replace', index=False)
    print(f'  fact_allgroups:{len(df_allgroups)} rows')

    fact_groups = df_groups[['group_name', 'period', 'period_date',
                              'index_value', 'qoq_pct_change', 'yoy_pct_change']]
    fact_groups.to_sql('fact_groups', conn, if_exists='replace', index=False)
    print(f'  fact_groups:   {len(fact_groups)} rows')

    df_regional.to_sql('fact_regional', conn, if_exists='replace', index=False)
    print(f'  fact_regional: {len(df_regional)} rows')

    conn.commit()


def verify(conn):
    print('\nVerification:')
    cursor = conn.cursor()
    expected = {
        'dim_period':     33,
        'dim_group':      56,
        'dim_region':      8,
        'fact_allgroups': 33,
        'fact_groups':   280,
        'fact_regional':  40,
    }
    all_ok = True
    for table, exp in expected.items():
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        actual = cursor.fetchone()[0]
        ok = actual == exp
        status = 'OK' if ok else f'EXPECTED {exp}'
        print(f'  {table:<25} {actual:>4} rows  {status}')
        if not ok:
            all_ok = False
    if all_ok:
        print('\n  All counts correct — database is clean!')
    else:
        print('\n  Some counts wrong — re-run 01_extract_FIXED.py first, then retry.')


if __name__ == '__main__':
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f'Old database removed: {DB_PATH}')
        except PermissionError:
            print('WARNING: Close DB Browser for SQLite first, then re-run.')
            exit(1)

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    print('\nLoading data:')
    load_data(conn)
    verify(conn)
    conn.close()
    print(f'\nDone — database saved to: {DB_PATH}')
