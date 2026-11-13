-- =============================================================================
-- 01_prospect_base.sql  |  Maple & Main acquisition project
-- One row per prospect, ready for modelling, plus a QC log.
-- Dialect: DuckDB.  Inputs: raw_prospects, and the cleaned customers / orders
-- tables built by the shared cleaning script (projects/01-churn-retention/sql/01_clean.sql).
-- =============================================================================

-- Prospects whose conversion window is fully observed.
--   * Conversion can take up to 45 days after first contact, so the last 45 days
--     of data are dropped: those prospects have not had time to convert.
--   * The first weeks of data only contain prospects who converted (the customer
--     file starts in November 2023), so the base starts on 1 January 2024.
CREATE OR REPLACE TABLE prospect_abt AS
SELECT
    p.prospect_id,
    CAST(p.first_contact_date AS DATE)                         AS first_contact_date,
    CASE WHEN CAST(p.first_contact_date AS DATE) < DATE '2025-10-01' THEN 'train' ELSE 'test' END AS role,
    p.lead_source,
    p.province,
    p.age_band,
    p.household_income_band,
    CASE p.household_income_band WHEN '<50k' THEN 0 WHEN '50-75k' THEN 1 WHEN '75-100k' THEN 2
                                 WHEN '100-150k' THEN 3 ELSE 4 END AS income_rank,
    p.has_children,
    p.distance_to_store_km,
    p.web_visits_30d,
    LEAST(p.web_visits_30d, 8)                                 AS web_visits_capped,   -- fewer than 0.1% have more than 8; capped so a handful of extremes do not steer the scorecard
    p.email_engaged_flag,
    p.converted_flag,
    p.converted_customer_id
FROM raw_prospects p
WHERE CAST(p.first_contact_date AS DATE) >= DATE '2024-01-01'
  AND CAST(p.first_contact_date AS DATE) <= DATE '2026-09-15'
ORDER BY p.prospect_id;

CREATE OR REPLACE TABLE prospect_qc AS
SELECT 'prospects in raw file' AS check_name, COUNT(*) AS n FROM raw_prospects
UNION ALL SELECT 'duplicate prospect_id', COUNT(*) - COUNT(DISTINCT prospect_id) FROM raw_prospects
UNION ALL SELECT 'dropped: first contact before 2024-01-01 (converters only)', COUNT(*) FROM raw_prospects WHERE CAST(first_contact_date AS DATE) < DATE '2024-01-01'
UNION ALL SELECT 'dropped: first contact after 2026-09-15 (conversion window still open)', COUNT(*) FROM raw_prospects WHERE CAST(first_contact_date AS DATE) > DATE '2026-09-15'
UNION ALL SELECT 'kept for modelling', COUNT(*) FROM prospect_abt
UNION ALL SELECT 'missing value in any model input', COUNT(*) FROM prospect_abt
          WHERE lead_source IS NULL OR age_band IS NULL OR household_income_band IS NULL OR has_children IS NULL
             OR distance_to_store_km IS NULL OR web_visits_30d IS NULL OR email_engaged_flag IS NULL
UNION ALL SELECT 'distance below 0 or above 150 km', COUNT(*) FROM prospect_abt WHERE distance_to_store_km < 0 OR distance_to_store_km > 150
UNION ALL SELECT 'converted flag without a customer id', COUNT(*) FROM prospect_abt WHERE converted_flag = 1 AND converted_customer_id IS NULL
UNION ALL SELECT 'customer id without a converted flag', COUNT(*) FROM prospect_abt WHERE converted_flag = 0 AND converted_customer_id IS NOT NULL
UNION ALL SELECT 'converted customer id not found in customer file', COUNT(*) FROM prospect_abt p
          LEFT JOIN customers c ON c.customer_id = p.converted_customer_id WHERE p.converted_flag = 1 AND c.customer_id IS NULL
UNION ALL SELECT 'converted before first contact', COUNT(*) FROM prospect_abt p
          JOIN customers c ON c.customer_id = p.converted_customer_id WHERE c.join_date < p.first_contact_date
UNION ALL SELECT 'converted more than 45 days after first contact', COUNT(*) FROM prospect_abt p
          JOIN customers c ON c.customer_id = p.converted_customer_id WHERE c.join_date > p.first_contact_date + 45;
