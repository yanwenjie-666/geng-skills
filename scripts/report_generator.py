#!/usr/bin/env python3
"""
report_generator.py — Comprehensive HTML + Markdown Report Generator
for the Geng Skill Academic Fraud Detection Project.

Generates professional, self-contained analysis reports from assessment JSON
produced by the detection pipeline. Supports two output formats:
  - HTML (self-contained with embedded CSS/figures, printable)
  - Markdown (for GitHub/documentation, figures as relative paths)

Usage:
    python3 report_generator.py --input assessment.json --figures figures/ --output report/

The input assessment.json is expected to have this structure:
{
  "metadata": { "source_file", "timestamp", "tool_version", "columns", "rows", ... },
  "overall_risk": { "score": 0-100, "level": "LOW|MEDIUM|HIGH|CRITICAL" },
  "data_overview": { "columns": [...], "preview": [...], "statistics": {...} },
  "modules": [
    {
      "name": "...",
      "description": "...",
      "method": "...",
      "results": { ... },
      "figures": ["fig1.png", ...],
      "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
      "p_value": ...,
      "test_statistic": ...,
      "evidence_summary": "..."
    }, ...
  ],
  "suspicious_points": [
    { "row": ..., "column": "...", "value": ..., "reason": "...", "module": "..." }, ...
  ],
  "confidence": { "overall": ..., "intervals": {...}, "limitations": [...] },
  "recommendations": [ { "priority": 1, "action": "...", "rationale": "..." }, ... ]
}

Author: BioMaster / Geng Skill Project
License: MIT
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOL_VERSION = "1.0.0"
TOOL_NAME = "Geng Skill Academic Data Integrity Analyzer"

RISK_COLORS = {
    "LOW": "#28a745",       # green
    "MEDIUM": "#ffc107",    # yellow/amber
    "HIGH": "#fd7e14",      # orange
    "CRITICAL": "#dc3545",  # red
}

RISK_EMOJI = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🟠",
    "CRITICAL": "🔴",
}

RISK_LABELS = {
    "LOW": "Low Risk",
    "MEDIUM": "Medium Risk",
    "HIGH": "High Risk",
    "CRITICAL": "Critical Risk",
}

METHODOLOGY_REFERENCES = {
    "benford": {
        "name": "Benford's Law (First-Digit Test)",
        "description": (
            "Tests whether the distribution of leading digits in the dataset "
            "conforms to the logarithmic distribution predicted by Benford's Law. "
            "Fabricated data often shows uniform or biased digit distributions."
        ),
        "references": [
            "Benford, F. (1938). The law of anomalous numbers. Proc. Amer. Phil. Soc., 78(4), 551-572.",
            "Nigrini, M.J. (2012). Benford's Law. Wiley.",
        ],
    },
    "terminal_digit": {
        "name": "Terminal Digit Analysis",
        "description": (
            "Examines the distribution of last digits in numeric data. "
            "Authentic measurements typically show uniform terminal digit distribution, "
            "while fabricated data often exhibits preference for certain digits (e.g., 0, 5)."
        ),
        "references": [
            "Mosimann, J.E., Wiseman, C.V., & Edelman, R.E. (1995). Data fabrication. "
            "Chance, 8(2), 7-12.",
        ],
    },
    "grim": {
        "name": "GRIM Test (Granularity-Related Inconsistency of Means)",
        "description": (
            "Verifies whether reported means are mathematically possible given the "
            "reported sample size and measurement granularity. Impossible means indicate "
            "either reporting errors or data fabrication."
        ),
        "references": [
            "Brown, N.J.L., & Heathers, J.A.J. (2017). The GRIM test. "
            "Social Psychological and Personality Science, 8(4), 363-369.",
        ],
    },
    "sprite": {
        "name": "SPRITE (Sample Parameter Reconstruction via Iterative TEchniques)",
        "description": (
            "Reconstructs possible raw data distributions consistent with reported "
            "summary statistics. Flags cases where no valid distribution exists."
        ),
        "references": [
            "Heathers, J.A.J., & Brown, N.J.L. (2019). SPRITE. PeerJ Preprints.",
        ],
    },
    "distribution": {
        "name": "Distribution Shape Analysis",
        "description": (
            "Tests data against expected statistical distributions using "
            "Kolmogorov-Smirnov, Shapiro-Wilk, or Anderson-Darling tests. "
            "Fabricated data often shows abnormal distributional properties."
        ),
        "references": [
            "Simonsohn, U. (2013). Just post it. Psychological Science, 24(10), 1875-1888.",
        ],
    },
    "duplicates": {
        "name": "Duplicate/Near-Duplicate Detection",
        "description": (
            "Identifies exact and near-duplicate values, rows, or patterns that occur "
            "more frequently than expected by chance."
        ),
        "references": [
            "Bik, E.M., Casadevall, A., & Fang, F.C. (2016). The prevalence of "
            "inappropriate image duplication. mBio, 7(3), e00809-16.",
        ],
    },
    "variance": {
        "name": "Variance Analysis (ANOVA / Levene's Test)",
        "description": (
            "Examines whether variance patterns are consistent with genuine experimental "
            "data. Fabricated data often shows abnormally low or uniform variance."
        ),
        "references": [
            "Carlisle, J.B. (2017). Data fabrication and other reasons for "
            "non-random sampling. Anaesthesia, 72(8), 944-952.",
        ],
    },
    "correlation": {
        "name": "Correlation Structure Analysis",
        "description": (
            "Checks whether inter-variable correlations are biologically/experimentally "
            "plausible. Fabricated data may show correlations that are too perfect or "
            "internally inconsistent."
        ),
        "references": [
            "Simonsohn, U. (2014). Posterior-Hacking. Available at SSRN.",
        ],
    },
}

DISCLAIMER_EN = """
**DISCLAIMER**: This report is generated by an automated statistical analysis tool and is intended
for preliminary screening purposes ONLY. The results do NOT constitute proof of misconduct.
Statistical anomalies can arise from legitimate methodological choices, measurement artifacts,
or natural data properties. Any findings should be interpreted by qualified experts and investigated
through proper institutional channels before any conclusions about research integrity are drawn.
This tool should NEVER be used as the sole basis for accusations of fraud or misconduct.
""".strip()

DISCLAIMER_ZH = """
**免责声明**：本报告由自动化统计分析工具生成，仅用于初步筛查目的。分析结果不构成学术不端的证据。
统计异常可能源于合理的方法学选择、测量误差或数据的自然属性。任何发现都应由具备资质的专家解读，
并通过正规的机构渠道进行调查，方可得出关于研究诚信的结论。本工具绝不应作为指控欺诈或不端行为的
唯一依据。
""".strip()

# ---------------------------------------------------------------------------
# HTML Template & CSS
# ---------------------------------------------------------------------------

HTML_CSS = """
:root {
    --primary: #2c3e50;
    --secondary: #34495e;
    --accent: #3498db;
    --bg: #ffffff;
    --bg-alt: #f8f9fa;
    --border: #dee2e6;
    --text: #212529;
    --text-muted: #6c757d;
    --success: #28a745;
    --warning: #ffc107;
    --danger: #dc3545;
    --orange: #fd7e14;
}

