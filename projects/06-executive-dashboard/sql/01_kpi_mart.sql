-- =============================================================================
-- 01_kpi_mart.sql  |  Maple & Main executive dashboard
-- One weekly fact table for the whole business, plus the same measures cut by
-- the three dimensions an executive actually asks about.
--
-- Every measure is defined once, here, so the dashboard, the deck and any
-- future report cannot quietly disagree about what "active customer" means.
--
-- Dialect: DuckDB. Depends on the shared cleaning layer in
-- projects/01-churn-retention/sql/01_clean.sql and the weekly calendar from
-- projects/04-demand-forecasting/sql/01_weekly_series.sql.
-- =============================================================================

-- Order lines with everything the measures need, once
CREATE OR REPLACE TABLE kpi_lines AS
SELECT
    w.week_start, w.t,
    o.order_id, o.customer_id, o.channel, o.store_id,
    s.province,
    p.category,
    i.quantity                                      AS units,
    i.quantity * i.unit_price                       AS revenue,
    i.quantity * (i.unit_price - p.unit_cost)       AS margin,
    i.quantity * p.list_price                       AS list_value,
    i.promo_flag
FROM orders o
JOIN weeks w  ON o.order_date >= w.week_start AND o.order_date < w.week_start + 7
JOIN raw_order_items i ON i.order_id = o.order_id
JOIN raw_products   p  ON p.sku = i.sku
LEFT JOIN raw_stores s ON s.store_id = o.store_id;

-- A customer is "new" in the week they joined the loyalty programme.
-- First order date would do instead, but it puts every pre-existing member into
-- the first week of the extract and invents an acquisition spike that never happened.
CREATE OR REPLACE TABLE first_order AS
SELECT customer_id, join_date AS first_order_date
FROM customers;

-- Company level
CREATE OR REPLACE TABLE kpi_week AS
WITH base AS (
    SELECT
        l.week_start, l.t,
        SUM(l.revenue)                                               AS revenue,
        SUM(l.margin)                                                AS margin,
        COUNT(DISTINCT l.order_id)                                   AS orders,
        COUNT(DISTINCT l.customer_id)                                AS active_customers,
        SUM(l.units)                                                 AS units,
        SUM(l.revenue) / NULLIF(SUM(l.list_value), 0)                AS price_index,
        SUM(l.promo_flag * l.units) * 1.0 / NULLIF(SUM(l.units), 0)  AS promo_unit_share,
        SUM(CASE WHEN l.channel <> 'Store' THEN l.revenue ELSE 0 END)
            / NULLIF(SUM(l.revenue), 0)                              AS digital_revenue_share
    FROM kpi_lines l GROUP BY l.week_start, l.t
),
newc AS (
    SELECT w.t, COUNT(*) AS new_customers
    FROM first_order f JOIN weeks w
      ON f.first_order_date >= w.week_start AND f.first_order_date < w.week_start + 7
    GROUP BY w.t
),
media AS (
    SELECT cal.t, cal.media_total AS media_spend, cal.flyer_week, cal.peak_holiday, cal.back_to_school,
           cal.week_of_year, cal.month, cal.year
    FROM calendar cal
),
service AS (
    SELECT w.t,
           COUNT(*)                                                   AS service_contacts,
           AVG(CASE WHEN sc.resolved_flag = 1 THEN 1.0 ELSE 0 END)    AS service_resolved_rate,
           AVG(sc.csat_score)                                         AS csat
    FROM service_contacts sc JOIN weeks w
      ON sc.contact_date >= w.week_start AND sc.contact_date < w.week_start + 7
    GROUP BY w.t
)
SELECT
    b.*,
    COALESCE(n.new_customers, 0)                                     AS new_customers,
    b.revenue / NULLIF(b.orders, 0)                                  AS avg_basket,
    b.orders * 1.0 / NULLIF(b.active_customers, 0)                   AS orders_per_customer,
    b.units * 1.0 / NULLIF(b.orders, 0)                              AS units_per_order,
    b.margin / NULLIF(b.revenue, 0)                                  AS margin_rate,
    m.media_spend,
    b.revenue / NULLIF(m.media_spend, 0)                             AS revenue_per_media_dollar,
    COALESCE(s.service_contacts, 0)                                  AS service_contacts,
    s.service_resolved_rate, s.csat,
    m.flyer_week, m.peak_holiday, m.back_to_school, m.week_of_year, m.month, m.year
FROM base b
LEFT JOIN newc n USING (t)
LEFT JOIN media m USING (t)
LEFT JOIN service s USING (t)
ORDER BY b.t;

-- The same measures, cut three ways, for drill-down
CREATE OR REPLACE TABLE kpi_slice AS
SELECT 'Category' AS dimension, category AS slice, week_start, t,
       SUM(revenue) AS revenue, SUM(margin) AS margin, SUM(units) AS units,
       COUNT(DISTINCT order_id) AS orders, COUNT(DISTINCT customer_id) AS active_customers,
       SUM(revenue) / NULLIF(SUM(list_value), 0) AS price_index
FROM kpi_lines GROUP BY ALL
UNION ALL
SELECT 'Channel', channel, week_start, t,
       SUM(revenue), SUM(margin), SUM(units), COUNT(DISTINCT order_id), COUNT(DISTINCT customer_id),
       SUM(revenue) / NULLIF(SUM(list_value), 0)
FROM kpi_lines GROUP BY ALL
UNION ALL
SELECT 'Province', COALESCE(province, 'Online'), week_start, t,
       SUM(revenue), SUM(margin), SUM(units), COUNT(DISTINCT order_id), COUNT(DISTINCT customer_id),
       SUM(revenue) / NULLIF(SUM(list_value), 0)
FROM kpi_lines GROUP BY ALL
ORDER BY dimension, slice, t;

CREATE OR REPLACE TABLE kpi_qc AS
SELECT 'weeks in the mart' AS check_name, (SELECT COUNT(*) FROM kpi_week) AS n
UNION ALL SELECT 'weeks with missing revenue', (SELECT COUNT(*) FROM kpi_week WHERE revenue IS NULL)
UNION ALL SELECT 'weeks with no media figure', (SELECT COUNT(*) FROM kpi_week WHERE media_spend IS NULL)
UNION ALL SELECT 'weeks with no service contacts recorded', (SELECT COUNT(*) FROM kpi_week WHERE service_contacts = 0)
UNION ALL SELECT 'slice revenue that does not reconcile to the company total (tolerance $1)',
       (SELECT COUNT(*) FROM (
            SELECT s.dimension, s.t, SUM(s.revenue) AS sliced, MAX(k.revenue) AS total
            FROM kpi_slice s JOIN kpi_week k USING (t) GROUP BY 1, 2)
        WHERE ABS(sliced - total) > 1)
UNION ALL SELECT 'customers counted as new more than once',
       (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM first_order)
UNION ALL SELECT 'members who joined before the window (excluded from new customers)',
       (SELECT COUNT(*) FROM first_order WHERE first_order_date < (SELECT MIN(week_start) FROM weeks))
UNION ALL SELECT 'new customers across the window', (SELECT SUM(new_customers) FROM kpi_week)
UNION ALL SELECT 'orders counted in more than one week',
       (SELECT COUNT(*) FROM (SELECT order_id FROM kpi_lines GROUP BY order_id HAVING COUNT(DISTINCT t) > 1));
