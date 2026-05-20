#!/usr/bin/env python3
"""
Unified Input Pipeline for the Geng Skill Project
===================================================

A self-contained module that ingests data from PDFs, Excel files, and CSVs,
returning a standardized dictionary suitable for downstream statistical
forensics / anomaly-detection modules.

Supports three primary modes:
  - **extract**: Parse tables and numeric data from the input file.
  - **scale**: Automated "scan" mode — ingests a CSV/Excel, runs ALL detection
    modules, and highlights the most suspicious columns/pairs without user guidance.
  - **info**: Return metadata about the input file without full extraction.

CLI Usage
---------
    python3 input_pipeline.py --input paper.pdf --mode extract
    python3 input_pipeline.py --input data.xlsx --mode scale
    python3 input_pipeline.py --input results.csv --mode info

Author: Geng Skill / BioMaster
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Lazy imports with install hints
# ---------------------------------------------------------------------------

def _import_pdfplumber():
    """Lazily import pdfplumber with install hint on failure."""
    try:
        import pdfplumber
        return pdfplumber
    except ImportError:
        print(
            "[input_pipeline] pdfplumber not found. Install with:\n"
            "  python3 -m pip install pdfplumber",
            file=sys.stderr,
        )
        return None


def _import_fitz():
    """Lazily import PyMuPDF (fitz) with install hint on failure."""
    try:
        import fitz
        return fitz
    except ImportError:
        print(
            "[input_pipeline] PyMuPDF not found. Install with:\n"
            "  python3 -m pip install PyMuPDF",
            file=sys.stderr,
        )
        return None


def _import_tabula():
    """Lazily import tabula-py with install hint on failure."""
    try:
        import tabula
        return tabula
    except ImportError:
        print(
            "[input_pipeline] tabula-py not found. Install with:\n"
            "  python3 -m pip install tabula-py\n"
            "  (also requires Java runtime: apt-get install default-jre)",
            file=sys.stderr,
        )
        return None


def _import_pandas():
    """Lazily import pandas with install hint on failure."""
    try:
        import pandas as pd
        return pd
    except ImportError:
        print(
            "[input_pipeline] pandas not found. Install with:\n"
            "  python3 -m pip install pandas",
            file=sys.stderr,
        )
        sys.exit(1)


def _import_openpyxl():
    """Lazily import openpyxl with install hint on failure."""
    try:
        import openpyxl
        return openpyxl
    except ImportError:
        print(
            "[input_pipeline] openpyxl not found. Install with:\n"
            "  python3 -m pip install openpyxl",
            file=sys.stderr,
        )
        return None


def _import_xlrd():
    """Lazily import xlrd with install hint on failure."""
    try:
        import xlrd
        return xlrd
    except ImportError:
        print(
            "[input_pipeline] xlrd not found. Install with:\n"
            "  python3 -m pip install xlrd",
            file=sys.stderr,
        )
        return None


def _import_numpy():
    """Lazily import numpy with install hint on failure."""
    try:
        import numpy as np
        return np
    except ImportError:
        print(
            "[input_pipeline] numpy not found. Install with:\n"
            "  python3 -m pip install numpy",
            file=sys.stderr,
        )
        sys.exit(1)


def _import_scipy():
    """Lazily import scipy with install hint on failure."""
    try:
        import scipy
        return scipy
    except ImportError:
        print(
            "[input_pipeline] scipy not found. Install with:\n"
            "  python3 -m pip install scipy",
            file=sys.stderr,
        )
        return None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".tsv"}

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def detect_file_type(filepath: str) -> str:
    """
    Detect the logical file type from the file extension.

    Parameters
    ----------
    filepath : str
        Path to the input file.

    Returns
    -------
    str
        One of "pdf", "excel", "csv".

    Raises
    ------
    ValueError
        If the file extension is not supported.
    """
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    elif ext in (".xlsx", ".xls"):
        return "excel"
    elif ext in (".csv", ".tsv"):
        return "csv"
    else:
        raise ValueError(
            f"Unsupported file extension '{ext}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )


def _dataframe_to_serializable(df) -> List[Dict[str, Any]]:
    """
    Convert a pandas DataFrame to a list of row-dicts that is JSON-serializable.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to convert.

    Returns
    -------
    list of dict
        Each dict represents one row with column names as keys.
    """
    pd = _import_pandas()
    # Replace NaN/Inf with None for JSON compatibility
    import numpy as np
    df_clean = df.replace([np.inf, -np.inf], np.nan).where(df.notnull(), None)
    records = df_clean.to_dict(orient="records")
    # Ensure numpy types are converted to native Python types
    clean_records = []
    for row in records:
        clean_row = {}
        for k, v in row.items():
            if hasattr(v, "item"):
                clean_row[k] = v.item()
            else:
                clean_row[k] = v
        clean_records.append(clean_row)
    return clean_records


def _identify_numeric_columns(df) -> Dict[str, Dict[str, Any]]:
    """
    Auto-detect numeric columns and compute summary statistics.

    Parameters
    ----------
    df : pandas.DataFrame
        Input dataframe.

    Returns
    -------
    dict
        Mapping of column name -> {dtype, count, mean, std, min, max, n_missing}.
    """
    np = _import_numpy()
    numeric_info: Dict[str, Dict[str, Any]] = {}
    for col in df.columns:
        # Attempt numeric coercion for mixed-type columns
        series = df[col]
        if not _is_numeric_dtype(series):
            coerced = _try_coerce_numeric(series)
            if coerced is None:
                continue
            series = coerced

        n_missing = int(series.isna().sum())
        valid = series.dropna()
        if len(valid) == 0:
            continue

        numeric_info[str(col)] = {
            "dtype": str(series.dtype),
            "count": int(len(valid)),
            "mean": float(valid.mean()),
            "std": float(valid.std()) if len(valid) > 1 else 0.0,
            "min": float(valid.min()),
            "max": float(valid.max()),
            "n_missing": n_missing,
        }
    return numeric_info


def _is_numeric_dtype(series) -> bool:
    """Check if a pandas Series has a numeric dtype."""
    pd = _import_pandas()
    return pd.api.types.is_numeric_dtype(series)


def _try_coerce_numeric(series):
    """
    Attempt to coerce a series to numeric, returning None if <50% convertible.

    Parameters
    ----------
    series : pandas.Series
        The series to attempt coercion on.

    Returns
    -------
    pandas.Series or None
        Coerced numeric series, or None if not predominantly numeric.
    """
    pd = _import_pandas()
    coerced = pd.to_numeric(series, errors="coerce")
    valid_ratio = coerced.notna().sum() / max(len(series), 1)
    if valid_ratio >= 0.5:
        return coerced
    return None


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------


def extract_from_pdf(
    filepath: str,
    *,
    pages: Optional[List[int]] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract tables and text data from an academic paper PDF.

    Uses pdfplumber as the primary extractor with fallback to PyMuPDF for
    text extraction and tabula-py for table extraction.

    Parameters
    ----------
    filepath : str
        Path to the PDF file.
    pages : list of int, optional
        Specific 0-indexed page numbers to process. If None, all pages are
        processed.
    password : str, optional
        Password for encrypted/protected PDFs.

    Returns
    -------
    dict
        Standardized result dictionary with keys:
        - source_type : "pdf"
        - tables : list of list-of-dicts (each table as records)
        - numeric_columns : dict mapping column names to stats (aggregated)
        - metadata : dict with page_count, extractor_used, warnings, etc.

    Raises
    ------
    FileNotFoundError
        If the PDF file does not exist.
    RuntimeError
        If no PDF extraction library is available.

    Notes
    -----
    The function attempts extraction in the following order:
    1. pdfplumber (best for structured tables in academic papers)
    2. tabula-py (Java-based, good for complex table layouts)
    3. PyMuPDF/fitz (fallback for text-only extraction)

    Examples
    --------
    >>> result = extract_from_pdf("paper.pdf")
    >>> print(result["source_type"])
    'pdf'
    >>> print(len(result["tables"]))
    3
    """
    filepath = str(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"PDF file not found: {filepath}")

    pd = _import_pandas()
    np = _import_numpy()

    tables: List[List[Dict[str, Any]]] = []
    metadata: Dict[str, Any] = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "file_size_bytes": os.path.getsize(filepath),
        "extractor_used": None,
        "page_count": None,
        "warnings": [],
    }
    all_numeric_columns: Dict[str, Dict[str, Any]] = {}

    # --- Attempt 1: pdfplumber ---
    pdfplumber = _import_pdfplumber()
    if pdfplumber is not None:
        try:
            open_kwargs: Dict[str, Any] = {}
            if password:
                open_kwargs["password"] = password

            with pdfplumber.open(filepath, **open_kwargs) as pdf:
                metadata["page_count"] = len(pdf.pages)
                metadata["extractor_used"] = "pdfplumber"

                pages_to_process = pages if pages else range(len(pdf.pages))
                for page_idx in pages_to_process:
                    if page_idx >= len(pdf.pages):
                        metadata["warnings"].append(
                            f"Page {page_idx} out of range (total: {len(pdf.pages)})"
                        )
                        continue
                    page = pdf.pages[page_idx]
                    page_tables = page.extract_tables()
                    if not page_tables:
                        continue
                    for raw_table in page_tables:
                        if not raw_table or len(raw_table) < 2:
                            continue
                        # First row as header
                        header = [
                            str(c).strip() if c else f"col_{i}"
                            for i, c in enumerate(raw_table[0])
                        ]
                        # Deduplicate headers
                        header = _deduplicate_headers(header)
                        rows = raw_table[1:]
                        df = pd.DataFrame(rows, columns=header)
                        # Attempt numeric coercion on all columns
                        for col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="ignore")
                        tables.append(_dataframe_to_serializable(df))
                        col_info = _identify_numeric_columns(df)
                        all_numeric_columns.update(col_info)

            if tables:
                return {
                    "source_type": "pdf",
                    "tables": tables,
                    "numeric_columns": all_numeric_columns,
                    "metadata": metadata,
                }
        except Exception as e:
            metadata["warnings"].append(f"pdfplumber failed: {str(e)}")

    # --- Attempt 2: tabula-py ---
    tabula = _import_tabula()
    if tabula is not None:
        try:
            tabula_pages = "all"
            if pages:
                # tabula uses 1-indexed pages
                tabula_pages = [p + 1 for p in pages]

            kwargs: Dict[str, Any] = {"pages": tabula_pages, "multiple_tables": True}
            if password:
                kwargs["password"] = password

            dfs = tabula.read_pdf(filepath, **kwargs)
            metadata["extractor_used"] = "tabula-py"

            for df in dfs:
                if df.empty:
                    continue
                tables.append(_dataframe_to_serializable(df))
                col_info = _identify_numeric_columns(df)
                all_numeric_columns.update(col_info)

            if tables:
                return {
                    "source_type": "pdf",
                    "tables": tables,
                    "numeric_columns": all_numeric_columns,
                    "metadata": metadata,
                }
        except Exception as e:
            metadata["warnings"].append(f"tabula-py failed: {str(e)}")

    # --- Attempt 3: PyMuPDF (text-only fallback) ---
    fitz = _import_fitz()
    if fitz is not None:
        try:
            doc = fitz.open(filepath)
            if password and doc.is_encrypted:
                if not doc.authenticate(password):
                    metadata["warnings"].append("PyMuPDF: password authentication failed")
                    doc.close()
                    raise RuntimeError("Cannot decrypt PDF with provided password")

            metadata["page_count"] = len(doc)
            metadata["extractor_used"] = "PyMuPDF (text-only)"

            full_text_lines: List[str] = []
            pages_to_process = pages if pages else range(len(doc))
            for page_idx in pages_to_process:
                if page_idx >= len(doc):
                    continue
                page = doc[page_idx]
                text = page.get_text()
                full_text_lines.append(text)

            doc.close()

            # Attempt to parse tab/comma separated data from text
            extracted_df = _parse_text_tables("\n".join(full_text_lines))
            if extracted_df is not None and not extracted_df.empty:
                tables.append(_dataframe_to_serializable(extracted_df))
                all_numeric_columns = _identify_numeric_columns(extracted_df)

            metadata["text_length_chars"] = sum(len(t) for t in full_text_lines)

            return {
                "source_type": "pdf",
                "tables": tables,
                "numeric_columns": all_numeric_columns,
                "metadata": metadata,
            }
        except Exception as e:
            metadata["warnings"].append(f"PyMuPDF failed: {str(e)}")

    # --- All extractors failed ---
    if not any([pdfplumber, tabula, fitz]):
        raise RuntimeError(
            "No PDF extraction library available. Install at least one:\n"
            "  python3 -m pip install pdfplumber\n"
            "  python3 -m pip install tabula-py\n"
            "  python3 -m pip install PyMuPDF"
        )

    return {
        "source_type": "pdf",
        "tables": tables,
        "numeric_columns": all_numeric_columns,
        "metadata": metadata,
    }


