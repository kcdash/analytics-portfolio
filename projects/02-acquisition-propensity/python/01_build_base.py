"""
01_build_base.py
Loads the raw extracts, reuses the shared cleaning SQL from project 1, then builds
the prospect base table and the first-year value of acquired customers.
"""
import json

import duckdb

from common import OUT, PROJECT, REPO, WORK

RAW = ["customers", "transactions", "order_items", "products", "campaigns", "campaign_contacts",
       "web_activity_monthly", "service_contacts", "prospects"]


def main():
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    data = REPO / "data" / "full"
    con = duckdb.connect(str(WORK / "acquisition.duckdb"))
    con.execute("SET threads = 1")     # identical results on every run
    for t in RAW:
        types = ", types={'order_date': 'VARCHAR'}" if t == "transactions" else ""
        con.execute(f"CREATE OR REPLACE TABLE raw_{t} AS SELECT * FROM read_csv('{data / (t + '.csv')}'{types})")
    con.execute((REPO / "projects" / "01-churn-retention" / "sql" / "01_clean.sql").read_text())   # shared cleaning layer
    for script in ["01_prospect_base.sql", "02_customer_value.sql"]:
        con.execute((PROJECT / "sql" / script).read_text())
        print("ran", script)
    qc = dict(con.execute("SELECT check_name, n FROM prospect_qc").fetchall())
    (OUT / "qc_log.json").write_text(json.dumps(qc, indent=2))
    for k, v in qc.items():
        print(f"  {v:>8,}  {k}")
    con.execute(f"COPY prospect_abt TO '{WORK / 'prospect_abt.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY prospect_abt TO '{WORK / 'prospect_abt.csv'}' (HEADER)")          # input for the SAS version
    con.execute(f"COPY new_customer_value TO '{WORK / 'new_customer_value.parquet'}' (FORMAT PARQUET)")
    con.close()


if __name__ == "__main__":
    main()
