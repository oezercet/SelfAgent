"""Database helper functions for import and backup operations."""

import csv
import io
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


async def import_data(
    db: aiosqlite.Connection, input_path: str, table_name: str
) -> str:
    """Import data from CSV or JSON file into a table."""
    if not input_path:
        return "Error: input_path is required."
    if not table_name:
        return "Error: table_name is required."

    src = Path(input_path).expanduser()
    if not src.exists():
        return f"Error: File not found: {src}"

    ext = src.suffix.lower()
    content = src.read_text(encoding="utf-8")

    if ext == ".json":
        data = json.loads(content)
        if not data or not isinstance(data, list):
            return "Error: JSON file must contain a list of objects."
        cols = list(data[0].keys())
        rows_data = [tuple(row.get(c) for c in cols) for row in data]
    elif ext == ".csv":
        reader = csv.DictReader(io.StringIO(content))
        cols = reader.fieldnames
        if not cols:
            return "Error: CSV file has no headers."
        rows_data = [tuple(row.get(c) for c in cols) for row in reader]
    else:
        return f"Error: Unsupported file format '{ext}'. Use .csv or .json."

    if not rows_data:
        return "Error: No data rows found in file."

    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
    await db.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')

    placeholders = ", ".join("?" for _ in cols)
    col_names = ", ".join(f'"{c}"' for c in cols)
    await db.executemany(
        f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})',
        rows_data,
    )
    await db.commit()

    return f"Imported {len(rows_data)} rows into '{table_name}' from {src}"


async def create_backup(db_path: str, output_path: str) -> str:
    """Create a backup copy of a SQLite database."""
    if not db_path:
        return "Error: db_path is required."

    src = Path(db_path).expanduser()
    if not src.exists():
        return f"Error: Database not found: {src}"

    if output_path:
        dest = Path(output_path).expanduser()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = src.with_name(f"{src.stem}_backup_{ts}{src.suffix}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))

    size_kb = dest.stat().st_size / 1024
    return f"Backup created: {dest} ({size_kb:.1f} KB)"
