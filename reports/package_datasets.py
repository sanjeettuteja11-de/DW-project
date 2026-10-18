"""Package the raw and cleaned dataset files (submission item 6).

    python reports/package_datasets.py

Writes submission/06_Datasets.zip with:
  raw/        matches.csv, deliveries.csv exactly as downloaded (checksums in README)
  clean/      clean_matches.csv, clean_deliveries.csv and the mapping tables
  warehouse/  ipl_dw.sqlite (star schema + views) and every dimension / fact as CSV
  README.txt  what each folder holds and how to regenerate everything from the raw files
"""
import sqlite3
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "submission" / "06_Datasets.zip"
DB = ROOT / "db" / "ipl_dw.sqlite"


def main():
    ext = pd.read_csv(ROOT / "logs" / "extraction_log.csv").drop_duplicates("file", keep="last").set_index("file")
    con = sqlite3.connect(DB)
    tmp = ROOT / "data" / "clean"
    for t in ("clean_matches", "clean_deliveries"):
        pd.read_sql(f"SELECT * FROM {t}", con).to_csv(tmp / f"{t}.csv", index=False)
    fact_delivery = pd.read_sql("SELECT * FROM fact_delivery", con)
    con.close()
    fd_csv = ROOT / "data" / "export" / "fact_delivery.csv"
    fact_delivery.to_csv(fd_csv, index=False)

    readme = f"""IPL Phase-Performance and Style-Drift Data Warehouse - dataset files
=====================================================================

raw/        The two source files exactly as downloaded (never edited).
            Source: {ext.loc['matches.csv', 'source_url']}
            Version: {ext.loc['matches.csv', 'dataset_version']}; downloaded {ext.loc['matches.csv', 'download_date']}
            matches.csv     {ext.loc['matches.csv', 'rows']:>7} rows  sha256 {ext.loc['matches.csv', 'sha256']}
            deliveries.csv  {ext.loc['deliveries.csv', 'rows']:>7} rows  sha256 {ext.loc['deliveries.csv', 'sha256']}
            Licence: Open Database License / Database Contents License (Kaggle);
            ball-by-ball data from Cricsheet (cricsheet.org), Open Data Commons Attribution License.

clean/      Cleaned, normalised and flagged tables (steps E4-E6) and the canonical mapping tables
            used to resolve team, venue and player names.

warehouse/  ipl_dw.sqlite: the star schema (3 facts, 7 dimensions) and analysis views, plus
            each table as CSV. fact_delivery.csv is the delivery-grain fact (260,920 rows).

Regenerate everything from the raw files (Python 3.11+):
    pip install -r requirements.txt
    copy raw/matches.csv and raw/deliveries.csv into data/raw/ of the project repository
    python -m src.pipeline      # ETL, validation gates, exports
    python -m src.analysis      # insights tables and figures
    python -m src.ml            # models
    python -m src.powerbi       # Power BI workbook
or open notebooks/IPL_DW_Project.ipynb and Run All.
"""
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("README.txt", readme)
        for f in ("matches.csv", "deliveries.csv"):
            z.write(ROOT / "data" / "raw" / f, f"raw/{f}")
        for f in ("clean_matches.csv", "clean_deliveries.csv", "map_team.csv", "map_venue.csv", "map_player.csv"):
            z.write(tmp / f, f"clean/{f}")
        z.write(DB, "warehouse/ipl_dw.sqlite")
        for f in sorted((ROOT / "data" / "export").glob("*.csv")):
            if f.name.startswith(("dim_", "fact_")):
                z.write(f, f"warehouse/{f.name}")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