def _deduplicate_headers(headers: List[str]) -> List[str]:
    """
    Ensure all column headers are unique by appending suffixes.

    Parameters
    ----------
    headers : list of str
        Raw header names (may contain duplicates).

    Returns
    -------
    list of str
        Deduplicated header names.
    """
    seen: Dict[str, int] = {}
    result: List[str] = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            result.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            result.append(h)
    return result


def _parse_text_tables(text: str):
    """
    Heuristically parse tabular data from raw text (TSV or CSV-like).

    Parameters
    ----------
    text : str
        Raw text extracted from a PDF page.

    Returns
    -------
    pandas.DataFrame or None
        Parsed dataframe if a table-like structure is detected, else None.
    """
    pd = _import_pandas()
    import io

    lines = [l for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return None

    # Detect delimiter (tab > comma > multiple-spaces)
    for delimiter in ["\t", ",", "  "]:
        counts = [l.count(delimiter) for l in lines[:10]]
        if all(c > 0 for c in counts) and max(counts) - min(counts) <= 2:
            try:
                df = pd.read_csv(
                    io.StringIO("\n".join(lines)),
                    sep=delimiter if delimiter != "  " else r"\s{2,}",
                    engine="python" if delimiter == "  " else "c",
                )
                if df.shape[1] >= 2 and df.shape[0] >= 2:
                    return df
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# Excel extraction
# ---------------------------------------------------------------------------


def extract_from_excel(
    filepath: str,
    *,
    sheet_names: Optional[List[str]] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read tables from .xlsx/.xls files with auto-detection of numeric columns.

    Parameters
    ----------
    filepath : str
        Path to the Excel file.
    sheet_names : list of str, optional
        Specific sheet names to read. If None, all sheets are read.
    password : str, optional
        Password for protected workbooks (openpyxl only, limited support).

    Returns
    -------
    dict
        Standardized result dictionary with keys:
        - source_type : "excel"
        - tables : list of list-of-dicts (one per non-empty sheet)
        - numeric_columns : dict mapping column names to stats (aggregated)
        - metadata : dict with sheet_names_found, engine_used, warnings, etc.

    Raises
    ------
    FileNotFoundError
        If the Excel file does not exist.
    RuntimeError
        If no Excel reading library is available.

    Notes
    -----
    Uses openpyxl for .xlsx and xlrd for .xls files. Falls back between
    engines as needed.

    Examples
    --------
    >>> result = extract_from_excel("data.xlsx")
    >>> print(result["source_type"])
    'excel'
    >>> print(list(result["numeric_columns"].keys()))
    ['age', 'score', 'p_value']
    """
    filepath = str(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Excel file not found: {filepath}")

    pd = _import_pandas()
    np = _import_numpy()

    ext = Path(filepath).suffix.lower()
    tables: List[List[Dict[str, Any]]] = []
    all_numeric_columns: Dict[str, Dict[str, Any]] = {}
    metadata: Dict[str, Any] = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "file_size_bytes": os.path.getsize(filepath),
        "engine_used": None,
        "sheet_names_found": [],
        "sheets_processed": [],
        "warnings": [],
    }

    # Determine engine
    engine = None
    if ext == ".xlsx":
        openpyxl = _import_openpyxl()
        if openpyxl is not None:
            engine = "openpyxl"
        else:
            metadata["warnings"].append("openpyxl not available for .xlsx")
    elif ext == ".xls":
        xlrd = _import_xlrd()
        if xlrd is not None:
            engine = "xlrd"
        else:
            metadata["warnings"].append("xlrd not available for .xls")

    if engine is None:
        # Try pandas default
        try:
            _ = pd.ExcelFile(filepath)
            engine = "auto"
        except Exception as e:
            raise RuntimeError(
                f"No suitable Excel engine available for '{ext}'. "
                "Install with:\n"
                "  python3 -m pip install openpyxl  # for .xlsx\n"
                "  python3 -m pip install xlrd      # for .xls"
            ) from e

    metadata["engine_used"] = engine

    # Read Excel file
    try:
        read_kwargs: Dict[str, Any] = {"sheet_name": None}  # Read all sheets
        if engine != "auto":
            read_kwargs["engine"] = engine

        # Handle password-protected xlsx (limited support)
        if password and ext == ".xlsx":
            try:
                import msoffcrypto
                import io

                decrypted = io.BytesIO()
                with open(filepath, "rb") as f:
                    office_file = msoffcrypto.OfficeFile(f)
                    office_file.load_key(password=password)
                    office_file.decrypt(decrypted)
                decrypted.seek(0)
                sheets_dict = pd.read_excel(decrypted, **read_kwargs)
            except ImportError:
                metadata["warnings"].append(
                    "msoffcrypto not available for password-protected files. "
                    "Install with: python3 -m pip install msoffcrypto-tool"
                )
                # Try without password
                sheets_dict = pd.read_excel(filepath, **read_kwargs)
            except Exception as e:
                metadata["warnings"].append(f"Password decryption failed: {e}")
                sheets_dict = pd.read_excel(filepath, **read_kwargs)
        else:
            sheets_dict = pd.read_excel(filepath, **read_kwargs)

    except Exception as e:
        metadata["warnings"].append(f"Excel read failed: {str(e)}")
        return {
            "source_type": "excel",
            "tables": tables,
            "numeric_columns": all_numeric_columns,
            "metadata": metadata,
        }

    metadata["sheet_names_found"] = list(sheets_dict.keys())

    # Filter to requested sheets
    sheets_to_process = sheet_names if sheet_names else list(sheets_dict.keys())

    for sheet_name in sheets_to_process:
        if sheet_name not in sheets_dict:
            metadata["warnings"].append(f"Sheet '{sheet_name}' not found")
            continue

        df = sheets_dict[sheet_name]
        if df.empty:
            metadata["warnings"].append(f"Sheet '{sheet_name}' is empty")
            continue

        # Drop fully-empty rows and columns
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue

        metadata["sheets_processed"].append(str(sheet_name))
        tables.append(_dataframe_to_serializable(df))

        col_info = _identify_numeric_columns(df)
        # Prefix with sheet name if multiple sheets
        if len(sheets_to_process) > 1:
            col_info = {f"{sheet_name}::{k}": v for k, v in col_info.items()}
        all_numeric_columns.update(col_info)

    return {
        "source_type": "excel",
        "tables": tables,
        "numeric_columns": all_numeric_columns,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# CSV extraction
# ---------------------------------------------------------------------------


def extract_from_csv(filepath: str) -> Dict[str, Any]:
    """
    Read a CSV/TSV file and identify numeric columns.

    Parameters
    ----------
    filepath : str
        Path to the CSV or TSV file.

    Returns
    -------
    dict
        Standardized result dictionary with keys:
        - source_type : "csv"
        - tables : list containing one list-of-dicts
        - numeric_columns : dict mapping column names to stats
        - metadata : dict with delimiter_detected, row_count, col_count, etc.

    Raises
    ------
    FileNotFoundError
        If the CSV file does not exist.

    Examples
    --------
    >>> result = extract_from_csv("results.csv")
    >>> print(result["metadata"]["row_count"])
    150
    """
    filepath = str(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    pd = _import_pandas()

    metadata: Dict[str, Any] = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "file_size_bytes": os.path.getsize(filepath),
        "delimiter_detected": None,
        "row_count": 0,
        "col_count": 0,
        "warnings": [],
    }

    ext = Path(filepath).suffix.lower()
    sep = "\t" if ext == ".tsv" else ","

    # Auto-detect delimiter from first few lines
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            sample = f.read(4096)
        if sep == "," and sample.count("\t") > sample.count(","):
            sep = "\t"
        elif sep == "," and sample.count(";") > sample.count(","):
            sep = ";"
    except Exception:
        pass

    metadata["delimiter_detected"] = repr(sep)

    try:
        df = pd.read_csv(filepath, sep=sep, engine="python", on_bad_lines="skip")
    except Exception as e:
        metadata["warnings"].append(f"CSV read failed: {str(e)}")
        return {
            "source_type": "csv",
            "tables": [],
            "numeric_columns": {},
            "metadata": metadata,
        }

    # Drop fully-empty rows/cols
    df = df.dropna(how="all").dropna(axis=1, how="all")

    metadata["row_count"] = len(df)
    metadata["col_count"] = len(df.columns)

    tables = [_dataframe_to_serializable(df)] if not df.empty else []
    numeric_columns = _identify_numeric_columns(df)

    return {
        "source_type": "csv",
        "tables": tables,
        "numeric_columns": numeric_columns,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Scale mode — automated multi-module anomaly scan
# ---------------------------------------------------------------------------


def run_scale_mode(filepath: str) -> Dict[str, Any]:
    """
    Automated "scale" scan: ingest a CSV/Excel, run ALL detection modules,
    and highlight the most suspicious columns/pairs without user guidance.

    Detection modules applied:
      1. **Digit frequency (Benford's Law)** — first-digit distribution test
      2. **Terminal digit bias** — last-digit uniformity test
      3. **GRIM test** — granularity-consistent mean test for integer-sourced means
      4. **Duplicate pattern detection** — unusual repetition in numeric values
      5. **Correlation anomalies** — suspiciously perfect or impossible correlations
      6. **Distribution shape** — normality tests and outlier fraction

    Parameters
    ----------
    filepath : str
        Path to a CSV or Excel file.

    Returns
    -------
    dict
        Standardized result with additional key:
        - scale_results : dict mapping module_name -> {
              flagged_columns: list,
              flagged_pairs: list,
              scores: dict,
              details: str
          }
        - suspicion_ranking : list of (column_or_pair, aggregate_score) sorted desc

    Notes
    -----
    The scale mode is designed to be run without any prior knowledge of the
    data. It is a screening tool; flagged columns should be investigated
    further before drawing conclusions.

    Examples
    --------
    >>> result = run_scale_mode("experiment_data.csv")
    >>> for item in result["suspicion_ranking"][:5]:
    ...     print(item)
    ('treatment_mean', 0.87)
    ('control_mean', 0.72)
    """
    # First, extract the data
    file_type = detect_file_type(filepath)
    if file_type == "csv":
        extraction = extract_from_csv(filepath)
    elif file_type == "excel":
        extraction = extract_from_excel(filepath)
    elif file_type == "pdf":
        extraction = extract_from_pdf(filepath)
    else:
        raise ValueError(f"Scale mode does not support file type: {file_type}")

    pd = _import_pandas()
    np = _import_numpy()

    # Reconstruct dataframes from extracted tables
    all_dfs: List = []
    for table_records in extraction.get("tables", []):
        if table_records:
            df = pd.DataFrame(table_records)
            all_dfs.append(df)

    if not all_dfs:
        extraction["scale_results"] = {}
        extraction["suspicion_ranking"] = []
        extraction["metadata"]["warnings"] = extraction.get("metadata", {}).get(
            "warnings", []
        ) + ["No tables found for scale analysis"]
        return extraction

    # Merge all tables for comprehensive analysis
    # (if multiple tables, concatenate columns with unique naming)
    combined_df = all_dfs[0]
    for i, df in enumerate(all_dfs[1:], start=1):
        df_renamed = df.add_prefix(f"table{i}_")
        combined_df = pd.concat([combined_df, df_renamed], axis=1)

    # Run detection modules
    scale_results: Dict[str, Dict[str, Any]] = {}
    suspicion_scores: Dict[str, float] = {}

    # Module 1: Benford's Law (first-digit distribution)
    benford_result = _module_benford(combined_df)
    scale_results["benford_first_digit"] = benford_result
    for col, score in benford_result.get("scores", {}).items():
        suspicion_scores[col] = suspicion_scores.get(col, 0.0) + score

    # Module 2: Terminal digit bias
    terminal_result = _module_terminal_digits(combined_df)
    scale_results["terminal_digit_bias"] = terminal_result
    for col, score in terminal_result.get("scores", {}).items():
        suspicion_scores[col] = suspicion_scores.get(col, 0.0) + score

    # Module 3: GRIM test
    grim_result = _module_grim(combined_df)
    scale_results["grim_test"] = grim_result
    for col, score in grim_result.get("scores", {}).items():
        suspicion_scores[col] = suspicion_scores.get(col, 0.0) + score

    # Module 4: Duplicate pattern detection
    dup_result = _module_duplicate_patterns(combined_df)
    scale_results["duplicate_patterns"] = dup_result
    for col, score in dup_result.get("scores", {}).items():
        suspicion_scores[col] = suspicion_scores.get(col, 0.0) + score

    # Module 5: Correlation anomalies
    corr_result = _module_correlation_anomalies(combined_df)
    scale_results["correlation_anomalies"] = corr_result
    for pair, score in corr_result.get("scores", {}).items():
        suspicion_scores[pair] = suspicion_scores.get(pair, 0.0) + score

    # Module 6: Distribution shape
    dist_result = _module_distribution_shape(combined_df)
    scale_results["distribution_shape"] = dist_result
    for col, score in dist_result.get("scores", {}).items():
        suspicion_scores[col] = suspicion_scores.get(col, 0.0) + score

    # Normalize and rank
    max_score = max(suspicion_scores.values()) if suspicion_scores else 1.0
    if max_score > 0:
        normalized = {k: round(v / max_score, 3) for k, v in suspicion_scores.items()}
    else:
        normalized = suspicion_scores

    ranking = sorted(normalized.items(), key=lambda x: x[1], reverse=True)

    extraction["scale_results"] = scale_results
    extraction["suspicion_ranking"] = ranking
    return extraction


# ---------------------------------------------------------------------------
# Detection modules for scale mode
# ---------------------------------------------------------------------------


def _module_benford(df) -> Dict[str, Any]:
    """
    Test first-digit distribution against Benford's Law.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to analyze.

    Returns
    -------
    dict
        Module result with flagged_columns, scores, and details.
    """
    np = _import_numpy()
    scipy = _import_scipy()

    benford_expected = np.array([
        np.log10(1 + 1.0 / d) for d in range(1, 10)
    ])

    scores: Dict[str, float] = {}
    flagged: List[str] = []
    details_parts: List[str] = []

    for col in df.select_dtypes(include=["number"]).columns:
        series = df[col].dropna()
        if len(series) < 30:
            continue

        # Extract first significant digit
        abs_vals = series[series != 0].abs()
        if len(abs_vals) < 30:
            continue

        first_digits = abs_vals.apply(
            lambda x: int(str(f"{x:.10e}")[0]) if x > 0 else 0
        )
        first_digits = first_digits[first_digits.between(1, 9)]

        if len(first_digits) < 20:
            continue

        # Compute observed distribution
        observed = np.zeros(9)
        for d in range(1, 10):
            observed[d - 1] = (first_digits == d).sum()

        total = observed.sum()
        if total == 0:
            continue
        observed_freq = observed / total

        # Chi-squared test
        if scipy is not None:
            from scipy.stats import chisquare
            expected_counts = benford_expected * total
            # Avoid zero expected counts
            mask = expected_counts > 0
            if mask.sum() >= 5:
                stat, p_value = chisquare(observed[mask], expected_counts[mask])
                # Score: higher means more suspicious (low p-value)
                score = max(0.0, 1.0 - p_value)
                scores[str(col)] = round(score, 4)
                if p_value < 0.01:
                    flagged.append(str(col))
                    details_parts.append(
                        f"  {col}: chi2={stat:.2f}, p={p_value:.4e} (FLAGGED)"
                    )
        else:
            # Fallback: MAD from Benford
            mad = np.mean(np.abs(observed_freq - benford_expected))
            score = min(1.0, mad * 10)  # Scale heuristically
            scores[str(col)] = round(score, 4)
            if mad > 0.05:
                flagged.append(str(col))

    return {
        "flagged_columns": flagged,
        "flagged_pairs": [],
        "scores": scores,
        "details": (
            "Benford's Law first-digit test.\n" + "\n".join(details_parts)
            if details_parts
            else "Benford's Law first-digit test. No significant deviations."
        ),
    }


def _module_terminal_digits(df) -> Dict[str, Any]:
    """
    Test for non-uniform terminal (last) digit distribution.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to analyze.

    Returns
    -------
    dict
        Module result with flagged_columns, scores, and details.
    """
    np = _import_numpy()
    scipy = _import_scipy()

    scores: Dict[str, float] = {}
    flagged: List[str] = []
    details_parts: List[str] = []

    for col in df.select_dtypes(include=["number"]).columns:
        series = df[col].dropna()
        if len(series) < 20:
            continue

        # Get terminal digits (last digit before decimal or last significant)
        terminal_digits = []
        for val in series:
            s = str(val).rstrip("0").rstrip(".")
            if s and s[-1].isdigit():
                terminal_digits.append(int(s[-1]))

        if len(terminal_digits) < 20:
            continue

        td_array = np.array(terminal_digits)
        # Expected: uniform distribution over 0-9
        observed = np.array([(td_array == d).sum() for d in range(10)])
        total = observed.sum()
        expected = np.full(10, total / 10.0)

        if scipy is not None:
            from scipy.stats import chisquare
            stat, p_value = chisquare(observed, expected)
            score = max(0.0, 1.0 - p_value)
            scores[str(col)] = round(score, 4)
            if p_value < 0.01:
                flagged.append(str(col))
                details_parts.append(
                    f"  {col}: chi2={stat:.2f}, p={p_value:.4e} (non-uniform terminals)"
                )
        else:
            max_dev = np.max(np.abs(observed / total - 0.1))
            score = min(1.0, max_dev * 10)
            scores[str(col)] = round(score, 4)
            if max_dev > 0.1:
                flagged.append(str(col))

    return {
        "flagged_columns": flagged,
        "flagged_pairs": [],
        "scores": scores,
        "details": (
            "Terminal digit uniformity test.\n" + "\n".join(details_parts)
            if details_parts
            else "Terminal digit uniformity test. No significant bias detected."
        ),
    }


def _module_grim(df) -> Dict[str, Any]:
    """
    GRIM (Granularity-Related Inconsistency of Means) test.

    For columns that appear to be sample means derived from integer data,
    checks whether the reported mean is mathematically consistent with
    the implied sample size.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to analyze.

    Returns
    -------
    dict
        Module result with flagged_columns, scores, and details.
    """
    np = _import_numpy()

    scores: Dict[str, float] = {}
    flagged: List[str] = []
    details_parts: List[str] = []

    # GRIM applies to means of integer-scale items
    # Heuristic: columns with values like X.XX where denominator might be N
    for col in df.select_dtypes(include=["number"]).columns:
        series = df[col].dropna()
        if len(series) < 5:
            continue

        # Check if values look like means (between 1-7, typical Likert range)
        if series.min() < 0 or series.max() > 100:
            continue

        # Count GRIM-inconsistent values assuming various sample sizes
        inconsistent_count = 0
        total_tested = 0
        for val in series:
            # Determine decimal places
            val_str = f"{val:.10f}".rstrip("0")
            if "." in val_str:
                decimals = len(val_str.split(".")[1])
            else:
                decimals = 0

            if decimals < 1 or decimals > 4:
                continue

            # Test against common sample sizes (10-200)
            is_consistent = False
            for n in range(5, 201):
                # For a mean of integers with sample size n,
                # the mean must be a multiple of 1/n
                granularity = 1.0 / n
                remainder = abs(val % granularity)
                if remainder < 1e-8 or abs(remainder - granularity) < 1e-8:
                    is_consistent = True
                    break

            total_tested += 1
            if not is_consistent:
                inconsistent_count += 1

        if total_tested >= 5:
            inconsistency_rate = inconsistent_count / total_tested
            score = min(1.0, inconsistency_rate * 2)  # Scale up
            scores[str(col)] = round(score, 4)
            if inconsistency_rate > 0.5:
                flagged.append(str(col))
                details_parts.append(
                    f"  {col}: {inconsistent_count}/{total_tested} "
                    f"GRIM-inconsistent ({inconsistency_rate:.0%})"
                )

    return {
        "flagged_columns": flagged,
        "flagged_pairs": [],
        "scores": scores,
        "details": (
            "GRIM test for mean consistency.\n" + "\n".join(details_parts)
            if details_parts
            else "GRIM test. No inconsistencies detected."
        ),
    }


def _module_duplicate_patterns(df) -> Dict[str, Any]:
    """
    Detect unusual repetition/duplication patterns in numeric columns.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to analyze.

    Returns
    -------
    dict
        Module result with flagged_columns, scores, and details.
    """
    np = _import_numpy()

    scores: Dict[str, float] = {}
    flagged: List[str] = []
    details_parts: List[str] = []

    for col in df.select_dtypes(include=["number"]).columns:
        series = df[col].dropna()
        if len(series) < 10:
            continue

        n = len(series)
        n_unique = series.nunique()
        dup_ratio = 1.0 - (n_unique / n)

        # Also check for suspicious patterns (e.g., many values at round numbers)
        round_count = sum(1 for v in series if v == round(v, 0))
        round_ratio = round_count / n

        # Consecutive duplicate runs
        values = series.values
        max_run = 1
        current_run = 1
        for i in range(1, len(values)):
            if values[i] == values[i - 1]:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1

        # Score based on multiple signals
        score = 0.0
        # High duplication
        if dup_ratio > 0.5 and n_unique > 1:
            score += dup_ratio * 0.5
        # Long consecutive runs (suspicious for continuous data)
        expected_max_run = np.log2(n) if n > 1 else 1
        if max_run > expected_max_run * 2:
            score += 0.3
        # Too many round numbers in presumably continuous data
        if round_ratio > 0.8 and series.std() > 0.1:
            score += 0.2

        score = min(1.0, score)
        if score > 0.1:
            scores[str(col)] = round(score, 4)
        if score > 0.5:
            flagged.append(str(col))
            details_parts.append(
                f"  {col}: dup_ratio={dup_ratio:.2f}, max_run={max_run}, "
                f"round_ratio={round_ratio:.2f}"
            )

    return {
        "flagged_columns": flagged,
        "flagged_pairs": [],
        "scores": scores,
        "details": (
            "Duplicate/repetition pattern analysis.\n" + "\n".join(details_parts)
            if details_parts
            else "Duplicate pattern analysis. No unusual patterns."
        ),
    }


def _module_correlation_anomalies(df) -> Dict[str, Any]:
    """
    Detect suspiciously perfect or theoretically impossible correlations.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to analyze.

    Returns
    -------
    dict
        Module result with flagged_pairs, scores, and details.
    """
    np = _import_numpy()

    scores: Dict[str, float] = {}
    flagged_pairs: List[str] = []
    details_parts: List[str] = []

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(numeric_cols) < 2 or len(numeric_cols) > 100:
        # Too few or too many columns
        return {
            "flagged_columns": [],
            "flagged_pairs": flagged_pairs,
            "scores": scores,
            "details": "Correlation analysis: insufficient or too many columns.",
        }

    # Compute correlation matrix
    corr_matrix = df[numeric_cols].corr()

    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            col_a = numeric_cols[i]
            col_b = numeric_cols[j]
            r = corr_matrix.iloc[i, j]

            if np.isnan(r):
                continue

            pair_name = f"{col_a} <-> {col_b}"
            abs_r = abs(r)

            # Flag suspiciously perfect correlations (|r| > 0.999)
            if abs_r > 0.999:
                score = 1.0
                scores[pair_name] = score
                flagged_pairs.append(pair_name)
                details_parts.append(
                    f"  {pair_name}: r={r:.6f} (suspiciously perfect)"
                )
            elif abs_r > 0.99:
                score = 0.5
                scores[pair_name] = score
                flagged_pairs.append(pair_name)
                details_parts.append(
                    f"  {pair_name}: r={r:.4f} (very high correlation)"
                )

    return {
        "flagged_columns": [],
        "flagged_pairs": flagged_pairs,
        "scores": scores,
        "details": (
            "Correlation anomaly detection.\n" + "\n".join(details_parts)
            if details_parts
            else "Correlation analysis. No anomalous pairs detected."
        ),
    }


def _module_distribution_shape(df) -> Dict[str, Any]:
    """
    Test distribution normality and detect unusual outlier fractions.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to analyze.

    Returns
    -------
    dict
        Module result with flagged_columns, scores, and details.
    """
    np = _import_numpy()
    scipy = _import_scipy()

    scores: Dict[str, float] = {}
    flagged: List[str] = []
    details_parts: List[str] = []

    for col in df.select_dtypes(include=["number"]).columns:
        series = df[col].dropna()
        if len(series) < 20:
            continue

        values = series.values
        mean = np.mean(values)
        std = np.std(values, ddof=1)

        if std == 0:
            continue

        # Outlier fraction (beyond 3 sigma)
        z_scores = np.abs((values - mean) / std)
        outlier_frac = np.mean(z_scores > 3)

        # Expected ~0.3% for normal distribution
        # Suspiciously low outlier rate might indicate trimming
        score = 0.0

        if scipy is not None:
            from scipy.stats import shapiro, kurtosis, skew

            # Shapiro-Wilk test (on subsample if too large)
            test_sample = values[:5000] if len(values) > 5000 else values
            if len(test_sample) >= 8:
                try:
                    stat, p_value = shapiro(test_sample)
                    # Very low p-value isn't inherently suspicious
                    # but combined with other signals matters
                    if p_value > 0.99:
                        # TOO normal — might be fabricated
                        score += 0.3
                        details_parts.append(
                            f"  {col}: Shapiro p={p_value:.4f} "
                            "(suspiciously normal)"
                        )
                except Exception:
                    pass

            # Kurtosis check
            try:
                kurt = float(kurtosis(values))
                if abs(kurt) > 10:
                    score += 0.2
            except Exception:
                pass

        # Outlier fraction anomaly
        if len(values) > 50:
            if outlier_frac == 0 and len(values) > 200:
                # Zero outliers in large sample — suspicious
                score += 0.2
            elif outlier_frac > 0.05:
                # Too many outliers
                score += 0.2

        score = min(1.0, score)
        if score > 0.1:
            scores[str(col)] = round(score, 4)
        if score > 0.4:
            flagged.append(str(col))

    return {
        "flagged_columns": flagged,
        "flagged_pairs": [],
        "scores": scores,
        "details": (
            "Distribution shape and outlier analysis.\n" + "\n".join(details_parts)
            if details_parts
            else "Distribution analysis. No anomalies detected."
        ),
    }


# ---------------------------------------------------------------------------
# Unified pipeline entry point
# ---------------------------------------------------------------------------


def run_pipeline(
    filepath: str,
    *,
    mode: str = "extract",
    pages: Optional[List[int]] = None,
    sheet_names: Optional[List[str]] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified entry point for the input pipeline.

    Determines the file type, applies the appropriate extraction method,
    and optionally runs the full-scale anomaly detection suite.

    Parameters
    ----------
    filepath : str
        Path to the input file (PDF, Excel, or CSV).
    mode : str, default "extract"
        Processing mode:
        - "extract" : Parse and return tables with numeric column detection.
        - "scale" : Full automated anomaly scan (CSV/Excel only).
        - "info" : Return metadata only (lightweight).
    pages : list of int, optional
        For PDFs: specific 0-indexed page numbers to process.
    sheet_names : list of str, optional
        For Excel: specific sheet names to read.
    password : str, optional
        Password for encrypted files.

    Returns
    -------
    dict
        Standardized result dictionary:
        - source_type : "pdf" | "excel" | "csv"
        - tables : list of list-of-dicts (each table as records)
        - numeric_columns : dict mapping column names -> summary stats
        - metadata : dict with file info, warnings, processing details
        - scale_results : (only in "scale" mode) per-module detection results
        - suspicion_ranking : (only in "scale" mode) ranked suspicious items

    Raises
    ------
    FileNotFoundError
        If the input file does not exist.
    ValueError
        If the file type is unsupported or mode is invalid.

    Examples
    --------
    >>> result = run_pipeline("paper.pdf", mode="extract")
    >>> print(result["source_type"])
    'pdf'

    >>> result = run_pipeline("data.csv", mode="scale")
    >>> print(result["suspicion_ranking"][:3])
    [('col_a', 0.95), ('col_b', 0.82), ('col_c <-> col_d', 0.71)]
    """
    # Validate inputs
    filepath = str(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Input file not found: {filepath}")

    valid_modes = ("extract", "scale", "info")
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")

    file_type = detect_file_type(filepath)

    # Info mode: lightweight metadata only
    if mode == "info":
        metadata = {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "file_size_bytes": os.path.getsize(filepath),
            "detected_type": file_type,
        }
        return {
            "source_type": file_type,
            "tables": [],
            "numeric_columns": {},
            "metadata": metadata,
        }

    # Scale mode
    if mode == "scale":
        return run_scale_mode(filepath)

    # Extract mode
    if file_type == "pdf":
        return extract_from_pdf(filepath, pages=pages, password=password)
    elif file_type == "excel":
        return extract_from_excel(
            filepath, sheet_names=sheet_names, password=password
        )
    elif file_type == "csv":
        return extract_from_csv(filepath)
    else:
        raise ValueError(f"Unhandled file type: {file_type}")


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for CLI usage.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="input_pipeline",
        description=(
            "Unified Input Pipeline for the Geng Skill Project.\n"
            "Extracts tables and numeric data from PDFs, Excel files, and CSVs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 input_pipeline.py --input paper.pdf --mode extract\n"
            "  python3 input_pipeline.py --input data.xlsx --mode scale\n"
            "  python3 input_pipeline.py --input results.csv --mode info\n"
            "  python3 input_pipeline.py --input paper.pdf --pages 0 1 2\n"
            "  python3 input_pipeline.py --input data.xlsx --sheets Sheet1 Sheet2\n"
        ),
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input file (PDF, Excel, or CSV).",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["extract", "scale", "info"],
        default="extract",
        help="Processing mode (default: extract).",
    )
    parser.add_argument(
        "--pages",
        nargs="*",
        type=int,
        default=None,
        help="For PDFs: 0-indexed page numbers to process (default: all).",
    )
    parser.add_argument(
        "--sheets",
        nargs="*",
        default=None,
        help="For Excel: sheet names to read (default: all).",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password for encrypted/protected files.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path (default: stdout).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser


def main():
    """
    CLI entry point.

    Parses command-line arguments, runs the pipeline, and outputs
    results as JSON to stdout or a specified file.
    """
    parser = _build_parser()
    args = parser.parse_args()

    try:
        result = run_pipeline(
            args.input,
            mode=args.mode,
            pages=args.pages,
            sheet_names=args.sheets,
            password=args.password,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)

    # Serialize output
    indent = 2 if args.pretty else None
    json_output = json.dumps(result, indent=indent, ensure_ascii=False, default=str)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output, encoding="utf-8")
        print(f"Results written to: {args.output}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == "__main__":
    main()
