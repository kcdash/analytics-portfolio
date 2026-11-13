-- =============================================================================
-- 01_behaviour_features.sql  |  Maple & Main segmentation project
-- How each customer shops, measured twice, twelve months apart.
--
-- The features describe the SHAPE of a customer's shopping, not its SIZE:
-- category mix, channel mix, promotion sensitivity, trip rhythm, browsing.
-- Spend and margin are carried alongside but are NOT clustering inputs, so the
-- segments cannot collapse into "big spender / small spender".
--
-- Dialect: DuckDB.  Depends on the shared cleaning layer in
-- projects/01-churn-retention/sql/01_clean.sql (customers, orders, web_activity).
-- =============================================================================

CREATE OR REPLACE TABLE seg_snapshots AS
SELECT * FROM (VALUES (DATE '2025-05-05', 'prior'), (DATE '2026-05-04', 'current')) AS t(as_of_date, snapshot);

-- Active customers: joined at least a year ago, at least 2 orders in the last year.
-- Shape needs more than one trip to be meaningful.
CREATE OR REPLACE TABLE seg_base AS
SELECT c.customer_id, s.as_of_date, s.snapshot, c.join_date, c.province, c.age_band,
       c.loyalty_tier, c.acquisition_channel, c.email_opt_in, c.sms_opt_in
FROM customers c
CROSS JOIN seg_snapshots s
WHERE c.join_date <= s.as_of_date - 365
  AND (SELECT COUNT(*) FROM orders o
       WHERE o.customer_id = c.customer_id
         AND o.order_date >= s.as_of_date - 365 AND o.order_date < s.as_of_date) >= 2;

-- Order-level behaviour over the 12 months before the snapshot
CREATE OR REPLACE TABLE seg_orders AS
SELECT
    b.customer_id, b.as_of_date,
    COUNT(*)                                                   AS orders_365d,
    SUM(o.net_amount)                                          AS spend_365d,
    SUM(o.margin_amount)                                       AS margin_365d,
    AVG(o.net_amount)                                          AS avg_basket,
    DATE_DIFF('day', MAX(o.order_date), b.as_of_date)          AS recency_days,
    DATE_DIFF('day', MIN(o.order_date), MAX(o.order_date)) * 1.0
        / NULLIF(COUNT(*) - 1, 0)                              AS avg_gap_days,
    AVG(o.n_categories)                                        AS categories_per_order,
    SUM(o.discount_amount) / NULLIF(SUM(o.gross_amount), 0)    AS discount_share,
    SUM(o.n_promo_lines) * 1.0 / NULLIF(SUM(o.n_lines), 0)     AS promo_line_share,
    AVG(CASE WHEN o.channel = 'Store' THEN 1.0 ELSE 0 END)     AS store_share,
    AVG(CASE WHEN o.channel = 'Web'   THEN 1.0 ELSE 0 END)     AS web_share,
    AVG(CASE WHEN o.channel = 'App'   THEN 1.0 ELSE 0 END)     AS app_share,
    AVG(CASE WHEN DAYOFWEEK(o.order_date) IN (0, 6) THEN 1.0 ELSE 0 END) AS weekend_share,
    AVG(CASE WHEN MONTH(o.order_date) IN (11, 12) THEN 1.0 ELSE 0 END)   AS q4_share,
    SUM(CASE WHEN o.points_redeemed > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS redemption_rate
FROM seg_base b
JOIN orders o
  ON o.customer_id = b.customer_id
 AND o.order_date >= b.as_of_date - 365
 AND o.order_date <  b.as_of_date
GROUP BY b.customer_id, b.as_of_date;

-- Category and private-label mix, as a share of spend
CREATE OR REPLACE TABLE seg_mix AS
SELECT
    b.customer_id, b.as_of_date,
    SUM(i.quantity * i.unit_price)                                                      AS line_spend,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Apparel'), 0)                AS sp_apparel,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Home'), 0)                   AS sp_home,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Outdoor & Garden'), 0)       AS sp_outdoor,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Electronics'), 0)            AS sp_electronics,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Beauty & Wellness'), 0)      AS sp_beauty,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Grocery & Pantry'), 0)       AS sp_grocery,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Toys & Seasonal'), 0)        AS sp_toys,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.category = 'Sports & Fitness'), 0)       AS sp_sports,
    COALESCE(SUM(i.quantity * i.unit_price) FILTER (WHERE p.brand = 'Main Street (private label)'), 0) AS sp_private_label,
    COUNT(DISTINCT p.category)                                                          AS distinct_categories,
    -- unit counts per category: the evidence behind a persona label, and less noisy than spend
    SUM(i.quantity)                                                                     AS units_total,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Apparel'), 0)                  AS u_apparel,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Home'), 0)                     AS u_home,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Outdoor & Garden'), 0)         AS u_outdoor,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Electronics'), 0)              AS u_electronics,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Beauty & Wellness'), 0)        AS u_beauty,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Grocery & Pantry'), 0)         AS u_grocery,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Toys & Seasonal'), 0)          AS u_toys,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Sports & Fitness'), 0)         AS u_sports
