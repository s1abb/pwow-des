"""Write fitted parameters to fitting/output/fitted_config.py."""

from __future__ import annotations

import pprint
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_OUTPUT_DIR = Path(__file__).parents[2] / "output"
_OUTPUT_FILE = _OUTPUT_DIR / "fitted_config.py"


def _build_entry(
    row: pd.Series, dur_df: pd.DataFrame, model: str, order_type_group: str, activity_group: str
) -> dict:
    """Build a single failure entry from fitted rows."""
    entry: dict = {
        "shape": round(float(row["shape"]), 4),
        "scale": round(float(row["scale_op"]), 1),
        "n": int(row["n"]),
    }
    mask = (
        (dur_df["model"] == model)
        & (dur_df["order_type_group"] == order_type_group)
        & (dur_df["activity_group"] == activity_group)
    )
    dur_rows = dur_df[mask]
    if not dur_rows.empty:
        dr = dur_rows.iloc[0]
        entry["repair_mean"] = round(float(dr["dur_mean"]), 2)
        entry["repair_sd"] = round(float(dr["dur_sd"]), 2)
        entry["dur_n"] = int(dr["n"])
    return entry


def export_config(
    weibull_df: pd.DataFrame,
    duration_df: pd.DataFrame,
    util_factor: float = 1.0,
    output_path: str | Path | None = None,
) -> Path:
    """Write ``fitted_config.py`` and return its path.

    Produces a single nested dict
    ``PREMATURE_FAILURE_FITTED[model][order_type_group][activity_group]``.
    Missing combinations are silently omitted.
    """
    out = Path(output_path) if output_path is not None else _OUTPUT_FILE
    out.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_n = int(weibull_df["n"].sum()) if not weibull_df.empty else 0

    if not weibull_df.empty:
        model_ns = weibull_df.groupby("model")["n"].sum().to_dict()
        sample_lines = "  " + "\n  ".join(
            f"{m}: {n} IFT samples" for m, n in sorted(model_ns.items())
        )
    else:
        sample_lines = "  (none)"

    # Build nested dict: model → order_type_group → activity_group → entry
    pf: dict[str, dict] = {}
    for _, row in weibull_df.iterrows():
        model = row["model"]
        otg = row["order_type_group"]
        ag = row["activity_group"]
        pf.setdefault(model, {}).setdefault(otg, {})[ag] = _build_entry(
            row, duration_df, model, otg, ag
        )

    lines = [
        f'"""Fitted simulation parameters \u2014 generated {now}',
        f"",
        f"Weibull IFT samples by model:",
        sample_lines,
        f"",
        f"Utilisation factor applied: {util_factor}",
        f"",
        f"Structure: PREMATURE_FAILURE_FITTED[model][order_type_group][activity_group]",
        f"  order_type_group: 'corrective' | 'preventive'",
        f"",
        f"Missing combinations are absent (simulation falls back to hand-coded defaults).",
        f'"""',
        f"",
        f"PREMATURE_FAILURE_FITTED = \\",
    ]
    lines.append(pprint.pformat(pf, width=88))
    lines.append("")

    out.write_text("\n".join(lines))
    return out
