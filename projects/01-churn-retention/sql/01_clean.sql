-- =============================================================================
-- 01_clean.sql  |  Maple & Main churn project
-- Turns the raw extracts into analysis-ready tables and logs every fix.
-- Dialect: DuckDB (ANSI SQL plus QUALIFY / FILTER / TRY_STRPTIME).
-- Inputs : raw_customers, raw_transactions, raw_order_items, raw_products,
--          raw_campaigns, raw_campaign_contacts, raw_web_activity_monthly,
--          raw_service_contacts
-- =============================================================================

-- Customers: one row per customer_id, province as a two-letter code.
CREATE OR REPLACE TABLE customers AS
SELECT
    customer_id,
    MIN(CAST(join_date AS DATE))            AS join_date,
    MIN(CASE province WHEN 'Ontario' THEN 'ON' WHEN 'Quebec' THEN 'QC'
                      WHEN 'British Columbia' THEN 'BC' WHEN 'Alberta' THEN 'AB'
                      ELSE province END)    AS province,
    MAX(postal_fsa)                         AS postal_fsa,      -- keep the non-missing value
    MIN(age_band)                           AS age_band,
    MIN(loyalty_tier)                       AS loyalty_tier,
    MIN(acquisition_channel)                AS acquisition_channel,
    MAX(email_opt_in)                       AS email_opt_in,
    MAX(sms_opt_in)                         AS sms_opt_in,
    MIN(home_store_id)                      AS home_store_id
FROM raw_customers
GROUP BY customer_id;

-- Order lines carry the reliable amounts: rebuild order totals from them.
CREATE OR REPLACE TABLE order_totals AS
SELECT
    i.order_id,
    SUM(i.quantity * p.list_price)                    AS gross_amount,
    SUM(i.quantity * i.unit_price)                    AS net_amount,
    SUM(i.quantity * (i.unit_price - p.unit_cost))    AS margin_amount,
    COUNT(*)                                          AS n_lines,
    SUM(i.promo_flag)                                 AS n_promo_lines,
    COUNT(DISTINCT p.category)                        AS n_categories
FROM raw_order_items i
JOIN raw_products p USING (sku)
GROUP BY i.order_id;

-- Orders: de-duplicated, one date format, amounts taken from the order lines.
CREATE OR REPLACE TABLE orders AS
WITH dedup AS (
    SELECT * FROM raw_transactions
    QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_date) = 1
)
SELECT
    d.order_id,
    d.customer_id,
    CAST(COALESCE(TRY_STRPTIME(d.order_date, '%Y-%m-%d'),
                  TRY_STRPTIME(d.order_date, '%d/%m/%Y')) AS DATE) AS order_date,
    d.channel,
    d.store_id,
    ROUND(t.gross_amount, 2)                 AS gross_amount,
    ROUND(t.gross_amount - t.net_amount, 2)  AS discount_amount,
    ROUND(t.net_amount, 2)                   AS net_amount,
    ROUND(t.margin_amount, 2)                AS margin_amount,
    t.n_lines, t.n_promo_lines, t.n_categories,
    d.points_redeemed
FROM dedup d
JOIN order_totals t USING (order_id);

CREATE OR REPLACE TABLE campaigns AS
SELECT campaign_id, channel, offer, CAST(start_date AS DATE) AS start_date,
       CAST(end_date AS DATE) AS end_date, cost_per_contact_cad
FROM raw_campaigns;

CREATE OR REPLACE TABLE web_activity AS
SELECT customer_id, CAST(activity_month || '-01' AS DATE) AS month_start,
       sessions, page_views, cart_adds, abandoned_carts
FROM raw_web_activity_monthly;

CREATE OR REPLACE TABLE service_contacts AS
SELECT contact_id, customer_id, CAST(contact_date AS DATE) AS contact_date,
       reason, resolved_flag, csat_score
FROM raw_service_contacts;

-- QC log: what was found and fixed.
CREATE OR REPLACE TABLE qc_log AS
SELECT 'customers: duplicate rows removed' AS check_name,
       (SELECT COUNT(*) FROM raw_customers) - (SELECT COUNT(*) FROM customers) AS rows_affected
UNION ALL
SELECT 'customers: province spelled out, recoded',
       (SELECT COUNT(*) FROM raw_customers WHERE LENGTH(province) > 2)
UNION ALL
SELECT 'customers: postal FSA still missing after de-duplication',
       (SELECT COUNT(*) FROM customers WHERE postal_fsa IS NULL)
UNION ALL
SELECT 'transactions: duplicate rows removed',
       (SELECT COUNT(*) FROM raw_transactions) - (SELECT COUNT(DISTINCT order_id) FROM raw_transactions)
UNION ALL
SELECT 'transactions: order_date in DD/MM/YYYY, re-parsed',
       (SELECT COUNT(*) FROM (SELECT DISTINCT order_id, order_date FROM raw_transactions) WHERE order_date LIKE '%/%')
UNION ALL
SELECT 'transactions: order_date could not be parsed',
       (SELECT COUNT(*) FROM orders WHERE order_date IS NULL)
UNION ALL
SELECT 'transactions: negative net amount, replaced from order lines',
       (SELECT COUNT(*) FROM (SELECT DISTINCT order_id, net_amount FROM raw_transactions) WHERE net_amount < 0)
UNION ALL
SELECT 'transactions: amount 100x the order lines, replaced from order lines',
       (SELECT COUNT(*) FROM (SELECT DISTINCT order_id, gross_amount FROM raw_transactions) r
          JOIN order_totals t USING (order_id) WHERE r.gross_amount > 50 * t.gross_amount)
UNION ALL
SELECT 'transactions: orders with no order lines',
       (SELECT COUNT(DISTINCT order_id) FROM raw_transactions) - (SELECT COUNT(*) FROM orders);
