"""Generate the data dictionary (deliverable D4) from the comments in sql/ddl.sql.

    python -m src.dictionary        # writes docs/data_dictionary.csv
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .config import PROJECT_ROOT, SQL_DIR

TABLE_RE = re.compile(r"^-- @table (\w+): (.*)$")
CREATE_RE = re.compile(r"^CREATE TABLE (\w+)")
COLUMN_RE = re.compile(r"^\s+(\w+)\s+([A-Z]+)(.*?)(?:--\s*(.*))?$")


def parse(ddl: str) -> pd.DataFrame:
    rows, table, table_desc, descs = [], None, "", {}
    for line in ddl.splitlines():
        if m := TABLE_RE.match(line):
            descs[m.group(1)] = m.group(2)
        elif m := CREATE_RE.match(line):
            table, table_desc = m.group(1), descs.get(m.group(1), "")
        elif table and line.startswith(")"):
            table = None
        elif table and (m := COLUMN_RE.match(line)) and m.group(1) != "PRIMARY":
            rest = m.group(3)
            fk = re.search(r"REFERENCES (\w+)\((\w+)\)", rest)
            rows.append({
                "table": table, "table_description": table_desc, "column": m.group(1),
                "type": m.group(2),
                "nullable": "NOT NULL" not in rest and "PRIMARY KEY" not in rest,
                "key": "PK" if "PRIMARY KEY" in rest else ("FK" if fk else ""),
                "references": f"{fk.group(1)}.{fk.group(2)}" if fk else "",
                "description": (m.group(4) or "").strip(),
            })
        if table and (m := re.match(r"^\s+PRIMARY KEY \(([^)]*)\)", line)):
            for col in (c.strip() for c in m.group(1).split(",")):
                for r in rows:
                    if r["table"] == table and r["column"] == col:
                        r["key"] = "PK" if not r["key"] else "PK, FK"
    return pd.DataFrame(rows)


def main(out: Path = PROJECT_ROOT / "docs" / "data_dictionary.csv") -> pd.DataFrame:
    df = parse((SQL_DIR / "ddl.sql").read_text())
    df.to_csv(out, index=False)
    return df


if __name__ == "__main__":
    print(f"{len(main())} columns written")
