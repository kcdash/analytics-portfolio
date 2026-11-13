"""
01_build_series.py
Loads the raw extracts, reuses the shared cleaning SQL from project 1, and builds
weekly demand at four levels together with the calendar and media plan.
"""
import json

import duckdb

from common import OUT, PROJECT, REPO, WORK

RAW = ["customers", "transactions", "order_items", "products", "stores",
       "media_spend_weekly", "campaigns", "campaign_contacts", "web_activity_monthly", "service_contacts"]


def main():
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    data = REPO / "data" / "full"
    con = duckdb.connect(str(WORK / "forecast.duckdb"))
    con.execute("SET threads = 1")      # identical results on every run
    for t in RAW:
        types = ", types={'order_date': 'VARCHAR'}" if t == "transactions" else ""
        con.execute(f"CREATE OR REPLACE TABLE raw_{t} AS SELECT * FROM read_csv('{data / (t + '.csv')}'{types})")
    con.execute((REPO / "projects" / "01-churn-retention" / "sql" / "01_clean.sql").read_text())
    con.execute((PROJECT / "sql" / "01_weekly_series.sql").read_text())
    qc = dict(con.execute("SELECT check_name, n FROM forecast_qc").fetchall())
    (OUT / "qc_log.json").write_text(json.dumps(qc, indent=2))
    for k, v in qc.items():
        print(f"  {v:>9,}  {k}")
    con.execute(f"COPY series   TO '{WORK / 'series.parquet'}'   (FORMAT PARQUET)")
    con.execute(f"COPY calendar TO '{WORK / 'calendar.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY (SELECT * FROM series WHERE level IN ('Total', 'Category')) TO '{WORK / 'series.csv'}' (HEADER)")
    con.execute(f"COPY calendar TO '{WORK / 'calendar.csv'}' (HEADER)")      # input for the SAS version
    con.close()


if __name__ == "__main__":
    main()