* { box-sizing: border-box; }

body {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
    margin: 0;
    padding: 0;
}

.container {
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem;
}

/* Header */
.report-header {
    border-bottom: 3px solid var(--primary);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
}

.report-header h1 {
    font-size: 1.8rem;
    color: var(--primary);
    margin: 0 0 0.5rem 0;
}

.report-header .subtitle {
    font-size: 1rem;
    color: var(--text-muted);
    margin: 0;
}

/* Risk Badge */
.risk-badge {
    display: inline-block;
    padding: 0.4rem 1rem;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.9rem;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.risk-badge.low { background: var(--success); }
.risk-badge.medium { background: var(--warning); color: #212529; }
.risk-badge.high { background: var(--orange); }
.risk-badge.critical { background: var(--danger); }

/* Score Meter */
.score-meter {
    width: 100%;
    height: 24px;
    background: #e9ecef;
    border-radius: 12px;
    overflow: hidden;
    margin: 0.5rem 0;
}

.score-meter .fill {
    height: 100%;
    border-radius: 12px;
    transition: width 0.5s;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    color: #fff;
}

/* Sections */
.section {
    margin-bottom: 2.5rem;
}

.section h2 {
    font-size: 1.4rem;
    color: var(--primary);
    border-bottom: 2px solid var(--accent);
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
}

.section h3 {
    font-size: 1.1rem;
    color: var(--secondary);
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
}

/* Cards */
.card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.card.risk-low { border-left: 4px solid var(--success); }
.card.risk-medium { border-left: 4px solid var(--warning); }
.card.risk-high { border-left: 4px solid var(--orange); }
.card.risk-critical { border-left: 4px solid var(--danger); }

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.8rem;
}

.card-header h3 {
    margin: 0;
    font-size: 1.05rem;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    font-size: 0.9rem;
}

th, td {
    padding: 0.6rem 0.8rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
}

th {
    background: var(--primary);
    color: #fff;
    font-weight: 600;
    position: sticky;
    top: 0;
}

tr:nth-child(even) {
    background: var(--bg-alt);
}

tr:hover {
    background: #e8f4fd;
}

/* Figures */
.figure-container {
    text-align: center;
    margin: 1rem 0;
}

.figure-container img {
    max-width: 100%;
    height: auto;
    border: 1px solid var(--border);
    border-radius: 4px;
}

.figure-caption {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 0.4rem;
    font-style: italic;
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
}

.stat-box {
    background: var(--bg-alt);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    text-align: center;
}

.stat-box .stat-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--primary);
}

