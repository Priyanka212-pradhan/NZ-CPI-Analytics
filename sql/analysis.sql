/* 
   NZ CPI ANALYSIS - PORTFOLIO PROJECT
   Author: Priyanka Pradhan
   Date: May 2026
*/

---------------------------------------------------------
-- QUERY 1: Current Inflation State
-- Business question: What is NZ's current inflation and is it domestic-led or import-led?
---------------------------------------------------------
SELECT
    period,
    ROUND(allgroups_yoy_pct, 1)     AS all_groups_yoy,
    ROUND(tradeables_yoy_pct, 1)    AS tradeables_yoy,
    ROUND(nontradeables_yoy_pct, 1) AS nontradeables_yoy,
    CASE
        WHEN nontradeables_yoy_pct > tradeables_yoy_pct THEN 'Domestic-led'
        WHEN tradeables_yoy_pct > nontradeables_yoy_pct THEN 'Import-led'
        ELSE 'Balanced'
    END AS inflation_character
FROM fact_allgroups
ORDER BY period_date DESC
LIMIT 8;

---------------------------------------------------------
-- QUERY 2: Inflation Shift
-- Business question: When exactly did inflation shift from globally driven to domestically driven?
---------------------------------------------------------
SELECT
    period,
    ROUND(tradeables_yoy_pct, 1)                           AS tradeables_yoy,
    ROUND(nontradeables_yoy_pct, 1)                        AS nontradeables_yoy,
    -- Gap: positive = domestic higher, negative = imports higher
    ROUND(nontradeables_yoy_pct - tradeables_yoy_pct, 1)   AS domestic_gap,
    -- LAG() gets the value from the PREVIOUS row
    ROUND(
        (nontradeables_yoy_pct - tradeables_yoy_pct)
        - LAG(nontradeables_yoy_pct - tradeables_yoy_pct)
              OVER (ORDER BY period_date),
    2) AS gap_change
FROM fact_allgroups
ORDER BY period_date;

---------------------------------------------------------
-- QUERY 3: Spending Group Inflation
-- Business question: Which of the 11 spending groups are inflating fastest in Mar-26?
---------------------------------------------------------

SELECT
    f.group_name,
    ROUND(f.yoy_pct_change, 1)  AS yoy_pct,
    ROUND(f.qoq_pct_change, 1)  AS qoq_pct,
    -- RANK() assigns rank 1 to the highest value
    RANK() OVER (ORDER BY f.yoy_pct_change DESC) AS yoy_rank
FROM fact_groups f
-- JOIN dim_group to access 'level' column (stored in dimension, not fact)
JOIN dim_group d ON f.group_name = d.group_name
WHERE f.period = 'Mar-26'
  AND d.level  = 'group'
ORDER BY f.yoy_pct_change DESC;

---------------------------------------------------------
-- QUERY 4: Data validation — recalculate QoQ from scratch
-- Business question: Does our stored qoq_pct match what we calculate using LAG()? (data quality check)
---------------------------------------------------------

SELECT
    period,
    ROUND(allgroups_index, 1)                             AS index_now,
    ROUND(LAG(allgroups_index,1) OVER
         (ORDER BY period_date), 1)                       AS index_prev,
    -- Calculate QoQ ourselves using the standard formula
    ROUND(
        (allgroups_index
         - LAG(allgroups_index,1) OVER (ORDER BY period_date))
        / LAG(allgroups_index,1) OVER (ORDER BY period_date) * 100,
    2)                                                    AS calculated_qoq,
    -- Compare to the value Stats NZ gave us
    ROUND(allgroups_qoq_pct, 2)                           AS stored_qoq
FROM fact_allgroups
ORDER BY period_date DESC
LIMIT 6;

---------------------------------------------------------
-- QUERY 5: Rolling 4-quarter average — AVG() OVER ROWS
-- Business question: Removing seasonal noise, what is the true underlying inflation trend?
---------------------------------------------------------
SELECT
    period,
    ROUND(allgroups_yoy_pct, 1) AS yoy_pct,
    -- Rolling average of current + 3 previous quarters (= 1 full year)
    ROUND(
        AVG(allgroups_yoy_pct) OVER (
            ORDER BY period_date
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ),
    2) AS rolling_4q_avg,
    -- Is this quarter above or below its own 1-year rolling average?
    ROUND(
        allgroups_yoy_pct - AVG(allgroups_yoy_pct) OVER (
            ORDER BY period_date
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ),
    2) AS above_below_trend
FROM fact_allgroups
ORDER BY period_date DESC
LIMIT 8;
---------------------------------------------------------
-- QUERY 6: Persistent above-CPI groups — CTE pattern
-- Business question: Which groups have inflated above the national rate for ALL 5 quarters?
---------------------------------------------------------
-- Step 1: For each group and period, flag if it is above national rate
WITH group_vs_national AS (
    SELECT
        f.group_name,
        f.period,
        ROUND(f.yoy_pct_change, 1)    AS group_yoy,
        ROUND(a.allgroups_yoy_pct, 1) AS national_yoy,
        CASE WHEN f.yoy_pct_change > a.allgroups_yoy_pct
             THEN 1 ELSE 0 END        AS is_above
    FROM fact_groups f
    JOIN dim_group d    ON f.group_name = d.group_name
    JOIN fact_allgroups a ON f.period   = a.period
    WHERE d.level = 'group'
      AND f.group_name != 'All groups'
)
-- Step 2: Keep only groups above national in ALL 5 quarters
SELECT
    group_name,
    SUM(is_above)            AS quarters_above,
    ROUND(AVG(group_yoy), 1) AS avg_yoy_pct
FROM group_vs_national
GROUP BY group_name
HAVING SUM(is_above) = 5
ORDER BY avg_yoy_pct DESC;
---------------------------------------------------------
-- QUERY 7: Regional comparison — self-join
-- Business question: Which NZ regions have the highest inflation and how does Auckland compare?
---------------------------------------------------------
SELECT
    r.region,
    ROUND(r.yoy_pct_change, 1)                         AS yoy_pct,
    -- Self-join: bring in Auckland as the benchmark
    ROUND(r.yoy_pct_change - auck.yoy_pct_change, 2)   AS ppts_above_auckland,
    RANK() OVER (ORDER BY r.yoy_pct_change DESC)        AS inflation_rank
FROM fact_regional r
JOIN fact_regional auck
  ON  auck.period = r.period
  AND auck.region = 'Auckland'
WHERE r.period = 'Mar-26'
ORDER BY r.yoy_pct_change DESC;

---------------------------------------------------------
-- QUERY 8: Housing deep dive — LIKE pattern matching
-- Business question: Inside the Housing group, what is actually driving the 3.4% annual rise?
---------------------------------------------------------
SELECT
   f.group_name,
    d.level,
    ROUND(f.yoy_pct_change, 1)  AS yoy_pct,
    ROUND(f.qoq_pct_change, 1)  AS qoq_pct
FROM fact_groups f
JOIN dim_group d ON f.group_name = d.group_name
WHERE f.period = 'Mar-26'
  AND (
      f.group_name LIKE '%ousing%'
   OR f.group_name LIKE '%ent%'
   OR f.group_name LIKE '%lectricity%'
   OR f.group_name LIKE '%nergy%'
   OR f.group_name LIKE '%ates%'
   OR f.group_name LIKE '%nsurance%'
  )
ORDER BY f.yoy_pct_change DESC;

