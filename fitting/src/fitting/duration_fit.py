"""Fit Normal(mean, sd) to repair/PM durations per (model, order_type_group, activity_group)."""

from __future__ import annotations

import pandas as pd

# Minimum standard deviation to avoid a degenerate Normal distribution.
_MIN_SD = 0.1


def fit_durations(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of Normal duration parameters per group.

    Parameters
    ----------
    df:
        Cleaned work orders from ``load.load_work_orders()``.

    Returns
    -------
    DataFrame with columns:
        ``model``, ``equip_type``, ``order_type_group``, ``activity_group``,
        ``dur_mean``, ``dur_sd``, ``n``

    Only rows with ``sum_actual_hours > 0`` are used.
    """
    work = df[df["sum_actual_hours"] > 0].copy()

    _CM_AG_MAP = {"TYR": "TYR", "RPR": "RPR", "RPL": "RPL", "INS": "INS"}
    _PM_AG_MAP = {
        "RPL": "RPL", "SVC": "SVC", "NDT": "NDT",
        "INS": "INS", "TYR": "TYR", "CAS": "CAS",
    }

    def _classify(row: pd.Series) -> str:
        if row["order_type_group"] == "corrective":
            return _CM_AG_MAP.get(row["maintenance_activity_type_id"], "OTHER_CM")
        elif row["order_type_group"] == "preventive":
            return _PM_AG_MAP.get(row["maintenance_activity_type_id"], "OTHER_PM")
        return "OTHER"

    work["activity_group"] = work.apply(_classify, axis=1)

    rows = []
    for (model, order_type_group, activity_group), grp in work.groupby(
        ["model", "order_type_group", "activity_group"]
    ):
        hours = grp["sum_actual_hours"]
        n = len(hours)
        mean = float(hours.mean())
        sd = max(float(hours.std(ddof=1)) if n > 1 else 0.0, _MIN_SD)
        equip_type = grp["equip_type"].iloc[0]
        rows.append(
            {
                "model": model,
                "equip_type": equip_type,
                "order_type_group": order_type_group,
                "activity_group": activity_group,
                "dur_mean": mean,
                "dur_sd": sd,
                "n": n,
            }
        )

    return pd.DataFrame(rows)
