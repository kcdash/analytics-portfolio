"""
01_build_features.py
Loads the raw Maple & Main extracts into DuckDB, runs the three SQL scripts
(clean -> spine -> features) and writes the two analytical base tables.

    python projects/01-churn-retention/python/01_build_features.py            # full data
    python projects/01-churn-retention/python/01_build_features.py --sample   # 1% sample in the repo
"""
import argparse
import json
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
RAW_TABLES = ["customers", "transactions", "order_items", "products", "campaigns",
              "campaign_contacts", "web_activity_monthly", "service_contacts"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="use data/sample instead of data/full")
    args = ap.parse_args()
    data = REPO / "data" / ("sample" if args.sample else "full")
    work = PROJECT / "work"
    work.mkdir(exist_ok=True)

    con = duckdb.connect(str(work / "churn.duckdb"))
    con.execute("SET threads = 1")      # single thread: identical floating-point sums, so reruns match exactly
    for t in RAW_TABLES:
        # order_date is read as text on purpose: the raw file mixes two date formats
        types = ", types={'order_date': 'VARCHAR'}" if t == "transactions" else ""
        con.execute(f"CREATE OR REPLACE TABLE raw_{t} AS SELECT * FROM read_csv('{data / (t + '.csv')}'{types})")

    for script in ["01_clean.sql", "02_spine.sql", "03_features.sql"]:
        con.execute((PROJECT / "sql" / script).read_text())
        print("ran", script)

    # QC log, checked against the issues the generator planted
    found = dict(con.execute("SELECT check_name, rows_affected FROM qc_log").fetchall())
    planted = json.loads((data / "truth" / "ground_truth.json").read_text())["planted_issues"]
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ["customers", "orders", "churn_abt", "uplift_abt"]}
    (PROJECT / "outputs").mkdir(exist_ok=True)
    if not args.sample:
        (PROJECT / "outputs" / "qc_log.json").write_text(
            json.dumps({"found": found, "planted": planted, "row_counts": counts}, indent=2))
    for k, v in found.items():
        print(f"  {v:>9,}  {k}")
    print(counts)

    con.execute(f"COPY churn_abt  TO '{work / 'churn_abt.parquet'}'  (FORMAT PARQUET)")
    con.execute(f"COPY uplift_abt TO '{work / 'uplift_abt.parquet'}' (FORMAT PARQUET)")
    con.execute(f"COPY churn_abt  TO '{work / 'churn_abt.csv'}' (HEADER)")      # input for the SAS version
    con.close()


if __name__ == "__main__":
    main()