FROM seg_base b
JOIN orders o
  ON o.customer_id = b.customer_id
 AND o.order_date >= b.as_of_date - 365
 AND o.order_date <  b.as_of_date
JOIN raw_order_items i ON i.order_id = o.order_id
JOIN raw_products   p ON p.sku = i.sku
GROUP BY b.customer_id, b.as_of_date;

-- Browsing in the six complete months before the snapshot
CREATE OR REPLACE TABLE seg_web AS
SELECT b.customer_id, b.as_of_date,
       SUM(w.sessions)         AS web_sessions_6m,
       SUM(w.abandoned_carts)  AS abandoned_carts_6m
FROM seg_base b
JOIN web_activity w
  ON w.customer_id = b.customer_id
 AND w.month_start <  DATE_TRUNC('month', b.as_of_date)
 AND w.month_start >= DATE_TRUNC('month', b.as_of_date) - INTERVAL 6 MONTH
GROUP BY b.customer_id, b.as_of_date;

CREATE OR REPLACE TABLE seg_features AS
SELECT
    b.customer_id, b.as_of_date, b.snapshot,
    b.province, b.age_band, b.loyalty_tier, b.acquisition_channel, b.email_opt_in, b.sms_opt_in,
    DATE_DIFF('day', b.join_date, b.as_of_date) / 365.25            AS tenure_years,
    -- carried for profiling, never clustered on
    o.orders_365d, o.spend_365d, o.margin_365d, o.recency_days,
    -- shape features (the clustering inputs)
    o.avg_basket, o.avg_gap_days, o.categories_per_order,
    COALESCE(o.discount_share, 0)        AS discount_share,
    COALESCE(o.promo_line_share, 0)      AS promo_line_share,
    o.store_share, o.web_share, o.app_share, o.weekend_share, o.q4_share, o.redemption_rate,
    m.distinct_categories,
    m.sp_apparel     / NULLIF(m.line_spend, 0) AS share_apparel,
    m.sp_home        / NULLIF(m.line_spend, 0) AS share_home,
    m.sp_outdoor     / NULLIF(m.line_spend, 0) AS share_outdoor,
    m.sp_electronics / NULLIF(m.line_spend, 0) AS share_electronics,
    m.sp_beauty      / NULLIF(m.line_spend, 0) AS share_beauty,
    m.sp_grocery     / NULLIF(m.line_spend, 0) AS share_grocery,
    m.sp_toys        / NULLIF(m.line_spend, 0) AS share_toys,
    m.sp_sports      / NULLIF(m.line_spend, 0) AS share_sports,
    m.sp_private_label / NULLIF(m.line_spend, 0) AS share_private_label,
    m.units_total, m.u_apparel, m.u_home, m.u_outdoor, m.u_electronics,
    m.u_beauty, m.u_grocery, m.u_toys, m.u_sports,
    COALESCE(w.web_sessions_6m, 0) * 1.0 / o.orders_365d          AS sessions_per_order,
    COALESCE(w.abandoned_carts_6m, 0) * 1.0 / o.orders_365d       AS abandoned_per_order
FROM seg_base b
JOIN seg_orders o USING (customer_id, as_of_date)
JOIN seg_mix    m USING (customer_id, as_of_date)
LEFT JOIN seg_web w USING (customer_id, as_of_date)
ORDER BY b.as_of_date, b.customer_id;

