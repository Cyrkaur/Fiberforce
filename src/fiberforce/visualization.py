"""
Visualization module for FiberForce sensitivity and comparison results.

Provides real visual output for analysis features:
- plot_sensitivity(): bar/line charts for sensitivity sweeps
- plot_comparison(): side-by-side or delta visualization for compare results
- Rich table + ASCII sparkline / bar chart fallback when matplotlib is unavailable
- Headless / CI / no-display environment support (always safe; saves to file or ASCII only)

Design goals:
- matplotlib is OPTIONAL (powerful interactive/PNG/PDF output when present)
- Graceful degradation to rich (tables) + pure-ASCII charts (sparklines, bars) otherwise
- Works directly on SensitivityResult (and ComparisonResult)
- Also accepts simple dicts / raw compare outputs from CLI or library for convenience
- Clean integration point for SensitivityAnalyzer, AnalysisService, and the fiberforce CLI

Usage (library):
    from fiberforce.calculations import SensitivityAnalyzer
    from fiberforce.visualization import plot_sensitivity, ascii_sparkline

    result = analyzer.run(...)
    plot_sensitivity(result, save_path="sweep.png")   # or just plot_sensitivity(result)

CLI examples (after wiring):
    fiberforce sensitivity bench --variable load_kg --start 70 --end 120 --step 10 --plot
    fiberforce sensitivity squat --variable load_kg ... --save-plot sweep.png
    fiberforce compare squat --a high_bar --b low_bar --plot

When matplotlib is installed:
    - Uses a clean line+markers chart (or bars) with labels
    - Auto-selects Agg backend in headless environments
    - Respects save_path and show flags

Fallback (no matplotlib or ascii_only=True):
    - Prints (or returns) a rich table when rich is available
    - Always provides an ASCII sparkline + simple proportional bar chart
    - Works in any terminal, including dumb/CI environments
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional, Union

# --- Optional rich (used for beautiful tables in fallback path) ---
try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
    _console = Console()
except Exception:
    RICH_AVAILABLE = False
    _console = None  # type: ignore

# --- Optional matplotlib (the "real" visualization path) ---
try:
    import matplotlib

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    matplotlib = None  # type: ignore


from fiberforce.calculations.sensitivity import SensitivityResult


# -------------------------------------------------------------------
# Comparison result (for compare command + viz)
# -------------------------------------------------------------------
@dataclass
class ComparisonResult:
    """Structured result for a two-way comparison (used by CLI compare + visualization)."""
    lift: str
    config_a: str
    config_b: str
    load_kg: float
    target: str
    force_a_n: float
    force_b_n: float
    confidence_a: str = ""
    confidence_b: str = ""
    notes: str = ""

    def to_table_rows(self) -> list[dict]:
        diff = self.force_b_n - self.force_a_n
        pct = (diff / self.force_a_n * 100) if self.force_a_n > 0 else 0.0
        return [
            {
                "Config": self.config_a,
                "Peak Force (N)": round(self.force_a_n, 1),
                "Confidence": self.confidence_a or "-",
            },
            {
                "Config": self.config_b,
                "Peak Force (N)": round(self.force_b_n, 1),
                "Confidence": self.confidence_b or "-",
            },
            {
                "Config": "Δ (B - A)",
                "Peak Force (N)": f"{diff:+.1f} ({pct:+.1f}%)",
                "Confidence": "",
            },
        ]

    def __str__(self) -> str:
        return (
            f"Comparison({self.lift} {self.config_a} vs {self.config_b} @ {self.load_kg}kg): "
            f"{self.force_a_n:.1f}N vs {self.force_b_n:.1f}N"
        )


# -------------------------------------------------------------------
# Environment detection
# -------------------------------------------------------------------
def is_headless() -> bool:
    """Detect environments where interactive display is impossible or undesirable."""
    if os.environ.get("CI"):
        return True
    if os.environ.get("MPLBACKEND") == "Agg":
        return True
    # Unix without DISPLAY (ssh, containers, many CI). On Windows / macOS GUI this is often None anyway.
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        return True
    return False


def _prepare_matplotlib_backend():
    """Switch to Agg (non-interactive) when headless or when only saving."""
    if not MATPLOTLIB_AVAILABLE:
        return
    if is_headless():
        matplotlib.use("Agg", force=True)


# -------------------------------------------------------------------
# ASCII fallback primitives (always available)
# -------------------------------------------------------------------
def ascii_sparkline(values: list[float], width: int = 36, chars: str = "▁▂▃▄▅▆▇█") -> str:
    """Generate a compact Unicode sparkline for a sequence of numeric values."""
    if not values:
        return ""
    if len(values) == 1:
        return chars[-1] * min(width, 8)

    vmin, vmax = min(values), max(values)
    if vmax <= vmin:
        return chars[len(chars) // 2] * min(width, len(values))

    out = []
    n = len(chars) - 1
    for v in values:
        frac = (v - vmin) / (vmax - vmin)
        idx = int(frac * n)
        out.append(chars[max(0, min(n, idx))])

    # If more points than width, subsample (simple stride)
    if len(out) > width:
        stride = len(out) / float(width)
        sampled = [out[int(i * stride)] for i in range(width)]
        return "".join(sampled)
    return "".join(out)


def ascii_bars(
    labels: list[str],
    values: list[float],
    width: int = 42,
    unit: str = "N",
    max_bar_width: int = 28,
) -> str:
    """Simple ASCII horizontal proportional bar chart. Pure text, no external deps."""
    if not values:
        return "(no data)"

    vmin = min(v for v in values if v >= 0) if any(v >= 0 for v in values) else 0
    vmax = max(values) if values else 1.0
    if vmax <= vmin:
        vmax = vmin + 1.0

    lines = []
    for label, val in zip(labels, values):
        frac = (val - vmin) / (vmax - vmin) if vmax > vmin else 0.5
        bar_len = int(frac * max_bar_width)
        bar = "█" * bar_len + " " * (max_bar_width - bar_len)
        lines.append(f"  {label:14s} │{bar}│ {val:7.1f} {unit}")

    # Add a tiny scale footer
    scale = f"  {'':14s} └{'─' * max_bar_width}┘  range: {vmin:.1f}–{vmax:.1f} {unit}"
    return "\n".join(lines + [scale])


def _rich_print_table(rows: list[dict], title: str = "") -> None:
    """Best-effort rich table. Falls back to plain text if rich missing."""
    if not rows:
        print("(no rows)")
        return

    if RICH_AVAILABLE and _console is not None:
        table = Table(title=title or None, show_header=True, header_style="bold cyan")
        # Use keys from first row as columns
        for key in rows[0].keys():
            table.add_column(str(key))
        for row in rows:
            table.add_row(*[str(v) for v in row.values()])
        _console.print(table)
    else:
        # Very basic plain-text table fallback
        if title:
            print(f"\n{title}")
        keys = list(rows[0].keys())
        header = " | ".join(keys)
        print(header)
        print("-" * len(header))
        for r in rows:
            print(" | ".join(str(v) for v in r.values()))
        print()


# -------------------------------------------------------------------
# Core plotting / rendering functions
# -------------------------------------------------------------------
def plot_sensitivity(
    result: SensitivityResult,
    *,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    show: bool = True,
    ascii_only: bool = False,
    width: int = 50,
) -> Optional[str]:
    """
    Visualize a SensitivityResult as a chart (matplotlib line/bar when available)
    with accompanying table + ASCII fallback.

    Returns:
        ASCII art string when falling back or when ascii_only=True.
        None when a matplotlib figure was created (user manages plt.show / save).
    """
    if result is None or not result.points:
        msg = "No sensitivity data to visualize."
        print(msg)
        return msg

    variable = result.variable_name
    values = [p.variable_value for p in result.points]
    forces = [p.peak_force_n for p in result.points]
    confs = [p.confidence_level for p in result.points]

    effective_title = title or f"Sensitivity: {variable} → Peak Force ({result.target_region})"

    # Always produce a compact table + ASCII chart for immediate usefulness
    table_rows = result.to_table_rows()
    ascii_chart = ascii_bars(
        labels=[str(v) for v in values],
        values=forces,
        width=width,
        unit="N",
    )
    spark = ascii_sparkline(forces, width=min(40, len(forces) * 3))

    ascii_output = (
        f"\n{effective_title}\n\n"
        + "ASCII Sparkline: " + spark + "\n\n"
        + ascii_chart + "\n"
    )

    # Rich table (or plain)
    _rich_print_table(table_rows, title=effective_title)

    # --- Matplotlib path (preferred when available and not forced to ASCII) ---
    if MATPLOTLIB_AVAILABLE and not ascii_only:
        _prepare_matplotlib_backend()
        import matplotlib.pyplot as plt  # local import after backend switch

        fig, ax = plt.subplots(figsize=(9, 5))

        # Choose line chart for sweeps (connects the dots nicely); bar also works
        # Use line + markers — classic sensitivity sweep look
        ax.plot(values, forces, marker="o", linewidth=2.0, markersize=7, label="Peak Force")
        ax.fill_between(values, forces, alpha=0.15)

        ax.set_xlabel(variable)
        ax.set_ylabel("Peak Force (N)")
        ax.set_title(effective_title)
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.legend(loc="best")

        # Annotate a couple of points with confidence (keeps it light)
        for i, (x, y, c) in enumerate(zip(values, forces, confs)):
            if i % max(1, len(values) // 4) == 0:  # sparse labels
                short_c = c.split()[0] if c else ""
                ax.annotate(f"{y:.0f}N\n{short_c}", xy=(x, y), xytext=(4, 8),
                            textcoords="offset points", fontsize=8, alpha=0.8)

        fig.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"[visualization] Saved plot to {save_path}")

        if show and not is_headless() and not save_path:
            plt.show()
        elif show and (is_headless() or save_path):
            # In headless, we already saved (or user didn't want display)
            pass

        # Do not close automatically — let caller decide
        return None

    # Fallback path: print the ASCII chart we already built
    print(ascii_output)
    if save_path:
        # Even in pure ASCII mode we can write a .txt sidecar
        try:
            with open(save_path, "w") as f:
                f.write(ascii_output + "\n" + "\n".join(str(r) for r in table_rows))
            print(f"[visualization] Saved ASCII report to {save_path}")
        except Exception as e:
            print(f"[visualization] Failed to write ASCII report: {e}")

    return ascii_output


def plot_comparison(
    result: Union[ComparisonResult, dict, Any],
    *,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    show: bool = True,
    ascii_only: bool = False,
) -> Optional[str]:
    """
    Visualize a comparison (two configurations).

    Accepts:
      - ComparisonResult (preferred)
      - dict with keys: 'config_a', 'config_b', 'force_a_n', 'force_b_n', ...
      - Any object with the same attributes (duck typing)

    Renders side-by-side ASCII bars + delta callout. Matplotlib grouped bars when possible.
    """
    # Normalize input
    if isinstance(result, ComparisonResult):
        comp = result
    elif isinstance(result, dict):
        comp = ComparisonResult(
            lift=result.get("lift", "unknown"),
            config_a=result.get("config_a", "A"),
            config_b=result.get("config_b", "B"),
            load_kg=float(result.get("load_kg", 0)),
            target=result.get("target", "target"),
            force_a_n=float(result.get("force_a_n", result.get("a", 0))),
            force_b_n=float(result.get("force_b_n", result.get("b", 0))),
            confidence_a=result.get("confidence_a", ""),
            confidence_b=result.get("confidence_b", ""),
        )
    else:
        # Duck-type
        comp = ComparisonResult(
            lift=getattr(result, "lift", "unknown"),
            config_a=getattr(result, "config_a", "A"),
            config_b=getattr(result, "config_b", "B"),
            load_kg=getattr(result, "load_kg", 0.0),
            target=getattr(result, "target", "target"),
            force_a_n=getattr(result, "force_a_n", getattr(result, "a", 0.0)),
            force_b_n=getattr(result, "force_b_n", getattr(result, "b", 0.0)),
            confidence_a=getattr(result, "confidence_a", ""),
            confidence_b=getattr(result, "confidence_b", ""),
        )

    effective_title = title or f"Compare: {comp.config_a} vs {comp.config_b} ({comp.lift}) @ {comp.load_kg} kg"

    # Table
    rows = comp.to_table_rows()
    _rich_print_table(rows, title=effective_title)

    # ASCII bars for the two values
    labels = [comp.config_a, comp.config_b]
    vals = [comp.force_a_n, comp.force_b_n]
    ascii_chart = ascii_bars(labels, vals, width=44, unit="N", max_bar_width=24)

    diff = comp.force_b_n - comp.force_a_n
    pct = (diff / comp.force_a_n * 100) if comp.force_a_n > 0 else 0
    delta_line = f"Δ = {diff:+.1f} N  ({pct:+.1f}%)  — {'higher' if diff > 0 else 'lower' if diff < 0 else 'equal'} in B"

    ascii_output = f"\n{effective_title}\n\n{ascii_chart}\n{delta_line}\n"

    # Matplotlib grouped bar (very simple two-bar chart)
    if MATPLOTLIB_AVAILABLE and not ascii_only:
        _prepare_matplotlib_backend()
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 4.5))
        x = [0, 1]
        bars = ax.bar(x, vals, color=["#2E86AB", "#A23B72"], width=0.55, edgecolor="black", linewidth=0.8)

        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("Peak Force (N)")
        ax.set_title(effective_title)
        ax.grid(True, axis="y", alpha=0.25, linestyle="--")

        # Value labels on bars
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(vals) * 0.02,
                    f"{v:.1f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

        # Add delta annotation
        ax.annotate(delta_line, xy=(0.5, max(vals) * 0.92), xycoords="data",
                    ha="center", fontsize=9, style="italic")

        fig.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"[visualization] Saved comparison plot to {save_path}")

        if show and not is_headless() and not save_path:
            plt.show()

        return None

    # ASCII fallback
    print(ascii_output)
    if save_path:
        try:
            with open(save_path, "w") as f:
                f.write(ascii_output)
            print(f"[visualization] Saved ASCII comparison to {save_path}")
        except Exception as e:
            print(f"[visualization] ASCII write failed: {e}")

    return ascii_output


def visualize(
    obj: Any,
    *,
    kind: Optional[str] = None,
    **kwargs,
) -> Optional[str]:
    """
    Universal entry point. Dispatches to the appropriate plot_* function.

    kind: "sensitivity", "compare", or None (auto-detect from object type)
    """
    if kind == "sensitivity" or isinstance(obj, SensitivityResult):
        return plot_sensitivity(obj, **kwargs)
    if kind == "compare" or isinstance(obj, ComparisonResult) or (
        isinstance(obj, dict) and "config_a" in obj and "config_b" in obj
    ):
        return plot_comparison(obj, **kwargs)

    # Last-ditch: try sensitivity then comparison
    try:
        return plot_sensitivity(obj, **kwargs)
    except Exception:
        return plot_comparison(obj, **kwargs)


# -------------------------------------------------------------------
# Multi-position (ROM curve) visualization — Phase 2c addition
# -------------------------------------------------------------------
def plot_multi_position(
    results: list,
    positions: Optional[list[str]] = None,
    *,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    show: bool = True,
    ascii_only: bool = False,
    width: int = 48,
) -> Optional[str]:
    """
    Visualize multi-position analysis results as curves/tables (force + MA across discrete ROM positions).

    Accepts list of AnalysisResult (from analyze_multi_position) or compatible objects.
    Uses duck-typing on .position_description + .results[0].* for robustness (no hard dep on service at import).

    Always renders:
      - Per-position table (Position | Force (N) | MA (cm) | Confidence)
      - Summary stats (count, avg, range, deltas)
      - ASCII bars + sparkline for force curve
      - ASCII bars for MA curve (if MA data present)

    When matplotlib available and not ascii_only: dual-curve matplotlib plot (force + MA lines) with categorical x labels.

    Returns ASCII string (for fallback / ascii_only) or None (matplotlib path).
    """
    if not results:
        msg = "No multi-position results to visualize."
        print(msg)
        return msg

    # Extract data via duck-typing (works with AnalysisResult and plain dicts)
    labels: list[str] = []
    forces: list[float] = []
    mas: list[float] = []
    confs: list[str] = []
    notes: list[str] = []

    pos_list = positions or []
    for i, res in enumerate(results):
        # Position label
        if i < len(pos_list) and pos_list[i]:
            pos_label = str(pos_list[i])
        else:
            pos_label = getattr(res, "position_description", None) or f"pos{i}"
        labels.append(pos_label)

        # Primary force/MA (first result entry; CLI multi-pos uses single-target)
        force = 0.0
        ma = 0.0
        conf = ""
        note = ""
        rlist = getattr(res, "results", None) or []
        if rlist:
            primary = rlist[0]
            force = float(getattr(primary, "peak_force_newtons", 0.0) or 0.0)
            ma = float(getattr(primary, "moment_arm_used_cm", 0.0) or 0.0)
            conf = str(getattr(primary, "confidence_level", "") or "")
            note = str(getattr(primary, "notes", "") or "")[:80]
        forces.append(force)
        mas.append(ma)
        confs.append(conf)
        notes.append(note)

    effective_title = title or "Multi-Position Analysis: Peak Force & Moment Arm across ROM"

    # --- Build per-position table rows ---
    table_rows = []
    for lab, f, m, c in zip(labels, forces, mas, confs):
        table_rows.append({
            "Position": lab,
            "Peak Force (N)": round(f, 1),
            "MA (cm)": round(m, 2) if m else "-",
            "Confidence": c or "-",
        })
    _rich_print_table(table_rows, title=effective_title)

    # --- Summary stats ---
    n = len(forces)
    if n > 0:
        fmin, fmax = min(forces), max(forces)
        favg = sum(forces) / n
        deltas = [forces[i] - forces[i-1] for i in range(1, n)] if n > 1 else []
        max_delta = max(deltas) if deltas else 0.0
        min_delta = min(deltas) if deltas else 0.0
        summary_rows = [
            {"Metric": "Positions", "Value": str(n)},
            {"Metric": "Avg Peak Force", "Value": f"{favg:.1f} N"},
            {"Metric": "Range (min–max)", "Value": f"{fmin:.1f} – {fmax:.1f} N"},
            {"Metric": "Delta range", "Value": f"{min_delta:+.1f} … {max_delta:+.1f} N"},
        ]
        _rich_print_table(summary_rows, title="Summary across positions")
    else:
        summary_rows = []

    # --- ASCII curves (always) ---
    force_bars = ascii_bars(labels, forces, width=width, unit="N", max_bar_width=26)
    ma_bars = ascii_bars(labels, mas, width=width, unit="cm", max_bar_width=26) if any(mas) else "(no MA data)"

    spark_force = ascii_sparkline(forces, width=min(40, n * 4))
    spark_ma = ascii_sparkline(mas, width=min(40, n * 4)) if any(mas) else ""

    ascii_output = (
        f"\n{effective_title}\n\n"
        f"Force curve (ASCII sparkline): {spark_force}\n"
        + force_bars + "\n\n"
        + ("MA curve (ASCII sparkline): " + spark_ma + "\n" + ma_bars + "\n" if any(mas) else "")
    )

    # --- Matplotlib curves (force + MA on shared x) ---
    if MATPLOTLIB_AVAILABLE and not ascii_only:
        _prepare_matplotlib_backend()
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)

        x = list(range(len(labels)))
        ax1.plot(x, forces, marker="o", linewidth=2.2, markersize=8, label="Peak Force (N)", color="#1f77b4")
        ax1.fill_between(x, forces, alpha=0.15, color="#1f77b4")
        ax1.set_ylabel("Peak Force (N)")
        ax1.set_title(effective_title)
        ax1.grid(True, alpha=0.3, linestyle="--")
        ax1.legend(loc="best")

        if any(mas):
            ax2.plot(x, mas, marker="s", linewidth=2.0, markersize=7, label="Moment Arm (cm)", color="#ff7f0e")
            ax2.fill_between(x, mas, alpha=0.12, color="#ff7f0e")
            ax2.set_ylabel("Moment Arm (cm)")
            ax2.grid(True, alpha=0.3, linestyle="--")
            ax2.legend(loc="best")
        else:
            ax2.text(0.5, 0.5, "(No MA data available)", ha="center", va="center", transform=ax2.transAxes, fontsize=10, style="italic")
            ax2.set_ylabel("Moment Arm (cm)")

        ax2.set_xlabel("Position")
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=15 if len(labels) > 4 else 0)

        fig.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"[visualization] Saved multi-position plot to {save_path}")

        if show and not is_headless() and not save_path:
            plt.show()
        elif show and (is_headless() or save_path):
            pass

        return None

    # ASCII fallback path
    print(ascii_output)
    if save_path:
        try:
            with open(save_path, "w") as f:
                f.write(ascii_output + "\n")
                # also dump table data
                for row in table_rows + summary_rows:
                    f.write(str(row) + "\n")
            print(f"[visualization] Saved multi-position ASCII report to {save_path}")
        except Exception as e:
            print(f"[visualization] ASCII multi-pos write failed: {e}")

    return ascii_output


# -------------------------------------------------------------------
# Convenience re-exports and small helpers
# -------------------------------------------------------------------
__all__ = [
    "plot_sensitivity",
    "plot_comparison",
    "plot_multi_position",
    "visualize",
    "ascii_sparkline",
    "ascii_bars",
    "is_headless",
    "ComparisonResult",
    "MATPLOTLIB_AVAILABLE",
    "RICH_AVAILABLE",
]
