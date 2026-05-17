import os
import snowflake.connector

# ── CONFIG ────────────────────────────────────────────────────
# NOTE: Remove your real password before pushing to GitHub!
# Use environment variables in production:
# import os; 
password = os.environ.get('SNOWFLAKE_PASSWORD')
SNOWFLAKE_CONFIG = {
    'account':   'gf03742.australia-east.azure',
    'user':      'priyanka',
    'password':  password,
    'database':  'NZ_CPI_DB',
    'schema':    'ANALYTICS',
    'warehouse': 'CPI_WH',
}

# ── COPY INTO STATEMENTS ──────────────────────────────────────
# KEY FIX: always use NUMBER(10,2) not just NUMBER
# NUMBER alone = NUMBER(38,0) in Snowflake which rounds decimals to integers
# NUMBER(10,2) = up to 10 digits total, 2 after the decimal point
COPY_STATEMENTS = [

    # ── DIMENSIONS FIRST (facts reference them) ───────────────

    ('dim_period', """
        COPY INTO dim_period (period, period_date, year, quarter)
        FROM (
            SELECT $1,
                   TRY_TO_DATE($2, 'YYYY-MM-DD'),
                   $3::INTEGER,
                   $4
            FROM @CPI_STAGE/cpi_allgroups.csv
        )
        FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
        ON_ERROR = CONTINUE
        PURGE = FALSE;
    """),

    # dim_group via temp table to get exactly 56 unique rows
    ('dim_group_cleanup',     "TRUNCATE TABLE dim_group;"),
    ('dim_group_temp_create', """
        CREATE OR REPLACE TEMPORARY TABLE dim_group_temp (
            group_name VARCHAR,
            series_ref VARCHAR,
            level      VARCHAR
        );
    """),
    ('dim_group_load_temp', """
        COPY INTO dim_group_temp (group_name, series_ref, level)
        FROM (
            SELECT $3, $4, 'Group'
            FROM @CPI_STAGE/cpi_groups.csv
        )
        FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
        ON_ERROR = CONTINUE;
    """),
    ('dim_group_finalize', """
        INSERT INTO dim_group (group_name, series_ref, level)
        SELECT DISTINCT group_name, series_ref, level
        FROM dim_group_temp;
    """),

    ('dim_region', """
        COPY INTO dim_region (region)
        FROM (
            SELECT DISTINCT $5
            FROM @CPI_STAGE/cpi_regional.csv
        )
        FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
        ON_ERROR = CONTINUE
        PURGE = FALSE;
    """),

    # ── FACTS AFTER DIMENSIONS ────────────────────────────────

    # CSV column order: $1=period $2=period_date $3=year $4=quarter
    #   $5=tradeables_index $6=tradeables_qoq $7=tradeables_yoy
    #   $8=nontradeables_index $9=nontradeables_qoq $10=nontradeables_yoy
    #   $11=allgroups_index $12=allgroups_qoq $13=allgroups_yoy
    ('fact_allgroups', """
        COPY INTO fact_allgroups (
            period, period_date, year, quarter,
            tradeables_index,    tradeables_qoq_pct,    tradeables_yoy_pct,
            nontradeables_index, nontradeables_qoq_pct, nontradeables_yoy_pct,
            allgroups_index,     allgroups_qoq_pct,     allgroups_yoy_pct
        )
        FROM (
            SELECT $1,
                   TRY_TO_DATE($2, 'YYYY-MM-DD'),
                   $3::INTEGER,
                   $4,
                   $5::NUMBER(10,2),  $6::NUMBER(10,2),  $7::NUMBER(10,2),
                   $8::NUMBER(10,2),  $9::NUMBER(10,2),  $10::NUMBER(10,2),
                   $11::NUMBER(10,2), $12::NUMBER(10,2), $13::NUMBER(10,2)
            FROM @CPI_STAGE/cpi_allgroups.csv
        )
        FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
        ON_ERROR = CONTINUE
        PURGE = FALSE;
    """),

    # CSV column order: $1=period $2=period_date $3=group_name $4=series_ref
    #   $5=index_value $6=qoq_pct_change $7=yoy_pct_change
    ('fact_groups', """
        COPY INTO fact_groups (
            group_name, period, period_date,
            index_value, qoq_pct_change, yoy_pct_change
        )
        FROM (
            SELECT $3,
                   $1,
                   TRY_TO_DATE($2, 'YYYY-MM-DD'),
                   $5::NUMBER(10,2),
                   $6::NUMBER(10,2),
                   $7::NUMBER(10,2)
            FROM @CPI_STAGE/cpi_groups.csv
        )
        FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
        ON_ERROR = CONTINUE
        PURGE = FALSE;
    """),

    # CSV column order: $1=period $2=period_date $3=year $4=quarter $5=region
    #   $6=cpi_index $7=qoq_pct_change $8=yoy_pct_change
    # THE FIX: $8::NUMBER(10,2) not just $8::NUMBER
    # NUMBER without precision = NUMBER(38,0) = rounds 2.7 to 3, 3.9 to 4
    ('fact_regional', """
        COPY INTO fact_regional (
            region, period, period_date, year, quarter,
            cpi_index, qoq_pct_change, yoy_pct_change
        )
        FROM (
            SELECT $5,
                   $1,
                   TRY_TO_DATE($2, 'YYYY-MM-DD'),
                   $3::INTEGER,
                   $4,
                   $6::NUMBER(10,2),
                   $7::NUMBER(10,2),
                   $8::NUMBER(10,2)
            FROM @CPI_STAGE/cpi_regional.csv
        )
        FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
        ON_ERROR = CONTINUE
        PURGE = FALSE;
    """),
]

