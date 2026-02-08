"""Data analyzer tool — load, explore, query, and visualize datasets.

Uses pandas for data manipulation and matplotlib for charts.
Supports CSV, JSON, Excel files.
"""

import logging
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.data_helpers import compare_datasets, clean_data, export_report, read_file

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
                return export_report(
                    kwargs.get("dataset_id", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("format", "csv"),
                    self._get_df,
                )
            elif action == "compare_datasets":
                return compare_datasets(
                    pd,
                    kwargs.get("file_path", ""),
                    kwargs.get("file_path_2", ""),
                    kwargs.get("dataset_id", ""),
                    self._get_df,
                )
            elif action == "clean_data":
                return clean_data(
                    pd,
                    kwargs.get("dataset_id", ""),
                    kwargs.get("operations", []),
                    kwargs.get("output_path", ""),
                    self._get_df,
                    self._datasets,
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

        df = read_file(pd, path)
        if df is None:
            suffix = path.suffix.lower()
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

