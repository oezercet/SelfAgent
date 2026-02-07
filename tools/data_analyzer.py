"""Data analyzer tool — load, explore, query, and visualize datasets.

Uses pandas for data manipulation and matplotlib for charts.
Supports CSV, JSON, Excel files.
"""

import json
import logging
from pathlib import Path
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage" / "charts"


class DataAnalyzerTool(BaseTool):
    name = "data_analyzer"
    description = (
        "Analyze data: load datasets, compute statistics, run queries, "
        "create charts and visualizations, and export reports."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "load_data",
                    "describe_data",
                    "query_data",
                    "create_chart",
                    "export_report",
                    "compare_datasets",
                    "clean_data",
                ],
                "description": "The data analysis action to perform",
            },
            "file_path": {
                "type": "string",
                "description": "Path to the data file (for 'load_data')",
            },
            "dataset_id": {
                "type": "string",
                "description": "Identifier for a previously loaded dataset",
            },
            "query": {
                "type": "string",
                "description": "pandas query string (for 'query_data'), e.g. 'age > 30'",
            },
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "scatter", "pie", "histogram", "heatmap"],
                "description": "Type of chart to create (for 'create_chart')",
            },
            "x_column": {
                "type": "string",
                "description": "Column for X axis (for 'create_chart')",
            },
            "y_column": {
                "type": "string",
                "description": "Column for Y axis (for 'create_chart')",
            },
            "output_path": {
                "type": "string",
                "description": "Output file path (for 'create_chart', 'export_report')",
            },
            "format": {
                "type": "string",
                "enum": ["html", "csv", "json"],
                "description": "Export format (for 'export_report')",
            },
            "file_path_2": {
                "type": "string",
                "description": "Path to second data file (for 'compare_datasets')",
            },
            "operations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Cleaning ops: 'drop_duplicates', 'drop_nulls', 'fill_nulls:0', 'lowercase:col', 'strip_whitespace' (for 'clean_data')",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._datasets: dict[str, Any] = {}  # id -> DataFrame
        self._counter = 0

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            import pandas as pd
        except ImportError:
            return "Error: pandas is not installed. Run: pip install pandas"

        try:
            if action == "load_data":
                return self._load_data(pd, kwargs.get("file_path", ""))
            elif action == "describe_data":
                return self._describe_data(pd, kwargs.get("dataset_id", ""))
            elif action == "query_data":
                return self._query_data(
                    pd,
                    kwargs.get("dataset_id", ""),
                    kwargs.get("query", ""),
                )
            elif action == "create_chart":
                return self._create_chart(
                    kwargs.get("dataset_id", ""),
                    kwargs.get("chart_type", "bar"),
                    kwargs.get("x_column", ""),
                    kwargs.get("y_column", ""),
                    kwargs.get("output_path", ""),
                )
            elif action == "export_report":
                return self._export_report(
                    kwargs.get("dataset_id", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("format", "csv"),
                )
            elif action == "compare_datasets":
                return self._compare_datasets(
                    pd,
                    kwargs.get("file_path", ""),
                    kwargs.get("file_path_2", ""),
                    kwargs.get("dataset_id", ""),
                )
            elif action == "clean_data":
                return self._clean_data(
                    pd,
                    kwargs.get("dataset_id", ""),
                    kwargs.get("operations", []),
                    kwargs.get("output_path", ""),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Data analyzer error: %s", action)
            return f"Data analysis error: {e}"

    def _get_df(self, dataset_id: str) -> Any:
        if not dataset_id:
            # Use most recent dataset if only one
            if len(self._datasets) == 1:
                return next(iter(self._datasets.values()))
            return None
        return self._datasets.get(dataset_id)

    def _load_data(self, pd: Any, file_path: str) -> str:
        if not file_path:
            return "Error: file_path is required for load_data."

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found: {path}"

        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in (".xls", ".xlsx"):
            df = pd.read_excel(path)
        elif suffix == ".json":
            df = pd.read_json(path)
        elif suffix == ".parquet":
            df = pd.read_parquet(path)
        elif suffix in (".tsv", ".txt"):
            df = pd.read_csv(path, sep="\t")
        else:
            return f"Unsupported file format: {suffix}. Supported: csv, json, xlsx, parquet, tsv"

        self._counter += 1
        dataset_id = f"ds_{self._counter}"
        self._datasets[dataset_id] = df

        # Preview
        info_lines = [
            f"Loaded dataset '{dataset_id}' from {path.name}",
            f"  Shape: {df.shape[0]} rows x {df.shape[1]} columns",
            f"  Columns: {', '.join(df.columns[:20])}",
            f"\nFirst 5 rows:",
            df.head().to_string(),
        ]

        return "\n".join(info_lines)

    def _describe_data(self, pd: Any, dataset_id: str) -> str:
        df = self._get_df(dataset_id)
        if df is None:
            return "Error: No dataset found. Load data first with load_data."

        desc = df.describe(include="all")
        dtypes = df.dtypes.to_string()
        nulls = df.isnull().sum()
        null_str = nulls[nulls > 0].to_string() if nulls.any() else "None"

        return (
            f"Dataset shape: {df.shape[0]} rows x {df.shape[1]} columns\n\n"
            f"Column types:\n{dtypes}\n\n"
            f"Missing values:\n{null_str}\n\n"
            f"Statistics:\n{desc.to_string()}"
        )

    def _query_data(self, pd: Any, dataset_id: str, query: str) -> str:
        df = self._get_df(dataset_id)
        if df is None:
            return "Error: No dataset found. Load data first."
        if not query:
            return "Error: query is required for query_data."

        result = df.query(query)

        if result.empty:
            return f"Query '{query}' returned no results."

        output = result.head(50).to_string()
        if len(result) > 50:
            output += f"\n\n... showing 50 of {len(result)} matching rows"

        return f"Query: {query}\nResults ({len(result)} rows):\n\n{output}"

    def _create_chart(self, dataset_id: str, chart_type: str,
                      x_column: str, y_column: str, output_path: str) -> str:
        df = self._get_df(dataset_id)
        if df is None:
            return "Error: No dataset found. Load data first."

        try:
            import matplotlib
            matplotlib.use("Agg")  # Non-interactive backend
            import matplotlib.pyplot as plt
        except ImportError:
            return "Error: matplotlib is not installed. Run: pip install matplotlib"

        fig, ax = plt.subplots(figsize=(10, 6))

        if chart_type == "bar":
            if not x_column or not y_column:
                return "Error: x_column and y_column required for bar chart."
            df.plot.bar(x=x_column, y=y_column, ax=ax)
        elif chart_type == "line":
            if not x_column or not y_column:
                return "Error: x_column and y_column required for line chart."
            df.plot.line(x=x_column, y=y_column, ax=ax)
        elif chart_type == "scatter":
            if not x_column or not y_column:
                return "Error: x_column and y_column required for scatter chart."
            df.plot.scatter(x=x_column, y=y_column, ax=ax)
        elif chart_type == "pie":
            if not y_column:
                return "Error: y_column required for pie chart."
            col = x_column or df.columns[0]
            df.set_index(col)[y_column].plot.pie(ax=ax, autopct="%1.1f%%")
        elif chart_type == "histogram":
            col = x_column or y_column
            if not col:
                return "Error: x_column or y_column required for histogram."
            df[col].plot.hist(ax=ax, bins=20)
            ax.set_xlabel(col)
        elif chart_type == "heatmap":
            try:
                import numpy as np
                numeric = df.select_dtypes(include=[np.number])
                corr = numeric.corr()
                im = ax.imshow(corr, cmap="coolwarm", aspect="auto")
                ax.set_xticks(range(len(corr.columns)))
                ax.set_yticks(range(len(corr.columns)))
                ax.set_xticklabels(corr.columns, rotation=45, ha="right")
                ax.set_yticklabels(corr.columns)
                fig.colorbar(im)
            except Exception as e:
                return f"Heatmap error: {e}"
        else:
            return f"Unknown chart_type: {chart_type}"

        ax.set_title(f"{chart_type.title()} Chart")
        plt.tight_layout()

        if output_path:
            out = Path(output_path).expanduser()
        else:
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            out = STORAGE_DIR / f"chart_{chart_type}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out), dpi=150)
        plt.close(fig)

        size_kb = out.stat().st_size / 1024
        return f"Created {chart_type} chart at {out} ({size_kb:.1f} KB)"

    def _export_report(self, dataset_id: str, output_path: str, fmt: str) -> str:
        df = self._get_df(dataset_id)
        if df is None:
            return "Error: No dataset found. Load data first."
        if not output_path:
            return "Error: output_path is required for export_report."

        out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "csv":
            df.to_csv(out, index=False)
        elif fmt == "json":
            df.to_json(out, orient="records", indent=2)
        elif fmt == "html":
            desc = df.describe(include="all")
            html = (
                f"<html><head><title>Data Report</title>"
                f"<style>table {{border-collapse:collapse;}} "
                f"th,td {{border:1px solid #ddd;padding:8px;text-align:left;}}"
                f"th {{background:#f4f4f4;}}</style></head><body>"
                f"<h1>Data Report</h1>"
                f"<h2>Shape: {df.shape[0]} rows x {df.shape[1]} columns</h2>"
                f"<h3>Statistics</h3>{desc.to_html()}"
                f"<h3>First 20 Rows</h3>{df.head(20).to_html()}"
                f"</body></html>"
            )
            out.write_text(html, encoding="utf-8")
        else:
            return f"Unsupported format: {fmt}. Use csv, json, or html."

        size_kb = out.stat().st_size / 1024
        return f"Exported report to {out} ({fmt}, {size_kb:.1f} KB)"

    def _compare_datasets(self, pd: Any, file_path: str, file_path_2: str,
                          dataset_id: str) -> str:
        """Compare two datasets and report differences."""
        # Load first dataset
        if file_path:
            p1 = Path(file_path).expanduser()
            if not p1.exists():
                return f"Error: File not found: {p1}"
            df1 = self._read_file(pd, p1)
            name1 = p1.name
        elif dataset_id:
            df1 = self._get_df(dataset_id)
            name1 = dataset_id
        else:
            return "Error: file_path or dataset_id required for first dataset."

        if df1 is None:
            return "Error: Could not load first dataset."

        # Load second dataset
        if file_path_2:
            p2 = Path(file_path_2).expanduser()
            if not p2.exists():
                return f"Error: File not found: {p2}"
            df2 = self._read_file(pd, p2)
            name2 = p2.name
        else:
            return "Error: file_path_2 is required for compare_datasets."

        if df2 is None:
            return "Error: Could not load second dataset."

        lines = [f"Comparing: {name1} vs {name2}\n"]

        # Shape comparison
        lines.append(f"Shape: {df1.shape} vs {df2.shape}")

        # Column comparison
        cols1 = set(df1.columns)
        cols2 = set(df2.columns)
        common = cols1 & cols2
        only1 = cols1 - cols2
        only2 = cols2 - cols1

        lines.append(f"Common columns ({len(common)}): {', '.join(sorted(common)[:15])}")
        if only1:
            lines.append(f"Only in {name1} ({len(only1)}): {', '.join(sorted(only1))}")
        if only2:
            lines.append(f"Only in {name2} ({len(only2)}): {', '.join(sorted(only2))}")

        # Value comparison for common columns
        if common and df1.shape[0] == df2.shape[0]:
            lines.append(f"\nValue differences (same row count: {df1.shape[0]}):")
            for col in sorted(common):
                try:
                    diff_mask = df1[col].astype(str) != df2[col].astype(str)
                    diff_count = diff_mask.sum()
                    if diff_count > 0:
                        lines.append(f"  {col}: {diff_count} different values ({diff_count/len(df1)*100:.1f}%)")
                except Exception:
                    pass
        elif common:
            lines.append(f"\nRow counts differ ({df1.shape[0]} vs {df2.shape[0]}), skipping value comparison.")

        # Stats comparison for numeric columns
        import numpy as np
        num1 = df1.select_dtypes(include=[np.number]).columns
        num2 = df2.select_dtypes(include=[np.number]).columns
        num_common = set(num1) & set(num2)
        if num_common:
            lines.append(f"\nNumeric column stats comparison:")
            for col in sorted(num_common)[:10]:
                m1, m2 = df1[col].mean(), df2[col].mean()
                lines.append(f"  {col}: mean {m1:.2f} vs {m2:.2f}")

        return "\n".join(lines)

    def _read_file(self, pd: Any, path: Path) -> Any:
        """Helper to read a file into a DataFrame."""
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path)
        elif suffix in (".xls", ".xlsx"):
            return pd.read_excel(path)
        elif suffix == ".json":
            return pd.read_json(path)
        elif suffix == ".parquet":
            return pd.read_parquet(path)
        elif suffix in (".tsv", ".txt"):
            return pd.read_csv(path, sep="\t")
        return None

    def _clean_data(self, pd: Any, dataset_id: str, operations: list,
                    output_path: str) -> str:
        """Clean dataset by applying operations."""
        df = self._get_df(dataset_id)
        if df is None:
            return "Error: No dataset found. Load data first."
        if not operations:
            return (
                "Error: operations list required. Available:\n"
                "  - drop_duplicates\n"
                "  - drop_nulls\n"
                "  - fill_nulls:VALUE (e.g. fill_nulls:0)\n"
                "  - lowercase:COLUMN\n"
                "  - strip_whitespace\n"
                "  - rename:OLD:NEW"
            )

        original_shape = df.shape
        results = []

        for op in operations:
            op = op.strip()
            if op == "drop_duplicates":
                before = len(df)
                df = df.drop_duplicates()
                removed = before - len(df)
                results.append(f"drop_duplicates: removed {removed} rows")

            elif op == "drop_nulls":
                before = len(df)
                df = df.dropna()
                removed = before - len(df)
                results.append(f"drop_nulls: removed {removed} rows")

            elif op.startswith("fill_nulls:"):
                value = op.split(":", 1)[1]
                # Try numeric conversion
                try:
                    value = float(value)
                    if value == int(value):
                        value = int(value)
                except ValueError:
                    pass
                null_count = df.isnull().sum().sum()
                df = df.fillna(value)
                results.append(f"fill_nulls: filled {null_count} null values with '{value}'")

            elif op.startswith("lowercase:"):
                col = op.split(":", 1)[1]
                if col in df.columns:
                    df[col] = df[col].astype(str).str.lower()
                    results.append(f"lowercase: converted '{col}' to lowercase")
                else:
                    results.append(f"lowercase: column '{col}' not found")

            elif op == "strip_whitespace":
                str_cols = df.select_dtypes(include=["object"]).columns
                for col in str_cols:
                    df[col] = df[col].str.strip()
                results.append(f"strip_whitespace: cleaned {len(str_cols)} text columns")

            elif op.startswith("rename:"):
                parts = op.split(":", 2)
                if len(parts) == 3:
                    old_name, new_name = parts[1], parts[2]
                    if old_name in df.columns:
                        df = df.rename(columns={old_name: new_name})
                        results.append(f"rename: '{old_name}' -> '{new_name}'")
                    else:
                        results.append(f"rename: column '{old_name}' not found")
                else:
                    results.append(f"rename: use format rename:OLD:NEW")
            else:
                results.append(f"unknown operation: {op}")

        # Update stored dataset
        if dataset_id and dataset_id in self._datasets:
            self._datasets[dataset_id] = df
        elif self._datasets:
            key = next(iter(self._datasets))
            self._datasets[key] = df

        # Save if output_path given
        save_msg = ""
        if output_path:
            out = Path(output_path).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.suffix == ".json":
                df.to_json(out, orient="records", indent=2)
            else:
                df.to_csv(out, index=False)
            save_msg = f"\nSaved cleaned data to {out}"

        return (
            f"Cleaned dataset: {original_shape} -> {df.shape}\n"
            + "\n".join(f"  - {r}" for r in results)
            + save_msg
        )
