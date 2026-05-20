#!/usr/bin/env python3
"""
visualization.py — Publication-quality figure generation for academic fraud detection reports.

Part of the Geng Skill academic fraud detection project. Generates visualizations
for statistical tests including last-digit analysis, Benford's Law, fixed-ratio
detection, decimal pattern analysis, and comprehensive dashboards.

Usage (CLI):
    python3 visualization.py --input report.json --output figures/

Usage (API):
    from visualization import plot_last_digit, plot_benford, plot_fixed_ratio
    fig_path = plot_last_digit(test_result, output_dir="figures/")
"""

import json
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server environments
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Arc, Wedge
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.ticker as mticker
import seaborn as sns

# ---------------------------------------------------------------------------
# Font Configuration for CJK (Chinese) + English support
# ---------------------------------------------------------------------------

def _configure_fonts():
    """Configure matplotlib to support CJK characters with fallback."""
    # Try common CJK fonts available on Linux/macOS/Windows
    cjk_fonts = [
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "Noto Sans CJK SC",
        "SimHei",
        "Microsoft YaHei",
        "PingFang SC",
        "Hiragino Sans GB",
        "DejaVu Sans",
    ]
    
    available_fonts = set(
        f.name for f in matplotlib.font_manager.fontManager.ttflist
    )
    
    chosen_fonts = []
    for font in cjk_fonts:
        if font in available_fonts:
            chosen_fonts.append(font)
    
    # Fallback: always include DejaVu Sans for guaranteed rendering
    if "DejaVu Sans" not in chosen_fonts:
        chosen_fonts.append("DejaVu Sans")
    
    plt.rcParams["font.sans-serif"] = chosen_fonts + plt.rcParams.get("font.sans-serif", [])
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.family"] = "sans-serif"


_configure_fonts()

# ---------------------------------------------------------------------------
# Style Configuration
# ---------------------------------------------------------------------------

# Publication-quality defaults
STYLE_CONFIG = {
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.labelsize": 11,
    "axes.titlesize": 13,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.grid": False,
}
plt.rcParams.update(STYLE_CONFIG)

# Color palette
COLORS = {
    "observed": "#2196F3",      # Blue
    "expected": "#FF9800",      # Orange
    "highlight": "#F44336",     # Red (anomaly)
    "normal": "#4CAF50",        # Green (normal)
    "neutral": "#9E9E9E",       # Gray
    "regression": "#E91E63",    # Pink
    "scatter": "#3F51B5",       # Indigo
    "risk_low": "#4CAF50",      # Green
    "risk_medium": "#FFC107",   # Amber
    "risk_high": "#FF5722",     # Deep Orange
    "risk_critical": "#D32F2F", # Dark Red
}

