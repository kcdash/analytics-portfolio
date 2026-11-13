-- =============================================================================
-- 01_mmm_base.sql  |  Maple & Main marketing mix model
-- One row per week: what was sold, what was spent on media, and the trading
-- conditions that would otherwise be blamed on media.
--
-- Dialect: DuckDB. Depends on the shared cleaning layer in
-- projects/01-churn-retention/sql/01_clean.sql and on the weekly calendar from
-- projects/04-demand-forecasting/sql/01_weekly_series.sql.
-- =============================================================================

-- Sales, priced from order lines so discount depth is visible
CREATE OR REPLACE TABLE mmm_sales AS
SELECT
    w.week_start, w.t,
    SUM(i.quantity * i.unit_price)                                  AS revenue,
    SUM(i.quantity * (i.unit_price - p.unit_cost))                  AS margin,
    COUNT(DISTINCT o.order_id)                                      AS orders,
    SUM(i.quantity)                                                 AS units,
    SUM(i.quantity * i.unit_price) / COUNT(DISTINCT o.order_id)     AS avg_basket,
    -- realised price against list: the single best control for promotion depth
    SUM(i.quantity * i.unit_price) / SUM(i.quantity * p.list_price) AS price_index,
    SUM(i.promo_flag * i.quantity) * 1.0 / SUM(i.quantity)          AS promo_unit_share,
    COUNT(DISTINCT o.customer_id)                                   AS active_customers
FROM weeks w
JOIN orders o ON o.order_date >= w.week_start AND o.order_date < w.week_start + 7
JOIN raw_order_items i ON i.order_id = o.order_id
JOIN raw_products   p ON p.sku = i.sku
GROUP BY w.week_start, w.t;

-- Media spend and impressions by channel, one column per channel
CREATE OR REPLACE TABLE mmm_media AS
SELECT
    CAST(week_start AS DATE) AS week_start,
    COALESCE(SUM(spend_cad) FILTER (WHERE channel = 'TV'), 0)           AS tv,
    COALESCE(SUM(spend_cad) FILTER (WHERE channel = 'Paid Search'), 0)  AS paid_search,
    COALESCE(SUM(spend_cad) FILTER (WHERE channel = 'Paid Social'), 0)  AS paid_social,
    COALESCE(SUM(spend_cad) FILTER (WHERE channel = 'Display'), 0)      AS display,
    COALESCE(SUM(spend_cad) FILTER (WHERE channel = 'Flyer'), 0)        AS flyer,
    COALESCE(SUM(spend_cad) FILTER (WHERE channel = 'Email'), 0)        AS email,
    SUM(spend_cad)                                                      AS total_spend,
    COUNT(DISTINCT channel)                                             AS channels_reported
FROM raw_media_spend_weekly
GROUP BY 1;

-- CRM pressure: how many customers were contacted, which is a marketing input
-- the media file does not carry
CREATE OR REPLACE TABLE mmm_crm AS
SELECT w.week_start, COALESCE(SUM(cc.sent_flag), 0) AS crm_contacts
FROM weeks w
LEFT JOIN campaigns cp ON cp.start_date >= w.week_start AND cp.start_date < w.week_start + 7
LEFT JOIN raw_campaign_contacts cc ON cc.campaign_id = cp.campaign_id
GROUP BY w.week_start;

CREATE OR REPLACE TABLE mmm_base AS
SELECT
    s.week_start, s.t, s.revenue, s.margin, s.orders, s.units, s.avg_basket,
    s.price_index, s.promo_unit_share, s.active_customers,
    COALESCE(m.tv, 0) AS tv, COALESCE(m.paid_search, 0) AS paid_search,
    COALESCE(m.paid_social, 0) AS paid_social, COALESCE(m.display, 0) AS display,
    COALESCE(m.flyer, 0) AS flyer, COALESCE(m.email, 0) AS email,
    COALESCE(m.total_spend, 0) AS total_spend,
    COALESCE(c.crm_contacts, 0) AS crm_contacts,
    cal.week_of_year, cal.month, cal.year, cal.peak_holiday, cal.back_to_school,
    CASE WHEN m.week_start IS NULL OR m.channels_reported < 6 THEN 1 ELSE 0 END AS media_row_incomplete
FROM mmm_sales s
LEFT JOIN mmm_media m USING (week_start)
LEFT JOIN mmm_crm   c USING (week_start)
JOIN calendar cal USING (t)
ORDER BY s.t;

CREATE OR REPLACE TABLE mmm_qc AS
SELECT 'weeks in the model' AS check_name, (SELECT COUNT(*) FROM mmm_base) AS n
UNION ALL SELECT 'weeks with an incomplete media row', (SELECT COUNT(*) FROM mmm_base WHERE media_row_incomplete = 1)
UNION ALL SELECT 'weeks with zero spend in any channel',
       (SELECT COUNT(*) FROM mmm_base WHERE tv = 0 OR paid_search = 0 OR paid_social = 0 OR display = 0 OR flyer = 0 OR email = 0)
UNION ALL SELECT 'weeks with missing revenue', (SELECT COUNT(*) FROM mmm_base WHERE revenue IS NULL)
UNION ALL SELECT 'weeks where price index falls outside 0.5 to 1.0', (SELECT COUNT(*) FROM mmm_base WHERE price_index < 0.5 OR price_index > 1.0)
UNION ALL SELECT 'total media spend in the window, CAD', (SELECT CAST(ROUND(SUM(total_spend)) AS BIGINT) FROM mmm_base)
UNION ALL SELECT 'total revenue in the window, CAD', (SELECT CAST(ROUND(SUM(revenue)) AS BIGINT) FROM mmm_base);