.stat-box .stat-label {
    font-size: 0.8rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Evidence */
.evidence-list {
    list-style: none;
    padding: 0;
}

.evidence-list li {
    padding: 0.4rem 0;
    padding-left: 1.5rem;
    position: relative;
}

.evidence-list li::before {
    content: '•';
    position: absolute;
    left: 0.5rem;
    color: var(--accent);
    font-weight: 700;
}

/* Suspicious Points Table */
.suspicious-row {
    background: #fff3cd !important;
}

/* Disclaimer */
.disclaimer {
    background: #f8d7da;
    border: 1px solid #f5c6cb;
    border-radius: 6px;
    padding: 1.2rem;
    margin: 2rem 0;
    font-size: 0.9rem;
}

.disclaimer h3 {
    color: var(--danger);
    margin-top: 0;
}

/* Footer */
.report-footer {
    border-top: 2px solid var(--border);
    padding-top: 1rem;
    margin-top: 3rem;
    font-size: 0.8rem;
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
}

/* Print Styles */
@media print {
    body { font-size: 10pt; }
    .container { max-width: 100%; padding: 0; }
    .card { break-inside: avoid; }
    .section { break-inside: avoid; }
    table { font-size: 8pt; }
    .report-header { border-bottom-width: 2px; }
}

/* Recommendations */
.recommendation {
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
    padding: 0.8rem;
    margin-bottom: 0.5rem;
    background: var(--bg-alt);
    border-radius: 6px;
}

.recommendation .priority-num {
    background: var(--accent);
    color: #fff;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.85rem;
    flex-shrink: 0;
}

.recommendation .rec-content {
    flex: 1;
}

.recommendation .rec-action {
    font-weight: 600;
    margin-bottom: 0.2rem;
}

.recommendation .rec-rationale {
    font-size: 0.85rem;
    color: var(--text-muted);
}

/* Methodology */
.method-entry {
    margin-bottom: 1.2rem;
    padding-left: 1rem;
    border-left: 3px solid var(--accent);
}

.method-entry .method-name {
    font-weight: 700;
    margin-bottom: 0.3rem;
}

.method-entry .method-desc {
    font-size: 0.9rem;
    margin-bottom: 0.3rem;
}

.method-entry .method-ref {
    font-size: 0.8rem;
    color: var(--text-muted);
    font-style: italic;
}
"""

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def load_assessment(path: str) -> Dict[str, Any]:
    """Load and validate the assessment JSON file.

    Args:
        path: Path to the assessment JSON file.

    Returns:
        Parsed assessment dictionary.

    Raises:
        FileNotFoundError: If the assessment file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If required fields are missing.
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Assessment file not found: {path}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate required top-level keys
    required = ["metadata", "overall_risk", "modules"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Assessment JSON missing required keys: {missing}")

    return data


def encode_figure_base64(figure_path: str, figures_dir: str) -> Optional[str]:
    """Encode a figure file as base64 data URI for HTML embedding.

    Args:
        figure_path: Filename or relative path of the figure.
        figures_dir: Directory containing figures.

    Returns:
        Base64 data URI string, or None if file not found.
    """
    full_path = Path(figures_dir) / figure_path
    if not full_path.exists():
        return None

    suffix = full_path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(suffix, "image/png")

    with open(full_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    return f"data:{mime_type};base64,{encoded}"


def risk_level_to_css_class(level: str) -> str:
    """Convert risk level string to CSS class name.

    Args:
        level: Risk level (LOW, MEDIUM, HIGH, CRITICAL).

    Returns:
        CSS class string.
    """
    return level.lower()


def format_p_value(p: Optional[float]) -> str:
    """Format a p-value for display with appropriate precision.

    Args:
        p: The p-value to format, or None.

    Returns:
        Formatted string representation.
    """
    if p is None:
        return "N/A"
    if p < 0.001:
        return f"< 0.001 (p = {p:.2e})"
    elif p < 0.01:
        return f"{p:.4f}"
    elif p < 0.05:
        return f"{p:.3f}"
    else:
        return f"{p:.3f}"


def score_to_color(score: float) -> str:
    """Map a 0-100 risk score to a gradient color.

    Args:
        score: Risk score (0-100).

    Returns:
        CSS color string.
    """
    if score <= 25:
        return RISK_COLORS["LOW"]
    elif score <= 50:
        return RISK_COLORS["MEDIUM"]
    elif score <= 75:
        return RISK_COLORS["HIGH"]
    else:
        return RISK_COLORS["CRITICAL"]


def score_to_level(score: float) -> str:
    """Map a 0-100 risk score to a risk level string.

    Args:
        score: Risk score (0-100).

    Returns:
        Risk level string.
    """
    if score <= 25:
        return "LOW"
    elif score <= 50:
        return "MEDIUM"
    elif score <= 75:
        return "HIGH"
    else:
        return "CRITICAL"


# ---------------------------------------------------------------------------
# HTML Report Generator
# ---------------------------------------------------------------------------


class HTMLReportGenerator:
    """Generates a self-contained HTML report from assessment data.

    The report includes embedded CSS, base64-encoded figures, and is
    designed to be printable without external dependencies.

    Attributes:
        assessment: The assessment data dictionary.
        figures_dir: Path to the directory containing figure files.
    """

    def __init__(self, assessment: Dict[str, Any], figures_dir: str):
        """Initialize the HTML report generator.

        Args:
            assessment: Parsed assessment dictionary.
            figures_dir: Path to directory containing figure image files.
        """
        self.assessment = assessment
        self.figures_dir = figures_dir

    def generate(self) -> str:
        """Generate the complete HTML report.

        Returns:
            Complete HTML document as a string.
        """
        parts = [
            self._html_head(),
            '<body>',
            '<div class="container">',
            self._header(),
            self._executive_summary(),
            self._data_overview(),
            self._module_results(),
            self._suspicious_points(),
            self._confidence_limitations(),
            self._methodology(),
            self._recommendations(),
            self._disclaimer(),
            self._footer(),
            '</div>',
            '</body>',
            '</html>',
        ]
        return "\n".join(parts)

    def _html_head(self) -> str:
        """Generate HTML head with embedded CSS."""
        title = f"{TOOL_NAME} — Analysis Report"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{HTML_CSS}</style>
</head>"""

    def _header(self) -> str:
        """Generate report header section."""
        meta = self.assessment.get("metadata", {})
        source = meta.get("source_file", "Unknown")
        timestamp = meta.get("timestamp", datetime.now(timezone.utc).isoformat())

        return f"""
<div class="report-header">
    <h1>📊 {TOOL_NAME}</h1>
    <p class="subtitle">Analysis Report — {source}</p>
    <p class="subtitle">Generated: {timestamp}</p>
</div>"""

    def _executive_summary(self) -> str:
        """Generate executive summary section with overall risk score."""
        risk = self.assessment.get("overall_risk", {})
        score = risk.get("score", 0)
        level = risk.get("level", score_to_level(score))
        color = score_to_color(score)
        emoji = RISK_EMOJI.get(level, "⚪")
        label = RISK_LABELS.get(level, "Unknown")

        # Key findings
        modules = self.assessment.get("modules", [])
        flagged = [m for m in modules if m.get("risk_level", "LOW") in ("HIGH", "CRITICAL")]
        suspicious_count = len(self.assessment.get("suspicious_points", []))

        findings_html = ""
        if flagged:
            findings_html = "<ul>"
            for m in flagged:
                me = RISK_EMOJI.get(m.get("risk_level", "LOW"), "⚪")
                findings_html += f'<li>{me} <strong>{m.get("name", "Unknown")}</strong>: {m.get("evidence_summary", "Anomaly detected")}</li>'
            findings_html += "</ul>"
        else:
            findings_html = "<p>No high-risk anomalies detected across all modules.</p>"

        # Conclusion
        if level == "CRITICAL":
            conclusion = (
                "Multiple strong statistical indicators suggest significant anomalies in this dataset. "
                "The patterns observed are highly unlikely to arise from legitimate experimental data. "
                "Further expert review is strongly recommended."
            )
        elif level == "HIGH":
            conclusion = (
                "Several statistical indicators show notable anomalies that warrant further investigation. "
                "While not conclusive evidence of data integrity issues, the patterns deserve scrutiny."
            )
        elif level == "MEDIUM":
            conclusion = (
                "Some mild statistical anomalies were detected. These may reflect legitimate methodological "
                "choices or minor reporting inconsistencies. Routine verification is advisable."
            )
        else:
            conclusion = (
                "The dataset shows no significant statistical anomalies across the tests performed. "
                "The data patterns appear consistent with legitimate experimental measurements."
            )

        return f"""
<div class="section">
    <h2>Executive Summary</h2>
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-value" style="color: {color}">{score}/100</div>
            <div class="stat-label">Overall Risk Score</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{emoji} {label}</div>
            <div class="stat-label">Risk Level</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{len(modules)}</div>
            <div class="stat-label">Tests Performed</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" style="color: {'var(--danger)' if suspicious_count > 0 else 'var(--success)'}">{suspicious_count}</div>
            <div class="stat-label">Suspicious Data Points</div>
        </div>
    </div>
    <div class="score-meter">
        <div class="fill" style="width: {score}%; background: {color};">{score}%</div>
    </div>
    <h3>Key Findings</h3>
    {findings_html}
    <h3>Conclusion</h3>
    <p>{conclusion}</p>
</div>"""

    def _data_overview(self) -> str:
        """Generate data overview section with column stats and preview."""
        overview = self.assessment.get("data_overview", {})
        meta = self.assessment.get("metadata", {})

        # File info
        source = meta.get("source_file", "Unknown")
        rows = meta.get("rows", "N/A")
        cols = meta.get("columns_count", len(meta.get("columns", [])))
        file_size = meta.get("file_size", "N/A")

        info_html = f"""
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-value" style="font-size:1rem">{source}</div>
            <div class="stat-label">Source File</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{rows}</div>
            <div class="stat-label">Rows</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{cols}</div>
            <div class="stat-label">Columns</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" style="font-size:1rem">{file_size}</div>
            <div class="stat-label">File Size</div>
        </div>
    </div>"""

        # Column statistics table
        statistics = overview.get("statistics", {})
        stats_table = ""
        if statistics:
            stats_table = """
    <h3>Column Statistics</h3>
    <table>
        <tr><th>Column</th><th>Type</th><th>Non-Null</th><th>Mean</th><th>Std</th><th>Min</th><th>Max</th></tr>"""
            for col_name, stats in statistics.items():
                dtype = stats.get("dtype", "—")
                non_null = stats.get("non_null", "—")
                mean = stats.get("mean", "—")
                std = stats.get("std", "—")
                min_val = stats.get("min", "—")
                max_val = stats.get("max", "—")
                # Format numeric values
                if isinstance(mean, float):
                    mean = f"{mean:.4g}"
                if isinstance(std, float):
                    std = f"{std:.4g}"
                if isinstance(min_val, float):
                    min_val = f"{min_val:.4g}"
                if isinstance(max_val, float):
                    max_val = f"{max_val:.4g}"
                stats_table += f"\n        <tr><td>{col_name}</td><td>{dtype}</td><td>{non_null}</td><td>{mean}</td><td>{std}</td><td>{min_val}</td><td>{max_val}</td></tr>"
            stats_table += "\n    </table>"

        # Preview table
        preview = overview.get("preview", [])
        preview_html = ""
        if preview:
            columns = overview.get("columns", list(preview[0].keys()) if preview else [])
            preview_html = "\n    <h3>Data Preview (first rows)</h3>\n    <table>\n        <tr>"
            for col in columns:
                preview_html += f"<th>{col}</th>"
            preview_html += "</tr>"
            for row in preview[:10]:
                preview_html += "\n        <tr>"
                for col in columns:
                    val = row.get(col, "—")
                    preview_html += f"<td>{val}</td>"
                preview_html += "</tr>"
            preview_html += "\n    </table>"

        return f"""
<div class="section">
    <h2>Data Overview</h2>
    {info_html}
    {stats_table}
    {preview_html}
</div>"""

    def _module_results(self) -> str:
        """Generate module-by-module results section."""
        modules = self.assessment.get("modules", [])
        if not modules:
            return """
<div class="section">
    <h2>Module-by-Module Results</h2>
    <p>No detection modules were executed.</p>
</div>"""

        cards_html = ""
        for i, module in enumerate(modules, 1):
            name = module.get("name", f"Module {i}")
            description = module.get("description", "No description available.")
            method = module.get("method", "Unknown method")
            risk_level = module.get("risk_level", "LOW")
            p_value = module.get("p_value")
            test_stat = module.get("test_statistic")
            evidence = module.get("evidence_summary", "")
            results = module.get("results", {})
            figures = module.get("figures", [])

            css_class = risk_level_to_css_class(risk_level)
            emoji = RISK_EMOJI.get(risk_level, "⚪")
            label = RISK_LABELS.get(risk_level, "Unknown")
            color = RISK_COLORS.get(risk_level, "#6c757d")

            # Statistics row
            stats_html = '<div class="stats-grid">'
            if p_value is not None:
                stats_html += f"""
                <div class="stat-box">
                    <div class="stat-value" style="font-size:1rem">{format_p_value(p_value)}</div>
                    <div class="stat-label">p-value</div>
                </div>"""
            if test_stat is not None:
                ts_display = f"{test_stat:.4g}" if isinstance(test_stat, float) else str(test_stat)
                stats_html += f"""
                <div class="stat-box">
                    <div class="stat-value" style="font-size:1rem">{ts_display}</div>
                    <div class="stat-label">Test Statistic</div>
                </div>"""
            stats_html += f"""
                <div class="stat-box">
                    <div class="stat-value" style="color:{color}">{emoji} {label}</div>
                    <div class="stat-label">Risk Assessment</div>
                </div>
            </div>"""

            # Additional results
            results_html = ""
            if results:
                results_html = "<h4>Detailed Results</h4><ul class='evidence-list'>"
                for key, val in results.items():
                    if isinstance(val, float):
                        val = f"{val:.4g}"
                    results_html += f"<li><strong>{key}</strong>: {val}</li>"
                results_html += "</ul>"

            # Figures
            figures_html = ""
            for fig in figures:
                b64 = encode_figure_base64(fig, self.figures_dir)
                if b64:
                    figures_html += f"""
                <div class="figure-container">
                    <img src="{b64}" alt="{name} - {fig}">
                    <p class="figure-caption">{fig}</p>
                </div>"""

            # Evidence summary
            evidence_html = ""
            if evidence:
                evidence_html = f"<p><strong>Evidence:</strong> {evidence}</p>"

            cards_html += f"""
    <div class="card risk-{css_class}">
        <div class="card-header">
            <h3>{emoji} {name}</h3>
            <span class="risk-badge {css_class}">{label}</span>
        </div>
        <p><em>{description}</em></p>
        <p><strong>Method:</strong> {method}</p>
        {stats_html}
        {evidence_html}
        {results_html}
        {figures_html}
    </div>"""

        return f"""
<div class="section">
    <h2>Module-by-Module Results</h2>
    {cards_html}
</div>"""

    def _suspicious_points(self) -> str:
        """Generate suspicious data points section."""
        points = self.assessment.get("suspicious_points", [])

        if not points:
            return """
<div class="section">
    <h2>Suspicious Data Points</h2>
    <p>🟢 No individual data points were flagged as suspicious.</p>
</div>"""

        table_html = """
    <table>
        <tr><th>#</th><th>Row</th><th>Column</th><th>Value</th><th>Reason</th><th>Module</th></tr>"""

        for i, point in enumerate(points, 1):
            row = point.get("row", "—")
            col = point.get("column", "—")
            value = point.get("value", "—")
            reason = point.get("reason", "—")
            module = point.get("module", "—")
            if isinstance(value, float):
                value = f"{value:.6g}"
            table_html += f"""
        <tr class="suspicious-row">
            <td>{i}</td><td>{row}</td><td>{col}</td><td>{value}</td><td>{reason}</td><td>{module}</td>
        </tr>"""

        table_html += "\n    </table>"

        return f"""
<div class="section">
    <h2>🔍 Suspicious Data Points</h2>
    <p>The following <strong>{len(points)}</strong> data point(s) triggered alerts. Each entry shows the
    exact row/column reference, the observed value, and the reason for flagging.</p>
    {table_html}
</div>"""

    def _confidence_limitations(self) -> str:
        """Generate confidence and limitations section."""
        confidence = self.assessment.get("confidence", {})
        overall_conf = confidence.get("overall", "Not calculated")
        intervals = confidence.get("intervals", {})
        limitations = confidence.get("limitations", [])

        # Confidence intervals
        intervals_html = ""
        if intervals:
            intervals_html = """
    <h3>Confidence Intervals</h3>
    <table>
        <tr><th>Measure</th><th>Estimate</th><th>95% CI Lower</th><th>95% CI Upper</th></tr>"""
            for measure, data in intervals.items():
                est = data.get("estimate", "—")
                lower = data.get("ci_lower", "—")
                upper = data.get("ci_upper", "—")
                if isinstance(est, float):
                    est = f"{est:.4g}"
                if isinstance(lower, float):
                    lower = f"{lower:.4g}"
                if isinstance(upper, float):
                    upper = f"{upper:.4g}"
                intervals_html += f"\n        <tr><td>{measure}</td><td>{est}</td><td>{lower}</td><td>{upper}</td></tr>"
            intervals_html += "\n    </table>"

        # Limitations
        limitations_html = ""
        if limitations:
            limitations_html = "\n    <h3>Limitations — What This Tool Cannot Detect</h3>\n    <ul>"
            for lim in limitations:
                limitations_html += f"\n        <li>{lim}</li>"
            limitations_html += "\n    </ul>"
        else:
            # Default limitations
            limitations_html = """
    <h3>Limitations — What This Tool Cannot Detect</h3>
    <ul>
        <li>Selective reporting or HARKing (Hypothesizing After Results are Known)</li>
        <li>Subtle p-hacking through flexible analysis choices</li>
        <li>Data fabrication that perfectly mimics expected statistical properties</li>
        <li>Image manipulation or duplication (requires specialized image forensics)</li>
        <li>Plagiarism or text recycling</li>
        <li>Errors in experimental design or methodology</li>
        <li>Conflicts of interest or undisclosed funding</li>
        <li>Small-scale selective data exclusion that preserves distributional properties</li>
    </ul>"""

        # Overall confidence display
        if isinstance(overall_conf, (int, float)):
            conf_display = f"{overall_conf:.1%}" if overall_conf <= 1 else f"{overall_conf:.1f}%"
        else:
            conf_display = str(overall_conf)

        return f"""
<div class="section">
    <h2>Confidence &amp; Limitations</h2>
    <div class="stat-box" style="max-width:300px; margin: 1rem 0;">
        <div class="stat-value">{conf_display}</div>
        <div class="stat-label">Overall Assessment Confidence</div>
    </div>
    <p>Confidence reflects the reliability of the statistical tests given the data size,
    quality, and number of applicable tests. Higher confidence means the results are
    more likely to be meaningful rather than artifacts of small samples or noise.</p>
    {intervals_html}
    {limitations_html}
</div>"""

    def _methodology(self) -> str:
        """Generate methodology section with academic references."""
        modules = self.assessment.get("modules", [])
        methods_used = set()
        for m in modules:
            method_key = m.get("method_key", m.get("name", "").lower().replace(" ", "_"))
            methods_used.add(method_key)

        entries_html = ""
        for key in sorted(methods_used):
            info = METHODOLOGY_REFERENCES.get(key)
            if info:
                refs_html = "<br>".join(info["references"])
                entries_html += f"""
    <div class="method-entry">
        <div class="method-name">{info['name']}</div>
        <div class="method-desc">{info['description']}</div>
        <div class="method-ref">{refs_html}</div>
    </div>"""

        # If no known methods matched, list from module descriptions
        if not entries_html:
            for m in modules:
                name = m.get("name", "Unknown")
                method = m.get("method", "Not specified")
                entries_html += f"""
    <div class="method-entry">
        <div class="method-name">{name}</div>
        <div class="method-desc">Method: {method}</div>
    </div>"""

        return f"""
<div class="section">
    <h2>Methodology</h2>
    <p>The following statistical methods were applied during this analysis.
    Each method targets a specific class of data integrity anomalies.</p>
    {entries_html}
</div>"""

    def _recommendations(self) -> str:
        """Generate prioritized recommendations section."""
        recs = self.assessment.get("recommendations", [])

        if not recs:
            # Generate default recommendations based on risk level
            risk = self.assessment.get("overall_risk", {})
            level = risk.get("level", "LOW")
            if level in ("HIGH", "CRITICAL"):
                recs = [
                    {"priority": 1, "action": "Request raw data and analysis scripts from authors",
                     "rationale": "Direct verification of data provenance is the most reliable method."},
                    {"priority": 2, "action": "Have an independent statistician review the flagged anomalies",
                     "rationale": "Expert review can distinguish genuine anomalies from methodological artifacts."},
                    {"priority": 3, "action": "Check for corroborating evidence in supplementary materials",
                     "rationale": "Supplementary data may provide context that explains apparent anomalies."},
                    {"priority": 4, "action": "Consider contacting the journal or institution",
                     "rationale": "If anomalies persist after review, formal investigation may be warranted."},
                ]
            else:
                recs = [
                    {"priority": 1, "action": "Archive this report for reference",
                     "rationale": "Maintaining records supports longitudinal monitoring."},
                    {"priority": 2, "action": "No immediate action required",
                     "rationale": "Current findings do not indicate significant integrity concerns."},
                ]

        recs_html = ""
        for rec in sorted(recs, key=lambda r: r.get("priority", 99)):
            priority = rec.get("priority", "—")
            action = rec.get("action", "—")
            rationale = rec.get("rationale", "")
            recs_html += f"""
    <div class="recommendation">
        <div class="priority-num">{priority}</div>
        <div class="rec-content">
            <div class="rec-action">{action}</div>
            <div class="rec-rationale">{rationale}</div>
        </div>
    </div>"""

        return f"""
<div class="section">
    <h2>Recommendations</h2>
    {recs_html}
</div>"""

    def _disclaimer(self) -> str:
        """Generate bilingual disclaimer section."""
        return f"""
<div class="disclaimer">
    <h3>⚠️ Disclaimer / 免责声明</h3>
    <p>{DISCLAIMER_EN}</p>
    <hr style="border-color:#f5c6cb; margin: 1rem 0;">
    <p>{DISCLAIMER_ZH}</p>
</div>"""

    def _footer(self) -> str:
        """Generate report footer with metadata."""
        meta = self.assessment.get("metadata", {})
        source = meta.get("source_file", "Unknown")
        version = meta.get("tool_version", TOOL_VERSION)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        return f"""
<div class="report-footer">
    <span>Generated by {TOOL_NAME} v{version}</span>
    <span>Input: {source}</span>
    <span>Report timestamp: {now}</span>
</div>"""


# ---------------------------------------------------------------------------
# Markdown Report Generator
# ---------------------------------------------------------------------------


class MarkdownReportGenerator:
    """Generates a Markdown report from assessment data.

    Figures are referenced as relative paths (suitable for GitHub rendering).

    Attributes:
        assessment: The assessment data dictionary.
        figures_dir: Relative path to figures directory for Markdown links.
    """

    def __init__(self, assessment: Dict[str, Any], figures_dir: str):
        """Initialize the Markdown report generator.

        Args:
            assessment: Parsed assessment dictionary.
            figures_dir: Relative path to figures directory for image links.
        """
        self.assessment = assessment
        self.figures_dir = figures_dir

    def generate(self) -> str:
        """Generate the complete Markdown report.

        Returns:
            Complete Markdown document as a string.
        """
        parts = [
            self._header(),
            self._executive_summary(),
            self._data_overview(),
            self._module_results(),
            self._suspicious_points(),
            self._confidence_limitations(),
            self._methodology(),
            self._recommendations(),
            self._disclaimer(),
            self._footer(),
        ]
        return "\n\n".join(parts)

    def _header(self) -> str:
        """Generate Markdown header."""
        meta = self.assessment.get("metadata", {})
        source = meta.get("source_file", "Unknown")
        timestamp = meta.get("timestamp", datetime.now(timezone.utc).isoformat())

        return f"""# 📊 {TOOL_NAME}

## Analysis Report

- **Source File:** {source}
- **Generated:** {timestamp}
- **Tool Version:** {meta.get('tool_version', TOOL_VERSION)}

---"""

    def _executive_summary(self) -> str:
        """Generate executive summary in Markdown."""
        risk = self.assessment.get("overall_risk", {})
        score = risk.get("score", 0)
        level = risk.get("level", score_to_level(score))
        emoji = RISK_EMOJI.get(level, "⚪")
        label = RISK_LABELS.get(level, "Unknown")

        modules = self.assessment.get("modules", [])
        flagged = [m for m in modules if m.get("risk_level", "LOW") in ("HIGH", "CRITICAL")]
        suspicious_count = len(self.assessment.get("suspicious_points", []))

        findings = ""
        if flagged:
            for m in flagged:
                me = RISK_EMOJI.get(m.get("risk_level", "LOW"), "⚪")
                findings += f"- {me} **{m.get('name', 'Unknown')}**: {m.get('evidence_summary', 'Anomaly detected')}\n"
        else:
            findings = "- No high-risk anomalies detected across all modules.\n"

        # Conclusion
        if level == "CRITICAL":
            conclusion = (
                "Multiple strong statistical indicators suggest significant anomalies in this dataset. "
                "The patterns observed are highly unlikely to arise from legitimate experimental data. "
                "Further expert review is strongly recommended."
            )
        elif level == "HIGH":
            conclusion = (
                "Several statistical indicators show notable anomalies that warrant further investigation. "
                "While not conclusive evidence of data integrity issues, the patterns deserve scrutiny."
            )
        elif level == "MEDIUM":
            conclusion = (
                "Some mild statistical anomalies were detected. These may reflect legitimate methodological "
                "choices or minor reporting inconsistencies. Routine verification is advisable."
            )
        else:
            conclusion = (
                "The dataset shows no significant statistical anomalies across the tests performed. "
                "The data patterns appear consistent with legitimate experimental measurements."
            )

        return f"""## Executive Summary

| Metric | Value |
|--------|-------|
| **Overall Risk Score** | {score}/100 |
| **Risk Level** | {emoji} {label} |
| **Tests Performed** | {len(modules)} |
| **Suspicious Data Points** | {suspicious_count} |

### Key Findings

{findings}
### Conclusion

{conclusion}"""

    def _data_overview(self) -> str:
        """Generate data overview in Markdown."""
        overview = self.assessment.get("data_overview", {})
        meta = self.assessment.get("metadata", {})

        source = meta.get("source_file", "Unknown")
        rows = meta.get("rows", "N/A")
        cols = meta.get("columns_count", len(meta.get("columns", [])))
        file_size = meta.get("file_size", "N/A")

        md = f"""## Data Overview

| Property | Value |
|----------|-------|
| Source File | {source} |
| Rows | {rows} |
| Columns | {cols} |
| File Size | {file_size} |
"""

        # Column statistics
        statistics = overview.get("statistics", {})
        if statistics:
            md += "\n### Column Statistics\n\n"
            md += "| Column | Type | Non-Null | Mean | Std | Min | Max |\n"
            md += "|--------|------|----------|------|-----|-----|-----|\n"
            for col_name, stats in statistics.items():
                dtype = stats.get("dtype", "—")
                non_null = stats.get("non_null", "—")
                mean = stats.get("mean", "—")
                std = stats.get("std", "—")
                min_val = stats.get("min", "—")
                max_val = stats.get("max", "—")
                if isinstance(mean, float):
                    mean = f"{mean:.4g}"
                if isinstance(std, float):
                    std = f"{std:.4g}"
                if isinstance(min_val, float):
                    min_val = f"{min_val:.4g}"
                if isinstance(max_val, float):
                    max_val = f"{max_val:.4g}"
                md += f"| {col_name} | {dtype} | {non_null} | {mean} | {std} | {min_val} | {max_val} |\n"

        # Preview
        preview = overview.get("preview", [])
        if preview:
            columns = overview.get("columns", list(preview[0].keys()) if preview else [])
            md += "\n### Data Preview\n\n"
            md += "| " + " | ".join(str(c) for c in columns) + " |\n"
            md += "| " + " | ".join("---" for _ in columns) + " |\n"
            for row in preview[:10]:
                vals = [str(row.get(c, "—")) for c in columns]
                md += "| " + " | ".join(vals) + " |\n"

        return md

    def _module_results(self) -> str:
        """Generate module results in Markdown."""
        modules = self.assessment.get("modules", [])
        if not modules:
            return "## Module-by-Module Results\n\nNo detection modules were executed."

        md = "## Module-by-Module Results\n"

        for i, module in enumerate(modules, 1):
            name = module.get("name", f"Module {i}")
            description = module.get("description", "No description available.")
            method = module.get("method", "Unknown method")
            risk_level = module.get("risk_level", "LOW")
            p_value = module.get("p_value")
            test_stat = module.get("test_statistic")
            evidence = module.get("evidence_summary", "")
            results = module.get("results", {})
            figures = module.get("figures", [])

            emoji = RISK_EMOJI.get(risk_level, "⚪")
            label = RISK_LABELS.get(risk_level, "Unknown")

            md += f"\n### {emoji} {name}\n\n"
            md += f"**Description:** {description}\n\n"
            md += f"**Method:** {method}\n\n"

            # Statistics table
            md += "| Metric | Value |\n|--------|-------|\n"
            if p_value is not None:
                md += f"| p-value | {format_p_value(p_value)} |\n"
            if test_stat is not None:
                ts = f"{test_stat:.4g}" if isinstance(test_stat, float) else str(test_stat)
                md += f"| Test Statistic | {ts} |\n"
            md += f"| Risk Assessment | {emoji} {label} |\n"

            if evidence:
                md += f"\n**Evidence:** {evidence}\n"

            # Detailed results
            if results:
                md += "\n**Detailed Results:**\n\n"
                for key, val in results.items():
                    if isinstance(val, float):
                        val = f"{val:.4g}"
                    md += f"- **{key}**: {val}\n"

            # Figures
            for fig in figures:
                fig_path = f"{self.figures_dir}/{fig}" if self.figures_dir else fig
                md += f"\n![{name} - {fig}]({fig_path})\n"
                md += f"*Figure: {fig}*\n"

            md += "\n---\n"

        return md

    def _suspicious_points(self) -> str:
        """Generate suspicious points section in Markdown."""
        points = self.assessment.get("suspicious_points", [])

        if not points:
            return "## 🔍 Suspicious Data Points\n\n🟢 No individual data points were flagged as suspicious."

        md = f"## 🔍 Suspicious Data Points\n\n"
        md += f"The following **{len(points)}** data point(s) triggered alerts:\n\n"
        md += "| # | Row | Column | Value | Reason | Module |\n"
        md += "|---|-----|--------|-------|--------|--------|\n"

        for i, point in enumerate(points, 1):
            row = point.get("row", "—")
            col = point.get("column", "—")
            value = point.get("value", "—")
            reason = point.get("reason", "—")
            module = point.get("module", "—")
            if isinstance(value, float):
                value = f"{value:.6g}"
            md += f"| {i} | {row} | {col} | {value} | {reason} | {module} |\n"

        return md

    def _confidence_limitations(self) -> str:
        """Generate confidence and limitations section in Markdown."""
        confidence = self.assessment.get("confidence", {})
        overall_conf = confidence.get("overall", "Not calculated")
        intervals = confidence.get("intervals", {})
        limitations = confidence.get("limitations", [])

        if isinstance(overall_conf, (int, float)):
            conf_display = f"{overall_conf:.1%}" if overall_conf <= 1 else f"{overall_conf:.1f}%"
        else:
            conf_display = str(overall_conf)

        md = f"## Confidence & Limitations\n\n"
        md += f"**Overall Assessment Confidence:** {conf_display}\n\n"
        md += (
            "Confidence reflects the reliability of the statistical tests given the data size, "
            "quality, and number of applicable tests.\n"
        )

        if intervals:
            md += "\n### Confidence Intervals\n\n"
            md += "| Measure | Estimate | 95% CI Lower | 95% CI Upper |\n"
            md += "|---------|----------|--------------|-------------|\n"
            for measure, data in intervals.items():
                est = data.get("estimate", "—")
                lower = data.get("ci_lower", "—")
                upper = data.get("ci_upper", "—")
                if isinstance(est, float):
                    est = f"{est:.4g}"
                if isinstance(lower, float):
                    lower = f"{lower:.4g}"
                if isinstance(upper, float):
                    upper = f"{upper:.4g}"
                md += f"| {measure} | {est} | {lower} | {upper} |\n"

        md += "\n### Limitations — What This Tool Cannot Detect\n\n"
        if limitations:
            for lim in limitations:
                md += f"- {lim}\n"
        else:
            md += """- Selective reporting or HARKing (Hypothesizing After Results are Known)
- Subtle p-hacking through flexible analysis choices
- Data fabrication that perfectly mimics expected statistical properties
- Image manipulation or duplication (requires specialized image forensics)
- Plagiarism or text recycling
- Errors in experimental design or methodology
- Conflicts of interest or undisclosed funding
- Small-scale selective data exclusion that preserves distributional properties
"""

        return md

    def _methodology(self) -> str:
        """Generate methodology section in Markdown."""
        modules = self.assessment.get("modules", [])
        methods_used = set()
        for m in modules:
            method_key = m.get("method_key", m.get("name", "").lower().replace(" ", "_"))
            methods_used.add(method_key)

        md = "## Methodology\n\n"
        md += "The following statistical methods were applied during this analysis:\n\n"

        has_entries = False
        for key in sorted(methods_used):
            info = METHODOLOGY_REFERENCES.get(key)
            if info:
                has_entries = True
                md += f"### {info['name']}\n\n"
                md += f"{info['description']}\n\n"
                md += "**References:**\n\n"
                for ref in info["references"]:
                    md += f"- {ref}\n"
                md += "\n"

        if not has_entries:
            for m in modules:
                name = m.get("name", "Unknown")
                method = m.get("method", "Not specified")
                md += f"### {name}\n\n"
                md += f"Method: {method}\n\n"

        return md

    def _recommendations(self) -> str:
        """Generate recommendations section in Markdown."""
        recs = self.assessment.get("recommendations", [])

        if not recs:
            risk = self.assessment.get("overall_risk", {})
            level = risk.get("level", "LOW")
            if level in ("HIGH", "CRITICAL"):
                recs = [
                    {"priority": 1, "action": "Request raw data and analysis scripts from authors",
                     "rationale": "Direct verification of data provenance is the most reliable method."},
                    {"priority": 2, "action": "Have an independent statistician review the flagged anomalies",
                     "rationale": "Expert review can distinguish genuine anomalies from methodological artifacts."},
                    {"priority": 3, "action": "Check for corroborating evidence in supplementary materials",
                     "rationale": "Supplementary data may provide context that explains apparent anomalies."},
                    {"priority": 4, "action": "Consider contacting the journal or institution",
                     "rationale": "If anomalies persist after review, formal investigation may be warranted."},
                ]
            else:
                recs = [
                    {"priority": 1, "action": "Archive this report for reference",
                     "rationale": "Maintaining records supports longitudinal monitoring."},
                    {"priority": 2, "action": "No immediate action required",
                     "rationale": "Current findings do not indicate significant integrity concerns."},
                ]

        md = "## Recommendations\n\n"
        for rec in sorted(recs, key=lambda r: r.get("priority", 99)):
            priority = rec.get("priority", "—")
            action = rec.get("action", "—")
            rationale = rec.get("rationale", "")
            md += f"**{priority}.** {action}\n"
            if rationale:
                md += f"   > {rationale}\n"
            md += "\n"

        return md

    def _disclaimer(self) -> str:
        """Generate bilingual disclaimer in Markdown."""
        return f"""## ⚠️ Disclaimer / 免责声明

{DISCLAIMER_EN}

---

{DISCLAIMER_ZH}"""

    def _footer(self) -> str:
        """Generate footer in Markdown."""
        meta = self.assessment.get("metadata", {})
        source = meta.get("source_file", "Unknown")
        version = meta.get("tool_version", TOOL_VERSION)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        return f"""---

*Generated by {TOOL_NAME} v{version} | Input: {source} | Timestamp: {now}*"""


# ---------------------------------------------------------------------------
# Main / CLI
# ---------------------------------------------------------------------------


def generate_reports(
    assessment_path: str,
    figures_dir: str,
    output_dir: str,
    formats: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Generate reports in specified formats from an assessment JSON file.

    Args:
        assessment_path: Path to the assessment JSON file.
        figures_dir: Path to the directory containing figure files.
        output_dir: Directory where output reports will be written.
        formats: List of formats to generate ('html', 'markdown'). Defaults to both.

    Returns:
        Dictionary mapping format names to output file paths.

    Raises:
        FileNotFoundError: If assessment file doesn't exist.
        ValueError: If assessment JSON is invalid.
    """
    if formats is None:
        formats = ["html", "markdown"]

    # Load assessment
    assessment = load_assessment(assessment_path)

    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Determine base filename from source
    meta = assessment.get("metadata", {})
    source = meta.get("source_file", "analysis")
    base_name = Path(source).stem if source else "analysis"

    results = {}

    if "html" in formats:
        html_gen = HTMLReportGenerator(assessment, figures_dir)
        html_content = html_gen.generate()
        html_path = output_path / f"{base_name}_report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        results["html"] = str(html_path)
        print(f"✅ HTML report generated: {html_path}")

    if "markdown" in formats:
        # For markdown, use relative path to figures
        try:
            rel_figures = os.path.relpath(figures_dir, output_dir)
        except ValueError:
            rel_figures = figures_dir
        md_gen = MarkdownReportGenerator(assessment, rel_figures)
        md_content = md_gen.generate()
        md_path = output_path / f"{base_name}_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        results["markdown"] = str(md_path)
        print(f"✅ Markdown report generated: {md_path}")

    return results


def main():
    """CLI entry point for the report generator.

    Parses arguments and generates reports in the specified formats.
    """
    parser = argparse.ArgumentParser(
        description=f"{TOOL_NAME} — Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate both HTML and Markdown reports
  python3 report_generator.py --input assessment.json --figures figures/ --output report/

  # Generate only HTML
  python3 report_generator.py --input assessment.json --figures figures/ --output report/ --format html

  # Generate only Markdown
  python3 report_generator.py --input assessment.json --output report/ --format markdown
""",
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the assessment JSON file produced by the detection pipeline.",
    )
    parser.add_argument(
        "--figures", "-f",
        default="figures/",
        help="Directory containing figure image files (default: figures/).",
    )
    parser.add_argument(
        "--output", "-o",
        default="report/",
        help="Output directory for generated reports (default: report/).",
    )
    parser.add_argument(
        "--format",
        choices=["html", "markdown", "both"],
        default="both",
        help="Output format: html, markdown, or both (default: both).",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"%(prog)s {TOOL_VERSION}",
    )

    args = parser.parse_args()

    # Determine formats
    if args.format == "both":
        formats = ["html", "markdown"]
    else:
        formats = [args.format]

    try:
        results = generate_reports(
            assessment_path=args.input,
            figures_dir=args.figures,
            output_dir=args.output,
            formats=formats,
        )
        print(f"\n{'='*60}")
        print(f"Report generation complete!")
        print(f"{'='*60}")
        for fmt, path in results.items():
            print(f"  {fmt.upper():>10}: {path}")
        print()

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in assessment file: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
