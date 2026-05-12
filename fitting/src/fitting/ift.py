"""Compute fleet-level inter-failure times (IFTs) from corrective and preventive work orders."""

from __future__ import annotations

import pandas as pd

# Minimum IFT in hours — discards events with timestamps rounded to the same
# hour (genuine zero-time duplicates after work_order_id dedup).
_IFT_FLOOR_HRS = 0.5

# Activity group maps per order type
_CM_AG_MAP: dict[str, str] = {"TYR": "TYR", "RPR": "RPR", "RPL": "RPL", "INS": "INS"}
_PM_AG_MAP: dict[str, str] = {
    "RPL": "RPL", "SVC": "SVC", "NDT": "NDT",
    "INS": "INS", "TYR": "TYR", "CAS": "CAS",
}


def compute_ifts(df: pd.DataFrame) -> pd.DataFrame:
    """Return a tidy DataFrame of model-level IFTs for corrective and preventive events.

    Parameters
    ----------
    df:
        Cleaned work orders from ``load.load_work_orders()``.

    Returns
    -------
    DataFrame with columns:
        ``model``, ``equip_type``, ``order_type_group``, ``activity_group``, ``ift_hrs``

    Corrective activity groups
    --------------------------
    - ``RPR``      — corrective repairs (in-place)
    - ``RPL``      — corrective replacements
    - ``INS``      — corrective inspections
    - ``TYR``      — tyre corrective events
    - ``OTHER_CM`` — residual types (SVC, CAS, NDT); collapsed to avoid under-sampling

    Preventive activity groups
    --------------------------
    - ``RPL``      — preventive replacements
    - ``SVC``      — services
    - ``NDT``      — non-destructive testing
    - ``INS``      — preventive inspections
    - ``TYR``      — preventive tyre replacements
    - ``CAS``      — calibration/adjustment/setting
    - ``OTHER_PM`` — residual types; collapsed to avoid under-sampling
    """
    work = df[df["order_type_group"].isin(("corrective", "preventive"))].copy()

    def _classify(row: pd.Series) -> str:
        if row["order_type_group"] == "corrective":
            return _CM_AG_MAP.get(row["maintenance_activity_type_id"], "OTHER_CM")
        else:
            return _PM_AG_MAP.get(row["maintenance_activity_type_id"], "OTHER_PM")

    work["activity_group"] = work.apply(_classify, axis=1)

    # Deduplicate on work_order_id — primary mechanism against re-logged entries
    work = work.drop_duplicates(subset="work_order_id")

    work = work.sort_values(
        ["model", "order_type_group", "activity_group", "actual_start_timestamp"]
    )

    work["ift_hrs"] = (
        work.groupby(["model", "order_type_group", "activity_group"])["actual_start_timestamp"]
        .diff()
        .dt.total_seconds()
        / 3600.0
    )

    result = (
        work[work["ift_hrs"] > _IFT_FLOOR_HRS][
            ["model", "equip_type", "order_type_group", "activity_group", "ift_hrs"]
        ]
        .dropna()
        .reset_index(drop=True)
    )
    return result