# Risk level thresholds
RISK_THRESHOLDS = {
    "low": (0, 25),
    "medium": (25, 50),
    "high": (50, 75),
    "critical": (75, 100),
}


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def _ensure_output_dir(output_dir: str) -> Path:
    """Create output directory if it doesn't exist."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_figure(fig: plt.Figure, filepath: str, dpi: int = 300) -> str:
    """Save figure to file and close it.
    
    Args:
        fig: Matplotlib figure object.
        filepath: Output file path.
        dpi: Resolution in dots per inch.
    
    Returns:
        Absolute path of the saved figure.
    """
    fig.savefig(filepath, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(Path(filepath).resolve())


def _annotate_pvalue(ax: plt.Axes, p_value: float, x: float = 0.95, y: float = 0.95):
    """Add p-value annotation to axes with significance stars."""
    if p_value < 0.001:
        stars = "***"
        color = COLORS["highlight"]
    elif p_value < 0.01:
        stars = "**"
        color = COLORS["risk_high"]
    elif p_value < 0.05:
        stars = "*"
        color = COLORS["risk_medium"]
    else:
        stars = "ns"
        color = COLORS["normal"]
    
    text = f"p = {p_value:.4f} {stars}"
    ax.annotate(
        text,
        xy=(x, y),
        xycoords="axes fraction",
        fontsize=10,
        fontweight="bold",
        color=color,
        ha="right",
        va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8),
    )


# ---------------------------------------------------------------------------
# 1. Last Digit Distribution Plot
# ---------------------------------------------------------------------------

def plot_last_digit(
    result: Dict[str, Any],
    output_dir: str = "figures/",
    filename: str = "last_digit_distribution.png",
    dpi: int = 300,
) -> str:
    """Generate a bar chart of last digit distribution vs. expected uniform distribution.
    
    Shows observed frequencies of last digits (0-9) compared to the expected
    uniform distribution (10% each), with chi-square test p-value annotation.
    
    Args:
        result: Output dict from last-digit test module, expected keys:
            - observed_freq (list/dict): Observed frequencies for digits 0-9.
            - expected_freq (list/dict, optional): Expected frequencies.
            - chi_square (float): Chi-square statistic.
            - p_value (float): P-value from chi-square test.
            - n_samples (int, optional): Total sample count.
            - column_name (str, optional): Name of the analyzed column.
        output_dir: Directory to save the figure.
        filename: Output filename.
        dpi: Resolution.
    
    Returns:
        Path to the saved figure file.
    """
    output_path = _ensure_output_dir(output_dir)
    filepath = str(output_path / filename)
    
    # Extract data
    observed = result.get("observed_freq", result.get("observed", []))
    if isinstance(observed, dict):
        digits = sorted(observed.keys(), key=lambda x: int(x))
        obs_values = [observed[d] for d in digits]
        digits = [int(d) for d in digits]
    else:
        obs_values = list(observed)
        digits = list(range(len(obs_values)))
    
    # Normalize to proportions if raw counts
    obs_array = np.array(obs_values, dtype=float)
    if obs_array.sum() > 1.1:  # Raw counts, convert to proportions
        obs_array = obs_array / obs_array.sum()
    
    n_digits = len(digits)
    expected_prop = 1.0 / n_digits  # Uniform expectation
    
    chi_sq = result.get("chi_square", result.get("chi2", 0.0))
    p_value = result.get("p_value", result.get("pvalue", 1.0))
    n_samples = result.get("n_samples", result.get("n", "N/A"))
    col_name = result.get("column_name", result.get("column", ""))
    
    # Create figure
    fig, ax = plt.subplots(figsize=(8, 5))
    
    x = np.arange(n_digits)
    width = 0.35
    
    # Bar chart
    bars_obs = ax.bar(
        x - width / 2, obs_array, width,
        label="观测频率 Observed", color=COLORS["observed"], alpha=0.85, edgecolor="white"
    )
    bars_exp = ax.bar(
        x + width / 2, [expected_prop] * n_digits, width,
        label=f"期望频率 Expected ({expected_prop:.1%})", color=COLORS["expected"], alpha=0.6, edgecolor="white"
    )
    
    # Reference line
    ax.axhline(y=expected_prop, color=COLORS["neutral"], linestyle="--", linewidth=0.8, alpha=0.6)
    
    # Highlight anomalous digits (>2 standard deviations from expected)
    std_threshold = 2.0 * np.sqrt(expected_prop * (1 - expected_prop) / max(n_samples if isinstance(n_samples, (int, float)) else 100, 1))
    for i, (obs_val, bar) in enumerate(zip(obs_array, bars_obs)):
        if abs(obs_val - expected_prop) > std_threshold:
            bar.set_edgecolor(COLORS["highlight"])
            bar.set_linewidth(2)
    
    # Labels and title
    title = "末位数字分布检验 Last Digit Distribution Test"
    if col_name:
        title += f"\n[{col_name}]"
    ax.set_title(title, fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("末位数字 Last Digit", fontsize=11)
    ax.set_ylabel("频率 Frequency", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(digits)
    ax.set_ylim(0, max(obs_array.max(), expected_prop) * 1.35)
    ax.legend(loc="upper left", framealpha=0.9)
    
    # Annotate statistics
    _annotate_pvalue(ax, p_value)
    stats_text = f"χ² = {chi_sq:.2f}\nn = {n_samples}"
    ax.text(
        0.95, 0.80, stats_text,
        transform=ax.transAxes, fontsize=9,
        ha="right", va="top", color="#555555",
    )
    
    return _save_figure(fig, filepath, dpi)


# ---------------------------------------------------------------------------
# 2. Benford's Law Plot
# ---------------------------------------------------------------------------

def plot_benford(
    result: Dict[str, Any],
    output_dir: str = "figures/",
    filename: str = "benford_law.png",
    dpi: int = 300,
) -> str:
    """Generate a bar chart comparing observed first-digit frequencies to Benford's Law.
    
    Shows observed vs. theoretical Benford distribution with MAD (Mean Absolute
    Deviation) annotation and conformity assessment.
    
    Args:
        result: Output dict from Benford's Law test module, expected keys:
            - observed_freq (list/dict): Observed proportions for digits 1-9.
            - benford_freq (list/dict, optional): Theoretical Benford proportions.
            - mad (float): Mean Absolute Deviation from Benford's Law.
            - conformity (str, optional): Conformity level (e.g., "close", "acceptable").
            - chi_square (float, optional): Chi-square statistic.
            - p_value (float, optional): P-value.
            - column_name (str, optional): Name of the analyzed column.
        output_dir: Directory to save the figure.
        filename: Output filename.
        dpi: Resolution.
    
    Returns:
        Path to the saved figure file.
    """
    output_path = _ensure_output_dir(output_dir)
    filepath = str(output_path / filename)
    
    # Benford's theoretical distribution
    benford_theoretical = {
        d: np.log10(1 + 1 / d) for d in range(1, 10)
    }
    
    # Extract observed data
    observed = result.get("observed_freq", result.get("observed", {}))
    if isinstance(observed, (list, np.ndarray)):
        obs_values = list(observed)
        digits = list(range(1, len(obs_values) + 1))
    else:
        digits = sorted([int(k) for k in observed.keys()])
        obs_values = [observed[str(d)] if str(d) in observed else observed.get(d, 0) for d in digits]
    
    obs_array = np.array(obs_values, dtype=float)
    if obs_array.sum() > 1.1:
        obs_array = obs_array / obs_array.sum()
    
    # Benford expected
    benford_expected = np.array([benford_theoretical.get(d, 0) for d in digits])
    
    mad = result.get("mad", result.get("MAD", np.mean(np.abs(obs_array - benford_expected))))
    conformity = result.get("conformity", result.get("level", ""))
    p_value = result.get("p_value", result.get("pvalue", None))
    col_name = result.get("column_name", result.get("column", ""))
    
    # Create figure
    fig, ax = plt.subplots(figsize=(9, 5.5))
    
    x = np.arange(len(digits))
    width = 0.35
    
    # Bars
    ax.bar(
        x - width / 2, obs_array, width,
        label="观测频率 Observed", color=COLORS["observed"], alpha=0.85, edgecolor="white"
    )
    ax.bar(
        x + width / 2, benford_expected, width,
        label="Benford 理论值 Expected", color=COLORS["expected"], alpha=0.7, edgecolor="white"
    )
    
    # Benford curve overlay
    ax.plot(x, benford_expected, "o-", color=COLORS["expected"], alpha=0.9, linewidth=1.5, markersize=4)
    
    # Title and labels
    title = "Benford 定律检验 Benford's Law Test"
    if col_name:
        title += f"\n[{col_name}]"
    ax.set_title(title, fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("首位数字 First Digit", fontsize=11)
    ax.set_ylabel("频率 Frequency", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(digits)
    ax.set_ylim(0, max(obs_array.max(), benford_expected.max()) * 1.35)
    ax.legend(loc="upper right", framealpha=0.9)
    
    # MAD annotation with color coding
    # MAD thresholds (Nigrini 2012): <0.006 close, <0.012 acceptable, <0.015 marginally acceptable
    if mad < 0.006:
        mad_color = COLORS["normal"]
        mad_label = "Close conformity"
    elif mad < 0.012:
        mad_color = COLORS["risk_medium"]
        mad_label = "Acceptable conformity"
    elif mad < 0.015:
        mad_color = COLORS["risk_high"]
        mad_label = "Marginally acceptable"
    else:
        mad_color = COLORS["highlight"]
        mad_label = "Non-conformity"
    
    if conformity:
        mad_label = conformity
    
    mad_text = f"MAD = {mad:.4f}\n({mad_label})"
    ax.annotate(
        mad_text,
        xy=(0.02, 0.95),
        xycoords="axes fraction",
        fontsize=10,
        fontweight="bold",
        color=mad_color,
        ha="left",
        va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", edgecolor=mad_color, alpha=0.9),
    )
    
    # P-value if available
    if p_value is not None:
        _annotate_pvalue(ax, p_value, x=0.98, y=0.95)
    
    return _save_figure(fig, filepath, dpi)


# ---------------------------------------------------------------------------
# 3. Fixed Ratio Scatter Plot
# ---------------------------------------------------------------------------

def plot_fixed_ratio(
    result: Dict[str, Any],
    output_dir: str = "figures/",
    filename: str = "fixed_ratio_scatter.png",
    dpi: int = 300,
) -> str:
    """Generate a scatter plot with regression line for fixed-ratio detection.
    
    Visualizes the relationship between two numeric columns, annotating R²,
    slope, and whether the ratio appears suspiciously fixed (unnaturally high R²).
    
    Args:
        result: Output dict from fixed-ratio test module, expected keys:
            - x_values (list): Values of the first column.
            - y_values (list): Values of the second column.
            - r_squared (float): R² value of linear fit.
            - slope (float): Slope of regression line.
            - intercept (float): Intercept of regression line.
            - is_fixed (bool): Whether ratio is deemed suspiciously fixed.
            - threshold (float, optional): R² threshold used for detection.
            - x_column (str, optional): Name of x column.
            - y_column (str, optional): Name of y column.
            - p_value (float, optional): P-value for the regression.
        output_dir: Directory to save the figure.
        filename: Output filename.
        dpi: Resolution.
    
    Returns:
        Path to the saved figure file.
    """
    output_path = _ensure_output_dir(output_dir)
    filepath = str(output_path / filename)
    
    # Extract data
    x_vals = np.array(result.get("x_values", result.get("x", [])), dtype=float)
    y_vals = np.array(result.get("y_values", result.get("y", [])), dtype=float)
    r_squared = result.get("r_squared", result.get("r2", 0.0))
    slope = result.get("slope", 0.0)
    intercept = result.get("intercept", 0.0)
    is_fixed = result.get("is_fixed", result.get("fixed", False))
    x_col = result.get("x_column", result.get("x_col", "X"))
    y_col = result.get("y_column", result.get("y_col", "Y"))
    threshold = result.get("threshold", 0.99)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(7, 6))
    
    # Scatter plot
    scatter_color = COLORS["highlight"] if is_fixed else COLORS["scatter"]
    ax.scatter(
        x_vals, y_vals,
        c=scatter_color, alpha=0.5, s=30, edgecolors="white", linewidth=0.3,
        label="数据点 Data points"
    )
    
    # Regression line
    if len(x_vals) > 1:
        x_fit = np.linspace(x_vals.min(), x_vals.max(), 100)
        y_fit = slope * x_fit + intercept
        ax.plot(
            x_fit, y_fit,
            color=COLORS["regression"], linewidth=2, linestyle="-",
            label=f"回归线 y = {slope:.4f}x + {intercept:.4f}"
        )
    
    # Title
    status_str = "⚠️ 比值固定 FIXED" if is_fixed else "✓ 正常 NORMAL"
    title = f"固定比值检测 Fixed Ratio Detection\n{status_str}"
    title_color = COLORS["highlight"] if is_fixed else COLORS["normal"]
    ax.set_title(title, fontsize=13, fontweight="bold", pad=15, color=title_color)
    
    ax.set_xlabel(f"{x_col}", fontsize=11)
    ax.set_ylabel(f"{y_col}", fontsize=11)
    ax.legend(loc="lower right", framealpha=0.9)
    
    # Stats annotation box
    stats_lines = [
        f"R² = {r_squared:.6f}",
        f"Slope = {slope:.4f}",
        f"Intercept = {intercept:.4f}",
        f"Threshold = {threshold}",
        f"判定 Verdict: {'固定 Fixed' if is_fixed else '正常 Normal'}",
    ]
    stats_text = "\n".join(stats_lines)
    
    box_color = "#FFEBEE" if is_fixed else "#E8F5E9"
    border_color = COLORS["highlight"] if is_fixed else COLORS["normal"]
    
    ax.text(
        0.03, 0.97, stats_text,
        transform=ax.transAxes, fontsize=9,
        verticalalignment="top", fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor=box_color, edgecolor=border_color, alpha=0.9),
    )
    
    return _save_figure(fig, filepath, dpi)


# ---------------------------------------------------------------------------
# 4. Decimal Pattern Heatmap
# ---------------------------------------------------------------------------

def plot_decimal_heatmap(
    result: Dict[str, Any],
    output_dir: str = "figures/",
    filename: str = "decimal_pattern_heatmap.png",
    dpi: int = 300,
) -> str:
    """Generate a heatmap showing digit frequency at each decimal position.
    
    Visualizes the distribution of digits (0-9) at each decimal place,
    highlighting positions with anomalously uniform or non-uniform patterns.
    
    Args:
        result: Output dict from decimal pattern test module, expected keys:
            - frequency_matrix (list[list] or dict): Digit frequencies per position.
              Shape: (n_positions, 10) where columns are digits 0-9.
            - positions (list, optional): Labels for decimal positions.
            - anomalous_positions (list, optional): Positions flagged as anomalous.
            - column_name (str, optional): Name of analyzed column.
            - p_values (list, optional): Per-position p-values.
        output_dir: Directory to save the figure.
        filename: Output filename.
        dpi: Resolution.
    
    Returns:
        Path to the saved figure file.
    """
    output_path = _ensure_output_dir(output_dir)
    filepath = str(output_path / filename)
    
    # Extract frequency matrix
    freq_matrix = result.get("frequency_matrix", result.get("matrix", []))
    if isinstance(freq_matrix, dict):
        positions = sorted(freq_matrix.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
        matrix = np.array([freq_matrix[p] for p in positions], dtype=float)
    else:
        matrix = np.array(freq_matrix, dtype=float)
        positions = result.get("positions", [f"Pos {i+1}" for i in range(matrix.shape[0])])
    
    # Normalize rows to proportions
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # Avoid division by zero
    matrix_prop = matrix / row_sums
    
    anomalous = set(result.get("anomalous_positions", result.get("anomalous", [])))
    col_name = result.get("column_name", result.get("column", ""))
    
    # Create figure
    n_positions = matrix_prop.shape[0]
    fig_height = max(4, n_positions * 0.5 + 2)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    
    # Heatmap with diverging colormap centered on 0.1 (uniform expectation)
    vmin = 0.0
    vmax = max(0.25, matrix_prop.max())
    
    # Custom colormap: green (under) -> white (expected=0.1) -> red (over)
    cmap = sns.diverging_palette(145, 10, s=80, l=55, as_cmap=True)
    
    # Plot heatmap with deviation from expected (0.1)
    deviation = matrix_prop - 0.1
    
    sns.heatmap(
        deviation,
        ax=ax,
        cmap=cmap,
        center=0,
        vmin=-0.15,
        vmax=0.15,
        annot=matrix_prop,
        fmt=".3f",
        linewidths=0.5,
        linecolor="white",
        xticklabels=[str(d) for d in range(10)],
        yticklabels=[str(p) for p in positions],
        cbar_kws={"label": "偏差 Deviation from expected (0.1)", "shrink": 0.8},
    )
    
    # Highlight anomalous rows
    for i, pos in enumerate(positions):
        if pos in anomalous or i in anomalous or str(pos) in [str(a) for a in anomalous]:
            ax.add_patch(plt.Rectangle((0, i), 10, 1, fill=False, edgecolor=COLORS["highlight"], linewidth=2.5))
    
    # Title and labels
    title = "小数位数字模式热图 Decimal Pattern Heatmap"
    if col_name:
        title += f"\n[{col_name}]"
    ax.set_title(title, fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("数字 Digit", fontsize=11)
    ax.set_ylabel("小数位置 Decimal Position", fontsize=11)
    
    # Annotation for anomalous positions
    if anomalous:
        ax.text(
            1.02, 0.02,
            f"⚠ 异常位置: {len(anomalous)}",
            transform=ax.transAxes, fontsize=9,
            color=COLORS["highlight"], fontweight="bold",
            va="bottom",
        )
    
    plt.tight_layout()
    return _save_figure(fig, filepath, dpi)


# ---------------------------------------------------------------------------
# 5. Comprehensive Dashboard
# ---------------------------------------------------------------------------

def plot_dashboard(
    report: Dict[str, Any],
    output_dir: str = "figures/",
    filename: str = "comprehensive_dashboard.png",
    dpi: int = 300,
) -> str:
    """Generate a multi-panel comprehensive dashboard combining all tests.
    
    Creates a publication-ready figure with subplots for each statistical test,
    plus an overall risk assessment panel. Suitable for report inclusion.
    
    Args:
        report: Full report dict containing results from all tests, expected keys:
            - last_digit (dict): Last digit test results.
            - benford (dict): Benford's Law test results.
            - fixed_ratio (dict, optional): Fixed ratio test results.
            - decimal_pattern (dict, optional): Decimal pattern test results.
            - risk_score (float): Overall risk score 0-100.
            - summary (dict, optional): Summary statistics.
            - dataset_name (str, optional): Name of the dataset.
        output_dir: Directory to save the figure.
        filename: Output filename.
        dpi: Resolution.
    
    Returns:
        Path to the saved figure file.
    """
    output_path = _ensure_output_dir(output_dir)
    filepath = str(output_path / filename)
    
    # Determine layout based on available tests
    has_last_digit = "last_digit" in report
    has_benford = "benford" in report
    has_fixed_ratio = "fixed_ratio" in report
    has_decimal = "decimal_pattern" in report
    has_risk = "risk_score" in report
    
    # Create figure with GridSpec
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.4, wspace=0.35)
    
    dataset_name = report.get("dataset_name", report.get("name", "Unknown Dataset"))
    fig.suptitle(
        f"学术数据异常检测综合报告 Fraud Detection Dashboard\n{dataset_name}",
        fontsize=15, fontweight="bold", y=0.98,
    )
    
    # Panel 1: Last Digit Distribution (top-left)
    if has_last_digit:
        ax1 = fig.add_subplot(gs[0, 0])
        _draw_last_digit_panel(ax1, report["last_digit"])
    
    # Panel 2: Benford's Law (top-center)
    if has_benford:
        ax2 = fig.add_subplot(gs[0, 1])
        _draw_benford_panel(ax2, report["benford"])
    
    # Panel 3: Risk Score Gauge (top-right)
    if has_risk:
        ax3 = fig.add_subplot(gs[0, 2])
        _draw_risk_gauge_panel(ax3, report["risk_score"])
    
    # Panel 4: Fixed Ratio (middle-left)
    if has_fixed_ratio:
        ax4 = fig.add_subplot(gs[1, 0])
        _draw_fixed_ratio_panel(ax4, report["fixed_ratio"])
    
    # Panel 5: Decimal Pattern (middle-center + right)
    if has_decimal:
        ax5 = fig.add_subplot(gs[1, 1:])
        _draw_decimal_panel(ax5, report["decimal_pattern"])
    
    # Panel 6: Summary table (bottom row)
    ax6 = fig.add_subplot(gs[2, :])
    _draw_summary_panel(ax6, report)
    
    return _save_figure(fig, filepath, dpi)


def _draw_last_digit_panel(ax: plt.Axes, data: Dict):
    """Draw last digit distribution as a mini panel."""
    observed = data.get("observed_freq", data.get("observed", []))
    if isinstance(observed, dict):
        digits = sorted(observed.keys(), key=lambda x: int(x))
        obs_values = np.array([observed[d] for d in digits], dtype=float)
    else:
        obs_values = np.array(observed, dtype=float)
        digits = list(range(len(obs_values)))
    
    if obs_values.sum() > 1.1:
        obs_values = obs_values / obs_values.sum()
    
    n = len(digits)
    expected = 1.0 / n
    
    colors = [COLORS["highlight"] if abs(v - expected) > 0.05 else COLORS["observed"] for v in obs_values]
    ax.bar(range(n), obs_values, color=colors, alpha=0.8, edgecolor="white")
    ax.axhline(expected, color=COLORS["expected"], linestyle="--", linewidth=1)
    ax.set_title("末位数字 Last Digit", fontsize=10, fontweight="bold")
    ax.set_xlabel("Digit", fontsize=8)
    ax.set_ylabel("Freq", fontsize=8)
    ax.set_xticks(range(n))
    ax.set_xticklabels(digits, fontsize=7)
    
    p_val = data.get("p_value", data.get("pvalue", None))
    if p_val is not None:
        color = COLORS["highlight"] if p_val < 0.05 else COLORS["normal"]
        ax.text(0.95, 0.9, f"p={p_val:.3f}", transform=ax.transAxes, fontsize=8, ha="right", color=color, fontweight="bold")


def _draw_benford_panel(ax: plt.Axes, data: Dict):
    """Draw Benford's Law comparison as a mini panel."""
    observed = data.get("observed_freq", data.get("observed", {}))
    if isinstance(observed, (list, np.ndarray)):
        obs_values = np.array(observed, dtype=float)
    else:
        obs_values = np.array([observed.get(str(d), observed.get(d, 0)) for d in range(1, 10)], dtype=float)
    
    if obs_values.sum() > 1.1:
        obs_values = obs_values / obs_values.sum()
    
    benford = np.array([np.log10(1 + 1/d) for d in range(1, 10)])
    x = np.arange(9)
    
    ax.bar(x - 0.15, obs_values, 0.3, label="Obs", color=COLORS["observed"], alpha=0.8)
    ax.bar(x + 0.15, benford, 0.3, label="Benford", color=COLORS["expected"], alpha=0.6)
    ax.set_title("Benford 定律", fontsize=10, fontweight="bold")
    ax.set_xlabel("First Digit", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(range(1, 10), fontsize=7)
    ax.legend(fontsize=7, loc="upper right")
    
    mad = data.get("mad", data.get("MAD", 0))
    color = COLORS["highlight"] if mad > 0.015 else COLORS["normal"]
    ax.text(0.95, 0.9, f"MAD={mad:.4f}", transform=ax.transAxes, fontsize=8, ha="right", color=color, fontweight="bold")


def _draw_risk_gauge_panel(ax: plt.Axes, risk_score: float):
    """Draw a mini risk gauge."""
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-0.3, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    
    # Draw gauge arc segments
    angles = np.linspace(180, 0, 100)
    for i in range(len(angles) - 1):
        frac = i / (len(angles) - 1)
        if frac < 0.25:
            color = COLORS["risk_low"]
        elif frac < 0.5:
            color = COLORS["risk_medium"]
        elif frac < 0.75:
            color = COLORS["risk_high"]
        else:
            color = COLORS["risk_critical"]
        
        theta1 = angles[i + 1]
        theta2 = angles[i]
        wedge = Wedge((0, 0), 1.0, theta1, theta2, width=0.3, facecolor=color, alpha=0.7)
        ax.add_patch(wedge)
    
    # Needle
    needle_angle = 180 - (risk_score / 100) * 180
    needle_rad = np.radians(needle_angle)
    needle_x = 0.75 * np.cos(needle_rad)
    needle_y = 0.75 * np.sin(needle_rad)
    ax.annotate(
        "", xy=(needle_x, needle_y), xytext=(0, 0),
        arrowprops=dict(arrowstyle="-|>", color="#333333", lw=2),
    )
    ax.plot(0, 0, "o", color="#333333", markersize=6)
    
    # Score text
    if risk_score >= 75:
        score_color = COLORS["risk_critical"]
    elif risk_score >= 50:
        score_color = COLORS["risk_high"]
    elif risk_score >= 25:
        score_color = COLORS["risk_medium"]
    else:
        score_color = COLORS["risk_low"]
    
    ax.text(0, -0.2, f"{risk_score:.0f}", fontsize=20, fontweight="bold", ha="center", color=score_color)
    ax.set_title("风险评分 Risk Score", fontsize=10, fontweight="bold", pad=5)


def _draw_fixed_ratio_panel(ax: plt.Axes, data: Dict):
    """Draw fixed ratio scatter as a mini panel."""
    x_vals = np.array(data.get("x_values", data.get("x", [])), dtype=float)
    y_vals = np.array(data.get("y_values", data.get("y", [])), dtype=float)
    r_sq = data.get("r_squared", data.get("r2", 0))
    is_fixed = data.get("is_fixed", data.get("fixed", False))
    
    color = COLORS["highlight"] if is_fixed else COLORS["scatter"]
    if len(x_vals) > 0 and len(y_vals) > 0:
        ax.scatter(x_vals, y_vals, c=color, alpha=0.4, s=15, edgecolors="none")
        
        # Regression line
        if len(x_vals) > 1:
            slope = data.get("slope", 0)
            intercept = data.get("intercept", 0)
            x_fit = np.linspace(x_vals.min(), x_vals.max(), 50)
            ax.plot(x_fit, slope * x_fit + intercept, color=COLORS["regression"], linewidth=1.5)
    
    status = "⚠ FIXED" if is_fixed else "✓ Normal"
    ax.set_title(f"固定比值 {status}", fontsize=10, fontweight="bold", color=color)
    ax.text(0.05, 0.9, f"R²={r_sq:.4f}", transform=ax.transAxes, fontsize=8, fontweight="bold")


def _draw_decimal_panel(ax: plt.Axes, data: Dict):
    """Draw decimal pattern heatmap as a mini panel."""
    freq_matrix = data.get("frequency_matrix", data.get("matrix", []))
    if isinstance(freq_matrix, dict):
        positions = sorted(freq_matrix.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
        matrix = np.array([freq_matrix[p] for p in positions], dtype=float)
    else:
        matrix = np.array(freq_matrix, dtype=float)
        positions = data.get("positions", [f"P{i+1}" for i in range(matrix.shape[0])])
    
    if matrix.size == 0:
        ax.text(0.5, 0.5, "No decimal data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("小数模式 Decimal Pattern", fontsize=10, fontweight="bold")
        return
    
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    matrix_prop = matrix / row_sums
    
    sns.heatmap(
        matrix_prop, ax=ax, cmap="YlOrRd",
        annot=True if matrix_prop.shape[0] <= 5 else False,
        fmt=".2f", linewidths=0.3,
        xticklabels=[str(d) for d in range(10)],
        yticklabels=[str(p) for p in positions],
        cbar_kws={"shrink": 0.7},
    )
    ax.set_title("小数模式 Decimal Pattern", fontsize=10, fontweight="bold")
    ax.set_xlabel("Digit", fontsize=8)
    ax.set_ylabel("Position", fontsize=8)


def _draw_summary_panel(ax: plt.Axes, report: Dict):
    """Draw a summary table panel."""
    ax.axis("off")
    
    # Build summary rows
    rows = []
    headers = ["检测项目 Test", "结果 Result", "指标 Metric", "判定 Verdict"]
    
    if "last_digit" in report:
        ld = report["last_digit"]
        p_val = ld.get("p_value", ld.get("pvalue", "N/A"))
        verdict = "⚠ 异常" if (isinstance(p_val, (int, float)) and p_val < 0.05) else "✓ 正常"
        rows.append(["末位数字 Last Digit", f"χ²={ld.get('chi_square', ld.get('chi2', 'N/A')):.2f}" if isinstance(ld.get('chi_square', ld.get('chi2')), (int, float)) else "N/A", f"p={p_val:.4f}" if isinstance(p_val, (int, float)) else str(p_val), verdict])
    
    if "benford" in report:
        bf = report["benford"]
        mad = bf.get("mad", bf.get("MAD", "N/A"))
        verdict = "⚠ 异常" if (isinstance(mad, (int, float)) and mad > 0.015) else "✓ 正常"
        rows.append(["Benford 定律", f"MAD={mad:.4f}" if isinstance(mad, (int, float)) else str(mad), bf.get("conformity", ""), verdict])
    
    if "fixed_ratio" in report:
        fr = report["fixed_ratio"]
        is_fixed = fr.get("is_fixed", fr.get("fixed", False))
        r2 = fr.get("r_squared", fr.get("r2", "N/A"))
        verdict = "⚠ 固定" if is_fixed else "✓ 正常"
        rows.append(["固定比值 Fixed Ratio", f"R²={r2:.6f}" if isinstance(r2, (int, float)) else str(r2), f"slope={fr.get('slope', 'N/A')}", verdict])
    
    if "decimal_pattern" in report:
        dp = report["decimal_pattern"]
        n_anomalous = len(dp.get("anomalous_positions", dp.get("anomalous", [])))
        verdict = f"⚠ {n_anomalous}处异常" if n_anomalous > 0 else "✓ 正常"
        rows.append(["小数模式 Decimal", f"异常位置: {n_anomalous}", "", verdict])
    
    if rows:
        table = ax.table(
            cellText=rows,
            colLabels=headers,
            cellLoc="center",
            loc="center",
            colWidths=[0.25, 0.25, 0.25, 0.25],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.0, 1.5)
        
        # Style header
        for j in range(len(headers)):
            table[0, j].set_facecolor("#1976D2")
            table[0, j].set_text_props(color="white", fontweight="bold")
        
        # Color verdict cells (last column = index 3)
        n_cols = len(headers)
        for i, row in enumerate(rows):
            if "⚠" in row[-1]:
                table[i + 1, n_cols - 1].set_facecolor("#FFEBEE")
            else:
                table[i + 1, n_cols - 1].set_facecolor("#E8F5E9")
    
    risk = report.get("risk_score", None)
    if risk is not None:
        ax.set_title(
            f"综合评估 Overall Assessment | 风险评分 Risk Score: {risk:.0f}/100",
            fontsize=11, fontweight="bold", pad=10,
        )


# ---------------------------------------------------------------------------
# 6. Risk Score Gauge
# ---------------------------------------------------------------------------

def plot_risk_gauge(
    risk_score: float,
    output_dir: str = "figures/",
    filename: str = "risk_score_gauge.png",
    dpi: int = 300,
    label: str = "",
) -> str:
    """Generate a semi-circular gauge showing overall risk score (0-100).
    
    Creates a visually informative gauge with color gradient from green (low risk)
    through yellow/orange to red (high risk), with a needle indicating the score.
    
    Args:
        risk_score: Overall risk score between 0 and 100.
        output_dir: Directory to save the figure.
        filename: Output filename.
        dpi: Resolution.
        label: Optional label/dataset name to display.
    
    Returns:
        Path to the saved figure file.
    """
    output_path = _ensure_output_dir(output_dir)
    filepath = str(output_path / filename)
    
    risk_score = float(np.clip(risk_score, 0, 100))
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-0.5, 1.5)
    ax.set_aspect("equal")
    ax.axis("off")
    
    # Draw gauge background arc with color gradient
    n_segments = 200
    angles = np.linspace(180, 0, n_segments + 1)
    
    for i in range(n_segments):
        frac = i / n_segments
        # Color interpolation: green -> yellow -> orange -> red
        if frac < 0.25:
            r, g, b = 0.30, 0.69, 0.31  # Green
            f = frac / 0.25
            r = r + f * (1.0 - r)
            g = g + f * (0.76 - g)
            b = b + f * (0.03 - b)
        elif frac < 0.5:
            f = (frac - 0.25) / 0.25
            r, g, b = 1.0, 0.76 - f * 0.13, 0.03
        elif frac < 0.75:
            f = (frac - 0.5) / 0.25
            r, g, b = 1.0 - f * 0.04, 0.63 - f * 0.29, 0.03 + f * 0.10
        else:
            f = (frac - 0.75) / 0.25
            r, g, b = 0.96 - f * 0.13, 0.34 - f * 0.15, 0.13 + f * 0.06
        
        theta1 = angles[i + 1]
        theta2 = angles[i]
        wedge = Wedge((0, 0), 1.2, theta1, theta2, width=0.35, facecolor=(r, g, b), alpha=0.85)
        ax.add_patch(wedge)
    
    # Inner white circle for clean look
    inner_circle = plt.Circle((0, 0), 0.82, color="white", zorder=2)
    ax.add_patch(inner_circle)
    
    # Tick marks and labels
    tick_values = [0, 25, 50, 75, 100]
    tick_labels = ["0\n安全", "25\n低风险", "50\n中风险", "75\n高风险", "100\n极高"]
    for val, lbl in zip(tick_values, tick_labels):
        angle_rad = np.radians(180 - val / 100 * 180)
        # Outer tick
        x_outer = 1.28 * np.cos(angle_rad)
        y_outer = 1.28 * np.sin(angle_rad)
        x_inner = 1.18 * np.cos(angle_rad)
        y_inner = 1.18 * np.sin(angle_rad)
        ax.plot([x_inner, x_outer], [y_inner, y_outer], color="#333", linewidth=1.5)
        # Label
        x_label = 1.42 * np.cos(angle_rad)
        y_label = 1.42 * np.sin(angle_rad)
        ax.text(x_label, y_label, lbl, ha="center", va="center", fontsize=7, color="#555")
    
    # Needle
    needle_angle = np.radians(180 - (risk_score / 100) * 180)
    needle_length = 0.78
    needle_x = needle_length * np.cos(needle_angle)
    needle_y = needle_length * np.sin(needle_angle)
    
    # Needle triangle (wider base)
    base_angle1 = needle_angle + np.pi / 2
    base_angle2 = needle_angle - np.pi / 2
    base_r = 0.04
    triangle = plt.Polygon([
        [needle_x, needle_y],
        [base_r * np.cos(base_angle1), base_r * np.sin(base_angle1)],
        [base_r * np.cos(base_angle2), base_r * np.sin(base_angle2)],
    ], closed=True, facecolor="#333333", zorder=5)
    ax.add_patch(triangle)
    
    # Center dot
    center_circle = plt.Circle((0, 0), 0.06, color="#333333", zorder=6)
    ax.add_patch(center_circle)
    
    # Score display
    if risk_score >= 75:
        score_color = COLORS["risk_critical"]
        risk_label = "极高风险 Critical Risk"
    elif risk_score >= 50:
        score_color = COLORS["risk_high"]
        risk_label = "高风险 High Risk"
    elif risk_score >= 25:
        score_color = COLORS["risk_medium"]
        risk_label = "中等风险 Medium Risk"
    else:
        score_color = COLORS["risk_low"]
        risk_label = "低风险 Low Risk"
    
    ax.text(0, -0.15, f"{risk_score:.0f}", fontsize=32, fontweight="bold",
            ha="center", va="center", color=score_color, zorder=7)
    ax.text(0, -0.35, risk_label, fontsize=11, ha="center", va="center",
            color=score_color, fontweight="bold")
    
    # Title
    title = "学术数据风险评分 Academic Data Risk Score"
    if label:
        title += f"\n{label}"
    ax.set_title(title, fontsize=13, fontweight="bold", pad=20, y=1.0)
    
    return _save_figure(fig, filepath, dpi)


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def generate_all_figures(report: Dict[str, Any], output_dir: str = "figures/") -> Dict[str, str]:
    """Generate all available figures from a complete report.
    
    Args:
        report: Full report dict containing results from all tests.
        output_dir: Directory to save all figures.
    
    Returns:
        Dictionary mapping figure type to saved file path.
    """
    figures = {}
    
    if "last_digit" in report:
        try:
            path = plot_last_digit(report["last_digit"], output_dir=output_dir)
            figures["last_digit"] = path
            print(f"  ✓ Last digit plot: {path}")
        except Exception as e:
            print(f"  ✗ Last digit plot failed: {e}", file=sys.stderr)
    
    if "benford" in report:
        try:
            path = plot_benford(report["benford"], output_dir=output_dir)
            figures["benford"] = path
            print(f"  ✓ Benford plot: {path}")
        except Exception as e:
            print(f"  ✗ Benford plot failed: {e}", file=sys.stderr)
    
    if "fixed_ratio" in report:
        try:
            path = plot_fixed_ratio(report["fixed_ratio"], output_dir=output_dir)
            figures["fixed_ratio"] = path
            print(f"  ✓ Fixed ratio plot: {path}")
        except Exception as e:
            print(f"  ✗ Fixed ratio plot failed: {e}", file=sys.stderr)
    
    if "decimal_pattern" in report:
        try:
            path = plot_decimal_heatmap(report["decimal_pattern"], output_dir=output_dir)
            figures["decimal_heatmap"] = path
            print(f"  ✓ Decimal heatmap: {path}")
        except Exception as e:
            print(f"  ✗ Decimal heatmap failed: {e}", file=sys.stderr)
    
    if "risk_score" in report:
        try:
            label = report.get("dataset_name", "")
            path = plot_risk_gauge(report["risk_score"], output_dir=output_dir, label=label)
            figures["risk_gauge"] = path
            print(f"  ✓ Risk gauge: {path}")
        except Exception as e:
            print(f"  ✗ Risk gauge failed: {e}", file=sys.stderr)
    
    # Comprehensive dashboard (needs at least 2 test results)
    n_tests = sum(1 for k in ["last_digit", "benford", "fixed_ratio", "decimal_pattern"] if k in report)
    if n_tests >= 2:
        try:
            path = plot_dashboard(report, output_dir=output_dir)
            figures["dashboard"] = path
            print(f"  ✓ Dashboard: {path}")
        except Exception as e:
            print(f"  ✗ Dashboard failed: {e}", file=sys.stderr)
    
    return figures


def main():
    """CLI entry point for batch figure generation."""
    parser = argparse.ArgumentParser(
        description="Generate publication-quality figures for academic fraud detection reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 visualization.py --input report.json --output figures/
  python3 visualization.py --input report.json --output figures/ --dpi 600
  python3 visualization.py --input report.json --type benford --output figures/
        """,
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to JSON report file (output from fraud detection pipeline)."
    )
    parser.add_argument(
        "--output", "-o", default="figures/",
        help="Output directory for generated figures (default: figures/)."
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="Figure resolution in DPI (default: 300)."
    )
    parser.add_argument(
        "--type", "-t", choices=["all", "last_digit", "benford", "fixed_ratio", "decimal", "gauge", "dashboard"],
        default="all",
        help="Type of figure to generate (default: all)."
    )
    
    args = parser.parse_args()
    
    # Load report
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    with open(input_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    print(f"📊 Generating figures from: {args.input}")
    print(f"   Output directory: {args.output}")
    print(f"   DPI: {args.dpi}")
    print(f"   Type: {args.type}")
    print("-" * 50)
    
    # Update global DPI
    plt.rcParams["savefig.dpi"] = args.dpi
    
    if args.type == "all":
        figures = generate_all_figures(report, output_dir=args.output)
    elif args.type == "last_digit" and "last_digit" in report:
        path = plot_last_digit(report["last_digit"], output_dir=args.output, dpi=args.dpi)
        figures = {"last_digit": path}
        print(f"  ✓ Last digit plot: {path}")
    elif args.type == "benford" and "benford" in report:
        path = plot_benford(report["benford"], output_dir=args.output, dpi=args.dpi)
        figures = {"benford": path}
        print(f"  ✓ Benford plot: {path}")
    elif args.type == "fixed_ratio" and "fixed_ratio" in report:
        path = plot_fixed_ratio(report["fixed_ratio"], output_dir=args.output, dpi=args.dpi)
        figures = {"fixed_ratio": path}
        print(f"  ✓ Fixed ratio plot: {path}")
    elif args.type == "decimal" and "decimal_pattern" in report:
        path = plot_decimal_heatmap(report["decimal_pattern"], output_dir=args.output, dpi=args.dpi)
        figures = {"decimal_heatmap": path}
        print(f"  ✓ Decimal heatmap: {path}")
    elif args.type == "gauge" and "risk_score" in report:
        label = report.get("dataset_name", "")
        path = plot_risk_gauge(report["risk_score"], output_dir=args.output, dpi=args.dpi, label=label)
        figures = {"risk_gauge": path}
        print(f"  ✓ Risk gauge: {path}")
    elif args.type == "dashboard":
        path = plot_dashboard(report, output_dir=args.output, dpi=args.dpi)
        figures = {"dashboard": path}
        print(f"  ✓ Dashboard: {path}")
    else:
        print(f"Warning: No data available for type '{args.type}' in the report.", file=sys.stderr)
        figures = {}
    
    print("-" * 50)
    print(f"✅ Generated {len(figures)} figure(s).")
    
    if figures:
        # Save figure manifest
        manifest_path = Path(args.output) / "figures_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(figures, f, indent=2, ensure_ascii=False)
        print(f"📋 Manifest saved: {manifest_path}")


if __name__ == "__main__":
    main()
