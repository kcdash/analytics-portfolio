"""
01_build_features.py
Loads the raw extracts, reuses the shared cleaning SQL from project 1, and builds
the behaviour feature table at two snapshots twelve months apart.
"""
import json

import duckdb

from common import OUT, PROJECT, REPO, WORK

RAW = ["customers", "transactions", "order_items", "products", "campaigns", "campaign_contacts",
       "web_activity_monthly", "service_contacts"]


def main():
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    data = REPO / "data" / "full"
    con = duckdb.connect(str(WORK / "segmentation.duckdb"))
    con.execute("SET threads = 1")      # identical results on every run
    for t in RAW:
        types = ", types={'order_date': 'VARCHAR'}" if t == "transactions" else ""
        con.execute(f"CREATE OR REPLACE TABLE raw_{t} AS SELECT * FROM read_csv('{data / (t + '.csv')}'{types})")
    con.execute((REPO / "projects" / "01-churn-retention" / "sql" / "01_clean.sql").read_text())
    con.execute((PROJECT / "sql" / "01_behaviour_features.sql").read_text())
    qc = dict(con.execute("SELECT check_name, n FROM seg_qc").fetchall())
    (OUT / "qc_log.json").write_text(json.dumps(qc, indent=2))
    for k, v in qc.items():
        print(f"  {v:>9,}  {k}")
    con.execute(f"COPY seg_features TO '{WORK / 'seg_features.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY seg_units_24m TO '{WORK / 'seg_units_24m.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY seg_next_year TO '{WORK / 'seg_next_year.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY (SELECT * FROM seg_features WHERE snapshot = 'current') TO '{WORK / 'seg_features.csv'}' (HEADER)")
    con.close()


if __name__ == "__main__":
    main()
