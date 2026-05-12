"""CLI entry point: python -m fitting"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .load import load_work_orders
from .ift import compute_ifts
from .weibull_fit import fit_weibull
from .duration_fit import fit_durations
from .export_config import export_config


def main(data_path: str | Path | None = None) -> None:
    print("Loading work orders…")
    df = load_work_orders(data_path)
    print(f"  {len(df):,} completed rows loaded (model known, start <= today)")

    print("\nComputing inter-failure times (corrective + preventive)…")
    ifts = compute_ifts(df)
    print(f"  {len(ifts):,} IFT samples")
    for otg, cnt in ifts["order_type_group"].value_counts().items():
        print(f"    {otg}: {cnt:,}")

    print("\nFitting Weibull distributions…")
    weibull_df = fit_weibull(ifts, raw_wos=df)

    print("\nFitting repair/PM durations…")
    dur_df = fit_durations(df)

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n── Weibull IFT fits ──────────────────────────────────────────────────")
    if weibull_df.empty:
        print("  (no groups with sufficient data)")
    else:
        hdr = "{:10}  {:8}  {:11}  {:10}  {:>7}  {:>11}  {:>10}  {:>6}".format(
            "model", "equip", "order_type", "activity", "shape", "scale_fleet", "scale_unit", "n"
        )
        print(hdr)
        print("─" * len(hdr))
        for _, r in weibull_df.iterrows():
            print(
                "{:10}  {:8}  {:11}  {:10}  {:7.3f}  {:11.1f}  {:10.0f}  {:6d}".format(
                    r["model"], r["equip_type"], r["order_type_group"], r["activity_group"],
                    r["shape"], r["scale_fleet_cal"], r["scale_individual_cal"], r["n"],
                )
            )

    print("\n── Duration fits ─────────────────────────────────────────────────────")
    if dur_df.empty:
        print("  (no groups)")
    else:
        hdr2 = "{:10}  {:12}  {:10}  {:>8}  {:>7}  {:>6}".format(
            "model", "type", "activity", "mean", "sd", "n"
        )
        print(hdr2)
        print("─" * len(hdr2))
        for _, r in dur_df.iterrows():
            print(
                "{:10}  {:12}  {:10}  {:8.2f}h  {:6.2f}h  {:6d}".format(
                    r["model"], r["order_type_group"], r["activity_group"],
                    r["dur_mean"], r["dur_sd"], r["n"],
                )
            )

    print("\nExporting fitted_config.py…")
    out = export_config(weibull_df, dur_df)
    print(f"  Written to {out}")


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
