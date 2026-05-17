USE DATABASE NZ_CPI_DB;
USE SCHEMA ANALYTICS;
USE WAREHOUSE CPI_WH;
 
-- ── DIMENSION: dim_period ──────────────────────────────────────
CREATE OR REPLACE TABLE dim_period (
    period       VARCHAR(10)  PRIMARY KEY,   -- 'Mar-26'
    period_date  DATE,                        -- 2026-03-31
    year         INTEGER,                     -- 2026
    quarter      VARCHAR(5)                   -- 'Mar'
);
 
-- ── DIMENSION: dim_group ────────────────────────────────────────
CREATE OR REPLACE TABLE dim_group (
    group_name   VARCHAR(300) PRIMARY KEY,
    series_ref   VARCHAR(20),
    level        VARCHAR(20)   -- 'group' or 'subgroup'
);
 
-- ── DIMENSION: dim_region ───────────────────────────────────────
CREATE OR REPLACE TABLE dim_region (
    region       VARCHAR(150) PRIMARY KEY
);
 
-- ── FACT: fact_allgroups ────────────────────────────────────────
-- 33 rows: quarterly time series 2018-2026
CREATE OR REPLACE TABLE fact_allgroups (
    period                   VARCHAR(10)  PRIMARY KEY,
    period_date              DATE,
    year                     INTEGER,
    quarter                  VARCHAR(5),
    tradeables_index         NUMBER(10,2),
    tradeables_qoq_pct       NUMBER(10,2),
    tradeables_yoy_pct       NUMBER(10,2),
    nontradeables_index      NUMBER(10,2),
    nontradeables_qoq_pct    NUMBER(10,2),
    nontradeables_yoy_pct    NUMBER(10,2),
    allgroups_index          NUMBER(10,2),
    allgroups_qoq_pct        NUMBER(10,2),
    allgroups_yoy_pct        NUMBER(10,2),
    is_post_covid            BOOLEAN DEFAULT FALSE  -- added after load
);
 
-- ── FACT: fact_groups ───────────────────────────────────────────
-- 280 rows: 56 groups x 5 quarters
CREATE OR REPLACE TABLE fact_groups (
    group_name       VARCHAR(300),
    period           VARCHAR(10),
    period_date      DATE,
    index_value      NUMBER(10,2),
    qoq_pct_change   NUMBER(10,2),
    yoy_pct_change   NUMBER(10,2),
    is_post_covid    BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (group_name, period)
);
 
-- ── FACT: fact_regional ─────────────────────────────────────────
-- 40 rows: 8 regions x 5 quarters
CREATE OR REPLACE TABLE fact_regional (
    region           VARCHAR(150),
    period           VARCHAR(10),
    period_date      DATE,
    year             INTEGER,
    quarter          VARCHAR(5),
    cpi_index        NUMBER(10,2),
    qoq_pct_change   NUMBER(10,2),
    yoy_pct_change   NUMBER(10,2),
    is_post_covid    BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (region, period)
);
 
-- Verify all 5 tables were created:
SHOW TABLES;
