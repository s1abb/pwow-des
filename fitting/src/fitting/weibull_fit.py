"""Fit Weibull(shape, scale) to model-level IFT samples per (model, order_type_group, activity_group)."""

from __future__ import annotations

import warnings
from math import gamma as _gamma

import pandas as pd
from scipy.stats import weibull_min

# Minimum sample count required to attempt a Weibull fit.
_MIN_SAMPLES = 30

# Per-model fleet sizes from actuals.
N_UNITS: dict[str, int] = {
    "Cat_793F": 56,
    "EH4000":   19,
    "EH5000":   24,
    "EX3600":    8,
    "EX5600":    5,
    "EX8000":    3,
    "L9800":     2,
}

# equip_type lookup for each model (used to tag output rows)
_MODEL_EQUIP_TYPE: dict[str, str] = {
    "Cat_793F": "truck",
    "EH4000":   "truck",
    "EH5000":   "truck",
    "EX3600":   "shovel",
    "EX5600":   "shovel",
    "EX8000":   "shovel",
    "L9800":    "shovel",
}


def fit_weibull(
    ifts: pd.DataFrame,
    util_factor: float = 1.0,
    raw_wos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Fit a 2-parameter Weibull (loc=0) to each (model, order_type_group, activity_group).

    Parameters
    ----------
    ifts:
        Output of ``ift.compute_ifts()`` — columns ``model``, ``equip_type``,
        ``order_type_group``, ``activity_group``, ``ift_hrs``.
    util_factor:
        Fraction of calendar hours that equipment is operating.  Applied as
        ``scale_op = scale_individual_cal * util_factor``.  Default 1.0
        (calendar hours == operating hours).
    raw_wos:
        Optional raw work orders DataFrame from ``load.load_work_orders()``.
        When provided, the per-unit Weibull scale is derived from the true
        observed WO rate rather than from the pooled fleet IFTs, correcting
        the bias introduced by the IFT floor filter and fleet-level pooling.

        The rate-corrected scale formula is::

            scale_individual_cal = n_units × span_hrs / (n_wos × Γ(1 + 1/shape))

        This sets the Weibull mean TTF equal to the empirical mean time between
        work orders per unit, while preserving the fitted shape parameter.

    Returns
    -------
    DataFrame with columns:
        ``model``, ``equip_type``, ``order_type_group``, ``activity_group``,
        ``shape``, ``scale_fleet_cal``, ``scale_individual_cal``, ``scale_op``,
        ``n_units``, ``util_factor``, ``n``

    Groups with fewer than ``_MIN_SAMPLES`` samples are omitted silently.
    """
    # Pre-compute rate lookup from raw WOs if provided
    _rate_lookup: dict[tuple, tuple] | None = None
    if raw_wos is not None:
        from .ift import _CM_AG_MAP, _PM_AG_MAP

        span_hrs = (
            raw_wos["actual_start_timestamp"].max()
            - raw_wos["actual_start_timestamp"].min()
        ).total_seconds() / 3600.0

        work = raw_wos[raw_wos["order_type_group"].isin(("corrective", "preventive"))].copy()

        def _classify(row: pd.Series) -> str:
            if row["order_type_group"] == "corrective":
                return _CM_AG_MAP.get(row["maintenance_activity_type_id"], "OTHER_CM")
            return _PM_AG_MAP.get(row["maintenance_activity_type_id"], "OTHER_PM")

        work["activity_group"] = work.apply(_classify, axis=1)
        work = work.drop_duplicates(subset="work_order_id")

        _rate_lookup = {
            (m, otg, ag): (int(cnt), span_hrs)
            for (m, otg, ag), cnt in work.groupby(
                ["model", "order_type_group", "activity_group"]
            ).size().items()
        }

    rows = []

    for (model, order_type_group, activity_group), grp in ifts.groupby(
        ["model", "order_type_group", "activity_group"]
    ):
        data = grp["ift_hrs"].values
        n = len(data)

        if n < _MIN_SAMPLES:
            warnings.warn(
                f"Skipping {model}/{order_type_group}/{activity_group}: only {n} samples "
                f"(minimum {_MIN_SAMPLES}).",
                UserWarning,
                stacklevel=2,
            )
            continue

        shape, _loc, scale_fleet_ift = weibull_min.fit(data, floc=0)

        n_units = N_UNITS.get(model, 1)
        equip_type = _MODEL_EQUIP_TYPE.get(model, "unknown")

        if _rate_lookup is not None:
            key = (model, order_type_group, activity_group)
            n_wos, span_hrs = _rate_lookup.get(key, (n, float(data.sum())))
            # Rate-corrected: Weibull mean = scale × Γ(1 + 1/shape) = empirical mean TTF
            empirical_mean_ttf = n_units * span_hrs / n_wos
            scale_individual_cal = empirical_mean_ttf / _gamma(1.0 + 1.0 / shape)
            scale_fleet_cal = scale_individual_cal / n_units
        else:
            scale_fleet_cal = scale_fleet_ift
            scale_individual_cal = scale_fleet_ift * n_units

        scale_op = scale_individual_cal * util_factor

        rows.append(
            {
                "model": model,
                "equip_type": equip_type,
                "order_type_group": order_type_group,
                "activity_group": activity_group,
                "shape": shape,
                "scale_fleet_cal": scale_fleet_cal,
                "scale_individual_cal": scale_individual_cal,
                "scale_op": scale_op,
                "n_units": n_units,
                "util_factor": util_factor,
                "n": n,
            }
        )

    return pd.DataFrame(rows)
