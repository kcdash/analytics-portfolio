-- =============================================================================
-- 02_spine.sql  |  Who gets scored, and when
-- A "spine" row is one customer at one as-of date. Two sources share it:
--   1. Churn snapshots  : every active customer on six snapshot dates
--   2. Campaign contacts: every customer in a CRM campaign, as of its start date
-- All features are built from data strictly before the as-of date.
-- =============================================================================

CREATE OR REPLACE TABLE snapshots AS
SELECT * FROM (VALUES
    (DATE '2024-11-04', 'train'),
    (DATE '2025-02-03', 'train'),
    (DATE '2025-05-05', 'train'),
    (DATE '2025-08-04', 'train'),
    (DATE '2025-11-03', 'validate'),   -- used for probability calibration
    (DATE '2026-05-04', 'test')        -- untouched out-of-time test
) AS t(as_of_date, role);

-- Active customer = joined at least 30 days ago and ordered in the last 180 days.
-- Churn label     = no order in the 180 days from the snapshot date.
CREATE OR REPLACE TABLE churn_spine AS
SELECT
    c.customer_id,
    s.as_of_date,
    s.role,
    CASE WHEN EXISTS (SELECT 1 FROM orders o
                      WHERE o.customer_id = c.customer_id
                        AND o.order_date >= s.as_of_date
                        AND o.order_date <  s.as_of_date + 180)
         THEN 0 ELSE 1 END AS churn_180d
FROM customers c
CROSS JOIN snapshots s
WHERE c.join_date <= s.as_of_date - 30
  AND EXISTS (SELECT 1 FROM orders o
              WHERE o.customer_id = c.customer_id
                AND o.order_date >= s.as_of_date - 180
                AND o.order_date <  s.as_of_date);

-- Campaign contacts from November 2024 on, so each has a year of history behind it.
CREATE OR REPLACE TABLE campaign_spine AS
SELECT
    cc.campaign_id, cc.customer_id, cp.start_date AS as_of_date,
    cp.channel, cp.offer, cp.cost_per_contact_cad,
    CASE WHEN cc.treatment_group = 'Treatment' THEN 1 ELSE 0 END AS treated,
    cc.responded_flag,
    -- measured outcomes in the 14-day response window
    COALESCE(SUM(o.net_amount)    FILTER (WHERE o.order_date <  cp.start_date + 14), 0) AS net_14d,
    COALESCE(SUM(o.margin_amount) FILTER (WHERE o.order_date <  cp.start_date + 14), 0) AS margin_14d,
    -- did the customer keep buying in the six months after the response window?
    MAX(CASE WHEN o.order_date >= cp.start_date + 14 THEN 1 ELSE 0 END)                 AS active_next_180d
FROM raw_campaign_contacts cc
JOIN campaigns cp USING (campaign_id)
LEFT JOIN orders o
       ON o.customer_id = cc.customer_id
      AND o.order_date >= cp.start_date
      AND o.order_date <  cp.start_date + 194
WHERE cp.start_date >= DATE '2024-11-04'
GROUP BY ALL;

CREATE OR REPLACE TABLE spine AS
SELECT customer_id, as_of_date FROM churn_spine
UNION
SELECT customer_id, as_of_date FROM campaign_spine;
