-- =============================================================================
-- 03_features.sql  |  Point-in-time features for every spine row
-- Rule: a feature may only use rows dated before as_of_date. No exceptions.
-- The same feature table feeds the churn model and the uplift model.
-- =============================================================================

-- Purchase behaviour (recency, frequency, value, trend, mix)
CREATE OR REPLACE TABLE f_orders AS
SELECT
    s.customer_id, s.as_of_date,
    DATE_DIFF('day', MAX(o.order_date), s.as_of_date)                              AS recency_days,
    COUNT(*) FILTER (WHERE o.order_date >= s.as_of_date - 90)                      AS orders_90d,
    COUNT(*) FILTER (WHERE o.order_date >= s.as_of_date - 180
                       AND o.order_date <  s.as_of_date - 90)                      AS orders_prev_90d,
    COUNT(*)                                                                       AS orders_365d,
    SUM(o.net_amount)                                                              AS spend_365d,
    SUM(o.net_amount) FILTER (WHERE o.order_date >= s.as_of_date - 90)             AS spend_90d,
    SUM(o.margin_amount)                                                           AS margin_365d,
    AVG(o.net_amount)                                                              AS avg_basket_365d,
    SUM(o.discount_amount) / NULLIF(SUM(o.gross_amount), 0)                        AS discount_share_365d,
    SUM(o.n_promo_lines) * 1.0 / SUM(o.n_lines)                                    AS promo_line_share_365d,
    AVG(o.n_categories)                                                            AS avg_categories_per_order,
    AVG(CASE WHEN o.channel <> 'Store' THEN 1.0 ELSE 0 END)                        AS digital_order_share_365d,
    COUNT(*) FILTER (WHERE o.points_redeemed > 0)                                  AS redemptions_365d,
    -- average days between orders; NULL when there is only one order
    DATE_DIFF('day', MIN(o.order_date), MAX(o.order_date)) * 1.0
        / NULLIF(COUNT(*) - 1, 0)                                                  AS avg_gap_days
FROM spine s
JOIN orders o
  ON o.customer_id = s.customer_id
 AND o.order_date <  s.as_of_date
 AND o.order_date >= s.as_of_date - 365
GROUP BY s.customer_id, s.as_of_date;

-- Web behaviour: complete calendar months before the as-of month
CREATE OR REPLACE TABLE f_web AS
SELECT
    s.customer_id, s.as_of_date,
    SUM(w.sessions) FILTER (WHERE w.month_start >= DATE_TRUNC('month', s.as_of_date) - INTERVAL 1 MONTH)   AS web_sessions_1m,
    SUM(w.sessions) FILTER (WHERE w.month_start >= DATE_TRUNC('month', s.as_of_date) - INTERVAL 3 MONTH)   AS web_sessions_3m,
    SUM(w.sessions) FILTER (WHERE w.month_start <  DATE_TRUNC('month', s.as_of_date) - INTERVAL 3 MONTH)   AS web_sessions_prev_3m,
    SUM(w.abandoned_carts) FILTER (WHERE w.month_start >= DATE_TRUNC('month', s.as_of_date) - INTERVAL 3 MONTH) AS abandoned_carts_3m
FROM spine s
JOIN web_activity w
  ON w.customer_id = s.customer_id
 AND w.month_start <  DATE_TRUNC('month', s.as_of_date)
 AND w.month_start >= DATE_TRUNC('month', s.as_of_date) - INTERVAL 6 MONTH
GROUP BY s.customer_id, s.as_of_date;

-- Service friction
CREATE OR REPLACE TABLE f_service AS
SELECT
    s.customer_id, s.as_of_date,
    COUNT(*) FILTER (WHERE sc.contact_date >= s.as_of_date - 90)                             AS service_contacts_90d,
    COUNT(*)                                                                                 AS service_contacts_365d,
    COUNT(*) FILTER (WHERE sc.reason IN ('Delivery', 'Return/Refund', 'Product quality')
                       AND sc.contact_date >= s.as_of_date - 180)                            AS complaints_180d,
    COUNT(*) FILTER (WHERE sc.resolved_flag = 0 AND sc.contact_date >= s.as_of_date - 180)   AS unresolved_180d,
    MIN(sc.csat_score) FILTER (WHERE sc.contact_date >= s.as_of_date - 180)                  AS min_csat_180d
