-- =============================================================================
-- 01_weekly_series.sql  |  Maple & Main demand forecasting
-- Weekly demand at the four levels a retailer actually plans on, plus the
-- calendar and media facts that are known before the week starts.
--
-- Dialect: DuckDB. Depends on the shared cleaning layer in
-- projects/01-churn-retention/sql/01_clean.sql (orders, customers).
-- Weeks start on a Monday and are aligned to 2023-11-06, the first full week.
-- =============================================================================

CREATE OR REPLACE TABLE weeks AS
SELECT
    DATE '2023-11-06' + CAST(w * 7 AS INTEGER)                                     AS week_start,
    CAST(w AS INTEGER)                                              AS t,
    WEEKOFYEAR(DATE '2023-11-06' + CAST(w * 7 AS INTEGER))                         AS week_of_year,
    MONTH(DATE '2023-11-06' + CAST(w * 7 AS INTEGER))                              AS month,
    YEAR(DATE '2023-11-06' + CAST(w * 7 AS INTEGER))                               AS year
FROM range(0, 156) AS r(w);

-- Order lines, priced and dated, restricted to complete weeks
CREATE OR REPLACE TABLE line_week AS
SELECT
    w.week_start, w.t,
    o.store_id,
    p.category,
    i.quantity                                   AS units,
    i.quantity * i.unit_price                    AS revenue,
    i.quantity * (i.unit_price - p.unit_cost)    AS margin,
    i.promo_flag
FROM orders o
JOIN weeks w
  ON o.order_date >= w.week_start AND o.order_date < w.week_start + 7
JOIN raw_order_items i ON i.order_id = o.order_id
JOIN raw_products   p ON p.sku = i.sku;

-- Media is a planning input: the business sets next quarter's spend, so it is
-- known before the week starts and may be used as a forecasting feature.
CREATE OR REPLACE TABLE media_wide AS
SELECT
    CAST(week_start AS DATE) AS week_start,
    SUM(spend_cad)                                        AS media_total,
    SUM(spend_cad) FILTER (WHERE channel = 'TV')          AS spend_tv,
    SUM(spend_cad) FILTER (WHERE channel = 'Flyer')       AS spend_flyer,
    SUM(spend_cad) FILTER (WHERE channel = 'Paid Search') AS spend_search,
    SUM(spend_cad) FILTER (WHERE channel = 'Paid Social') AS spend_social,
    SUM(spend_cad) FILTER (WHERE channel = 'Email')       AS spend_email,
    SUM(spend_cad) FILTER (WHERE channel = 'Display')     AS spend_display
FROM raw_media_spend_weekly
GROUP BY 1;

CREATE OR REPLACE TABLE calendar AS
SELECT
    w.*,
    COALESCE(m.media_total, 0)                                      AS media_total,
    COALESCE(m.spend_tv, 0)                                         AS spend_tv,
    COALESCE(m.spend_flyer, 0)                                      AS spend_flyer,
    COALESCE(m.spend_search, 0)                                     AS spend_search,
    COALESCE(m.spend_social, 0)                                     AS spend_social,
    COALESCE(m.spend_email, 0)                                      AS spend_email,
    COALESCE(m.spend_display, 0)                                    AS spend_display,
    CASE WHEN m.week_start IS NULL THEN 1 ELSE 0 END                AS media_row_missing,
    -- a flyer drops in alternate weeks; the plan is known well in advance
    CASE WHEN COALESCE(m.spend_flyer, 0) > 25000 THEN 1 ELSE 0 END  AS flyer_week,
    CASE WHEN w.week_of_year BETWEEN 47 AND 52 THEN 1 ELSE 0 END    AS peak_holiday,
    CASE WHEN w.week_of_year BETWEEN 33 AND 36 THEN 1 ELSE 0 END    AS back_to_school
FROM weeks w
LEFT JOIN media_wide m USING (week_start);

CREATE OR REPLACE TABLE series_total AS
SELECT 'Total' AS level, 'All' AS series_id, week_start, t,
       SUM(units) AS units, SUM(revenue) AS revenue, SUM(margin) AS margin,
       SUM(CASE WHEN promo_flag = 1 THEN revenue ELSE 0 END) / NULLIF(SUM(revenue), 0) AS promo_revenue_share
FROM line_week GROUP BY ALL;

CREATE OR REPLACE TABLE series_category AS
SELECT 'Category' AS level, category AS series_id, week_start, t,
       SUM(units) AS units, SUM(revenue) AS revenue, SUM(margin) AS margin,
       SUM(CASE WHEN promo_flag = 1 THEN revenue ELSE 0 END) / NULLIF(SUM(revenue), 0) AS promo_revenue_share
FROM line_week GROUP BY ALL;

-- Store level counts in-store sales only: a web order is not a store's demand
CREATE OR REPLACE TABLE series_store AS
SELECT 'Store' AS level, CAST(store_id AS VARCHAR) AS series_id, week_start, t,
       SUM(units) AS units, SUM(revenue) AS revenue, SUM(margin) AS margin,
       SUM(CASE WHEN promo_flag = 1 THEN revenue ELSE 0 END) / NULLIF(SUM(revenue), 0) AS promo_revenue_share
FROM line_week WHERE store_id IS NOT NULL GROUP BY ALL;

CREATE OR REPLACE TABLE series_store_category AS
SELECT 'Store x Category' AS level, CAST(store_id AS VARCHAR) || ' | ' || category AS series_id, week_start, t,
       SUM(units) AS units, SUM(revenue) AS revenue, SUM(margin) AS margin,
       SUM(CASE WHEN promo_flag = 1 THEN revenue ELSE 0 END) / NULLIF(SUM(revenue), 0) AS promo_revenue_share
FROM line_week WHERE store_id IS NOT NULL GROUP BY ALL;

CREATE OR REPLACE TABLE series AS
SELECT * FROM series_total
UNION ALL SELECT * FROM series_category
UNION ALL SELECT * FROM series_store
UNION ALL SELECT * FROM series_store_category
ORDER BY level, series_id, t;

CREATE OR REPLACE TABLE forecast_qc AS
SELECT 'weeks in the series' AS check_name, (SELECT COUNT(*) FROM weeks) AS n
UNION ALL SELECT 'weeks with no media row (treated as zero spend)', (SELECT COUNT(*) FROM calendar WHERE media_row_missing = 1)
UNION ALL SELECT 'order lines outside the 156 complete weeks',
       (SELECT COUNT(*) FROM raw_order_items) - (SELECT COUNT(*) FROM line_week)
UNION ALL SELECT 'series at total level',            (SELECT COUNT(DISTINCT series_id) FROM series_total)
UNION ALL SELECT 'series at category level',         (SELECT COUNT(DISTINCT series_id) FROM series_category)
UNION ALL SELECT 'series at store level',            (SELECT COUNT(DISTINCT series_id) FROM series_store)
UNION ALL SELECT 'series at store x category level', (SELECT COUNT(DISTINCT series_id) FROM series_store_category)
UNION ALL SELECT 'series x week rows with no demand at all',
       (SELECT COUNT(*) FROM (SELECT level, series_id, COUNT(*) AS n FROM series GROUP BY 1, 2)
        WHERE n < (SELECT COUNT(*) FROM weeks))
UNION ALL SELECT 'weeks where category revenue does not reconcile to the total (tolerance $1)',
       (SELECT COUNT(*) FROM (
            SELECT t.t, t.revenue AS tot, SUM(c.revenue) AS cat
            FROM series_total t JOIN series_category c USING (t) GROUP BY 1, 2)
        WHERE ABS(tot - cat) > 1);
