"""Database tool — query and manage SQLite databases.

Default: SQLite (no setup needed). MySQL/PostgreSQL support via
connection strings in future phases.
"""

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any

import aiosqlite

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class DatabaseTool(BaseTool):
    """Query and manage databases."""

    name = "database"
    description = (
        "Interact with SQLite databases: connect, run SQL queries, "
        "describe tables, list tables, and export data to CSV/JSON."
    )
    requires_confirmation = True  # Write queries need confirmation
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "connect",
                    "query",
                    "describe_table",
                    "list_tables",
                    "export_data",
                    "import_data",
                    "create_backup",
                ],
                "description": "The database action",
            },
            "db_path": {
                "type": "string",
                "description": "Path to SQLite database file",
            },
            "sql": {
                "type": "string",
                "description": "SQL query to execute (for query, export_data)",
            },
            "table_name": {
                "type": "string",
                "description": "Table name (for describe_table)",
            },
            "output_path": {
                "type": "string",
                "description": "Output file path (for export_data)",
            },
            "format": {
                "type": "string",
                "enum": ["csv", "json"],
                "description": "Export format (for export_data, default csv)",
            },
            "input_path": {
                "type": "string",
                "description": "Input file path (for import_data, CSV or JSON)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._db: aiosqlite.Connection | None = None
        self._db_path: str = ""

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "connect":
                return await self._connect(kwargs.get("db_path", ""))
            elif action == "query":
                return await self._query(kwargs.get("sql", ""), kwargs.get("db_path", ""))
            elif action == "describe_table":
                return await self._describe_table(
                    kwargs.get("table_name", ""), kwargs.get("db_path", "")
                )
            elif action == "list_tables":
                return await self._list_tables(kwargs.get("db_path", ""))
            elif action == "export_data":
                return await self._export_data(
                    kwargs.get("sql", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("format", "csv"),
                    kwargs.get("db_path", ""),
                )
            elif action == "import_data":
                return await self._import_data(
                    kwargs.get("input_path", ""),
                    kwargs.get("table_name", ""),
                    kwargs.get("db_path", ""),
                )
            elif action == "create_backup":
                return await self._create_backup(
                    kwargs.get("db_path", ""),
                    kwargs.get("output_path", ""),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Database error: %s", action)
            return f"Database error: {e}"

    async def _ensure_connection(self, db_path: str = "") -> aiosqlite.Connection:
        """Connect to DB, reusing existing connection if path matches."""
        path = db_path or self._db_path
        if not path:
            raise ValueError("No database path. Use 'connect' first or provide db_path.")

        if self._db and self._db_path == path:
            return self._db

        if self._db:
            await self._db.close()

        resolved = str(Path(path).expanduser().resolve())
        self._db = await aiosqlite.connect(resolved)
        self._db.row_factory = aiosqlite.Row
        self._db_path = path
        return self._db

    async def _connect(self, db_path: str) -> str:
        if not db_path:
            return "Error: db_path is required."
        db = await self._ensure_connection(db_path)
        # Quick test
        cursor = await db.execute("SELECT sqlite_version()")
        row = await cursor.fetchone()
        version = row[0] if row else "unknown"
        return f"Connected to {db_path} (SQLite {version})"

    async def _query(self, sql: str, db_path: str) -> str:
        if not sql:
            return "Error: sql is required."

        db = await self._ensure_connection(db_path)
        cursor = await db.execute(sql)

        if sql.strip().upper().startswith("SELECT") or sql.strip().upper().startswith("PRAGMA"):
            rows = await cursor.fetchall()
            if not rows:
                return "Query returned no results."

            # Get column names
            cols = [d[0] for d in cursor.description]

            # Format as table
            lines = [" | ".join(cols)]
            lines.append("-" * len(lines[0]))
            for row in rows[:100]:
                lines.append(" | ".join(str(row[c]) for c in cols))

            result = "\n".join(lines)
            if len(rows) > 100:
                result += f"\n\n... showing 100 of {len(rows)} rows"
            return result
        else:
            await db.commit()
            return f"Query executed. Rows affected: {cursor.rowcount}"

    async def _describe_table(self, table_name: str, db_path: str) -> str:
        if not table_name:
            return "Error: table_name is required."
        db = await self._ensure_connection(db_path)
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        rows = await cursor.fetchall()
        if not rows:
            return f"Table '{table_name}' not found."

        lines = [f"Schema for '{table_name}':\n"]
        lines.append("  Column | Type | NotNull | Default | PK")
        lines.append("  " + "-" * 45)
        for row in rows:
            lines.append(
                f"  {row['name']} | {row['type']} | "
                f"{'YES' if row['notnull'] else 'NO'} | "
                f"{row['dflt_value'] or 'NULL'} | "
                f"{'YES' if row['pk'] else 'NO'}"
            )

        # Row count
        cursor2 = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
        count_row = await cursor2.fetchone()
        lines.append(f"\n  Total rows: {count_row[0]}")
        return "\n".join(lines)

    async def _list_tables(self, db_path: str) -> str:
        db = await self._ensure_connection(db_path)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        if not rows:
            return "No tables found."

        lines = ["Tables:\n"]
        for row in rows:
            lines.append(f"  - {row['name']}")
        return "\n".join(lines)

    async def _export_data(
        self, sql: str, output_path: str, fmt: str, db_path: str
    ) -> str:
        if not sql:
            return "Error: sql is required."
        if not output_path:
            return "Error: output_path is required."

        db = await self._ensure_connection(db_path)
        cursor = await db.execute(sql)
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]

        path = Path(output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "json":
            data = [dict(zip(cols, row)) for row in rows]
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        else:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(cols)
            for row in rows:
                writer.writerow(row)
            path.write_text(buf.getvalue(), encoding="utf-8")

        return f"Exported {len(rows)} rows to {path} ({fmt})"

    async def _import_data(self, input_path: str, table_name: str, db_path: str) -> str:
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

        db = await self._ensure_connection(db_path)

        # Create table if it doesn't exist (all TEXT columns)
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

    async def _create_backup(self, db_path: str, output_path: str) -> str:
        """Create a backup copy of a SQLite database."""
        if not db_path:
            return "Error: db_path is required."

        src = Path(db_path).expanduser()
        if not src.exists():
            return f"Error: Database not found: {src}"

        if output_path:
            dest = Path(output_path).expanduser()
        else:
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = src.with_name(f"{src.stem}_backup_{ts}{src.suffix}")

        dest.parent.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.copy2(str(src), str(dest))

        size_kb = dest.stat().st_size / 1024
        return f"Backup created: {dest} ({size_kb:.1f} KB)"