# ── POST-LOAD: add is_post_covid flag ────────────────────────
POST_LOAD_STATEMENTS = [
    """UPDATE fact_allgroups
       SET is_post_covid = TRUE
       WHERE year >= 2020;""",
    """UPDATE fact_groups
       SET is_post_covid = TRUE
       WHERE period_date >= '2020-01-01';""",
    """UPDATE fact_regional
       SET is_post_covid = TRUE
       WHERE year >= 2020;""",
]

# ── EXPECTED ROW COUNTS ──────────────────────────────────────
EXPECTED = {
    'dim_period':     33,
    'dim_group':      56,
    'dim_region':      8,
    'fact_allgroups': 33,
    'fact_groups':   280,
    'fact_regional':  40,
}


def run():
    print('Connecting to Snowflake...')
    conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
    cur  = conn.cursor()

    # Clear all tables before reloading (fresh start)
    print('\nClearing existing data...')
    for table in ['fact_regional', 'fact_groups', 'fact_allgroups',
                  'dim_region', 'dim_group', 'dim_period']:
        cur.execute(f'TRUNCATE TABLE {table}')
        print(f'  Cleared {table}')

    print('\nRunning COPY INTO for each table:')
    for table_name, sql in COPY_STATEMENTS:
        print(f'  {table_name}...')
        try:
            cur.execute(sql)
            results = cur.fetchall()
            for r in results:
                if len(r) > 3:
                    print(f'    rows loaded: {r[3]}  errors: {r[4] if len(r)>4 else 0}')
        except Exception as e:
            print(f'    ERROR: {e}')

    print('\nAdding is_post_covid flag...')
    for sql in POST_LOAD_STATEMENTS:
        try:
            cur.execute(sql)
            print(f'  Updated {cur.rowcount} rows')
        except Exception as e:
            print(f'  ERROR: {e}')

    print('\nVerification:')
    all_ok = True
    for table, expected in EXPECTED.items():
        try:
            cur.execute(f'SELECT COUNT(*) FROM {table}')
            actual = cur.fetchone()[0]
            ok = actual == expected
            status = 'OK' if ok else f'EXPECTED {expected}'
            print(f'  {table:<25} {actual:>4} rows  {status}')
            if not ok:
                all_ok = False
        except Exception as e:
            print(f'  {table:<25} ERROR: {e}')
            all_ok = False

    # Quick decimal check on fact_regional
    print('\nDecimal check on fact_regional (Mar-26):')
    cur.execute("""
        SELECT region, yoy_pct_change
        FROM fact_regional
        WHERE period = 'Mar-26'
        ORDER BY yoy_pct_change DESC
        LIMIT 4
    """)
    for row in cur.fetchall():
        print(f'  {row[0]:<25} {row[1]}')
    print('  (Should show 3.9, 3.4, 3.1... not 4, 3, 3)')

    cur.close()
    conn.close()

    if all_ok:
        print('\nDone — all counts correct. Snowflake is clean.')
    else:
        print('\nDone — some counts wrong. Check errors above.')


if __name__ == '__main__':
    run()