-- Two years of history at the current snapshot, used to test how much more of the
-- base could be labelled if the persona rule looked back further.
CREATE OR REPLACE TABLE seg_units_24m AS
SELECT
    b.customer_id,
    SUM(i.quantity)                                                             AS units_total,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Apparel'), 0)          AS u_apparel,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Home'), 0)             AS u_home,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Outdoor & Garden'), 0) AS u_outdoor,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Electronics'), 0)      AS u_electronics,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Beauty & Wellness'), 0) AS u_beauty,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Grocery & Pantry'), 0) AS u_grocery,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Toys & Seasonal'), 0)  AS u_toys,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Sports & Fitness'), 0) AS u_sports
FROM seg_base b
JOIN orders o
  ON o.customer_id = b.customer_id
 AND o.order_date >= b.as_of_date - 730
 AND o.order_date <  b.as_of_date
JOIN raw_order_items i ON i.order_id = o.order_id
JOIN raw_products   p ON p.sku = i.sku
WHERE b.snapshot = 'current'
GROUP BY b.customer_id
ORDER BY b.customer_id;

-- What each customer bought in the TWELVE MONTHS AFTER the prior snapshot.
-- Used to test whether a persona predicts the next year's shopping.
CREATE OR REPLACE TABLE seg_next_year AS
SELECT
    b.customer_id,
    SUM(i.quantity * i.unit_price)                                                      AS spend_next,
    SUM(i.quantity)                                                                     AS units_next,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Apparel'), 0)                  AS n_apparel,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Home'), 0)                     AS n_home,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Outdoor & Garden'), 0)         AS n_outdoor,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Electronics'), 0)              AS n_electronics,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Beauty & Wellness'), 0)        AS n_beauty,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Grocery & Pantry'), 0)         AS n_grocery,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Toys & Seasonal'), 0)          AS n_toys,
    COALESCE(SUM(i.quantity) FILTER (WHERE p.category = 'Sports & Fitness'), 0)         AS n_sports
FROM seg_base b
JOIN orders o
  ON o.customer_id = b.customer_id
 AND o.order_date >= b.as_of_date
 AND o.order_date <  b.as_of_date + 365
JOIN raw_order_items i ON i.order_id = o.order_id
JOIN raw_products   p ON p.sku = i.sku
WHERE b.snapshot = 'prior'
GROUP BY b.customer_id
ORDER BY b.customer_id;

CREATE OR REPLACE TABLE seg_qc AS
SELECT 'customers active at the current snapshot' AS check_name,
       (SELECT COUNT(*) FROM seg_features WHERE snapshot = 'current') AS n
UNION ALL SELECT 'customers active at the prior snapshot',  (SELECT COUNT(*) FROM seg_features WHERE snapshot = 'prior')
UNION ALL SELECT 'active at both snapshots (stability test)',
       (SELECT COUNT(*) FROM (SELECT customer_id FROM seg_features GROUP BY customer_id HAVING COUNT(*) = 2))
UNION ALL SELECT 'category shares that do not sum to 1, or are missing (tolerance 0.001)',
       (SELECT COUNT(*) FROM seg_features
        WHERE COALESCE(ABS(share_apparel + share_home + share_outdoor + share_electronics
                + share_beauty + share_grocery + share_toys + share_sports - 1), 9) > 0.001)
UNION ALL SELECT 'channel shares that do not sum to 1, or are missing (tolerance 0.001)',
       (SELECT COUNT(*) FROM seg_features WHERE COALESCE(ABS(store_share + web_share + app_share - 1), 9) > 0.001)
UNION ALL SELECT 'missing value in any clustering input',
       (SELECT COUNT(*) FROM seg_features
        WHERE avg_basket IS NULL OR avg_gap_days IS NULL OR categories_per_order IS NULL
           OR store_share IS NULL OR share_apparel IS NULL OR sessions_per_order IS NULL)
UNION ALL SELECT 'category unit counts that do not add up to the total',
       (SELECT COUNT(*) FROM seg_features
        WHERE u_apparel + u_home + u_outdoor + u_electronics + u_beauty + u_grocery + u_toys + u_sports <> units_total)
UNION ALL SELECT 'orders counted outside the 12-month window', 0;