FROM spine s
JOIN service_contacts sc
  ON sc.customer_id = s.customer_id
 AND sc.contact_date <  s.as_of_date
 AND sc.contact_date >= s.as_of_date - 365
GROUP BY s.customer_id, s.as_of_date;

-- CRM contact history (campaigns that started before the as-of date)
CREATE OR REPLACE TABLE f_crm AS
SELECT
    s.customer_id, s.as_of_date,
    SUM(cc.sent_flag)        AS crm_contacts_365d,
    SUM(cc.opened_flag)      AS crm_opens_365d,
    SUM(cc.clicked_flag)     AS crm_clicks_365d
FROM spine s
JOIN raw_campaign_contacts cc ON cc.customer_id = s.customer_id
JOIN campaigns cp
  ON cp.campaign_id = cc.campaign_id
 AND cp.start_date <  s.as_of_date
 AND cp.start_date >= s.as_of_date - 365
GROUP BY s.customer_id, s.as_of_date;

-- One row per spine row
CREATE OR REPLACE TABLE features AS
SELECT
    s.customer_id, s.as_of_date,
    DATE_DIFF('day', c.join_date, s.as_of_date)          AS tenure_days,
    c.province, c.age_band, c.loyalty_tier, c.acquisition_channel, c.email_opt_in, c.sms_opt_in,
    COALESCE(o.recency_days, 366)                        AS recency_days,
    COALESCE(o.orders_90d, 0)                            AS orders_90d,
    COALESCE(o.orders_prev_90d, 0)                       AS orders_prev_90d,
    COALESCE(o.orders_365d, 0)                           AS orders_365d,
    COALESCE(o.spend_365d, 0)                            AS spend_365d,
    COALESCE(o.spend_90d, 0)                             AS spend_90d,
    COALESCE(o.margin_365d, 0)                           AS margin_365d,
    o.avg_basket_365d,
    o.discount_share_365d,
    o.promo_line_share_365d,
    o.avg_categories_per_order,
    o.digital_order_share_365d,
    COALESCE(o.redemptions_365d, 0)                      AS redemptions_365d,
    o.avg_gap_days,
    -- how overdue is the next order, relative to this customer's own rhythm?
    o.recency_days / NULLIF(o.avg_gap_days, 0)           AS overdue_ratio,
    COALESCE(w.web_sessions_1m, 0)                       AS web_sessions_1m,
    COALESCE(w.web_sessions_3m, 0)                       AS web_sessions_3m,
    COALESCE(w.web_sessions_prev_3m, 0)                  AS web_sessions_prev_3m,
    COALESCE(w.abandoned_carts_3m, 0)                    AS abandoned_carts_3m,
    COALESCE(v.service_contacts_90d, 0)                  AS service_contacts_90d,
    COALESCE(v.service_contacts_365d, 0)                 AS service_contacts_365d,
    COALESCE(v.complaints_180d, 0)                       AS complaints_180d,
    COALESCE(v.unresolved_180d, 0)                       AS unresolved_180d,
    v.min_csat_180d,
    COALESCE(m.crm_contacts_365d, 0)                     AS crm_contacts_365d,
    COALESCE(m.crm_opens_365d, 0)                        AS crm_opens_365d,
    COALESCE(m.crm_clicks_365d, 0)                       AS crm_clicks_365d
FROM spine s
JOIN customers c USING (customer_id)
LEFT JOIN f_orders  o USING (customer_id, as_of_date)
LEFT JOIN f_web     w USING (customer_id, as_of_date)
LEFT JOIN f_service v USING (customer_id, as_of_date)
LEFT JOIN f_crm     m USING (customer_id, as_of_date);

-- Analytical base tables
CREATE OR REPLACE TABLE churn_abt AS
SELECT s.role, s.churn_180d, f.*
FROM churn_spine s JOIN features f USING (customer_id, as_of_date)
ORDER BY f.as_of_date, f.customer_id;              -- fixed row order keeps model training reproducible

CREATE OR REPLACE TABLE uplift_abt AS
SELECT s.campaign_id, s.channel, s.offer, s.cost_per_contact_cad, s.treated, s.responded_flag,
       s.net_14d, s.margin_14d, s.active_next_180d, f.*
FROM campaign_spine s JOIN features f USING (customer_id, as_of_date)
ORDER BY s.campaign_id, f.customer_id;
