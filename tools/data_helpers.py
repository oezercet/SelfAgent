"""Helper functions for the data analyzer tool.

Contains data cleaning, file reading, dataset comparison, and report export logic.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_file(pd: Any, path: Path) -> Any:
    """Read a file into a pandas DataFrame based on its extension.

    Args:
        pd: The pandas module.
        path: Path to the data file.

    Returns:
        A DataFrame, or None if the format is unsupported.
    """
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


def compare_datasets(
    pd: Any,
    file_path: str,
    file_path_2: str,
    dataset_id: str,
    get_df_fn: Any,
) -> str:
    """Compare two datasets and report differences.

    Args:
        pd: The pandas module.
        file_path: Path to the first data file (optional if dataset_id given).
        file_path_2: Path to the second data file.
        dataset_id: Identifier for a previously loaded dataset (first dataset).
        get_df_fn: Callable to retrieve a stored DataFrame by dataset_id.

    Returns:
        A string describing the comparison results.
    """
    # Load first dataset
    if file_path:
        p1 = Path(file_path).expanduser()
        if not p1.exists():
            return f"Error: File not found: {p1}"
        df1 = read_file(pd, p1)
        name1 = p1.name
    elif dataset_id:
        df1 = get_df_fn(dataset_id)
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
        df2 = read_file(pd, p2)
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


def clean_data(
    pd: Any,
    dataset_id: str,
    operations: list,
    output_path: str,
    get_df_fn: Any,
    datasets: dict[str, Any],
) -> str:
    """Clean dataset by applying operations.

    Args:
        pd: The pandas module.
        dataset_id: Identifier for the dataset to clean.
        operations: List of cleaning operation strings.
        output_path: Optional path to save the cleaned data.
        get_df_fn: Callable to retrieve a stored DataFrame by dataset_id.
        datasets: The mutable datasets dict (will be updated in-place).

    Returns:
        A string describing the cleaning results.
    """
    df = get_df_fn(dataset_id)
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
    if dataset_id and dataset_id in datasets:
        datasets[dataset_id] = df
    elif datasets:
        key = next(iter(datasets))
        datasets[key] = df

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


def export_report(
    dataset_id: str,
    output_path: str,
    fmt: str,
    get_df_fn: Any,
) -> str:
    """Export a dataset as a report in CSV, JSON, or HTML format.

    Args:
        dataset_id: Identifier for the dataset to export.
        output_path: File path for the exported report.
        fmt: Export format ('csv', 'json', or 'html').
        get_df_fn: Callable to retrieve a stored DataFrame by dataset_id.

    Returns:
        A string describing the export result.
    """
    df = get_df_fn(dataset_id)
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
