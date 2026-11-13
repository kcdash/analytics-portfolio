-- =============================================================================
-- 02_customer_value.sql  |  What is a newly acquired customer worth?
-- First-year margin for every converted prospect with a full year of history.
-- Customers who never order, or stop early, stay in with what they spent:
-- this is the expected value of an acquisition, not the value of a good one.
-- =============================================================================
CREATE OR REPLACE TABLE new_customer_value AS
SELECT
    p.prospect_id,
    p.lead_source,
    c.customer_id,
    c.join_date,
    COUNT(o.order_id)                       AS orders_first_year,
    COALESCE(SUM(o.net_amount), 0)          AS spend_first_year,
    COALESCE(SUM(o.margin_amount), 0)       AS margin_first_year,
    MAX(CASE WHEN o.order_date >= c.join_date + 183 THEN 1 ELSE 0 END) AS active_second_half
FROM prospect_abt p
JOIN customers c ON c.customer_id = p.converted_customer_id
LEFT JOIN orders o
       ON o.customer_id = c.customer_id
      AND o.order_date >= c.join_date
      AND o.order_date <  c.join_date + 365
WHERE p.converted_flag = 1
  AND c.join_date <= DATE '2025-11-01'      -- a full year of orders is observed
GROUP BY ALL
ORDER BY p.prospect_id;
