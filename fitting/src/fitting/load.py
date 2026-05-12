"""Load and clean work order actuals from Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Maps level_4_asset_description → (model short key, equip_type)
_FLEET_MAP: dict[str, tuple[str, str]] = {
    "Caterpillar 793F Dump Truck Fleet": ("Cat_793F", "truck"),
    "Hitachi EH4000 Dump Truck Fleet":   ("EH4000",   "truck"),
    "Hitachi EH5000 Dump Truck Fleet":   ("EH5000",   "truck"),
    "Hitachi EX3600 Excavator Fleet":    ("EX3600",   "shovel"),
    "Hitachi EX5600 Excavator Fleet":    ("EX5600",   "shovel"),
    "Hitachi EX8000 Excavator Fleet":    ("EX8000",   "shovel"),
    "Liebherr 9800 Excavator Fleet":     ("L9800",    "shovel"),
}

_ORDER_TYPE_MAP: dict[str, str] = {
    "Corrective Maintenance Order": "corrective",
    "Preventive Maintenance Order": "preventive",
}

_DEFAULT_PATH = Path(__file__).parents[3] / "actuals" / "am_work_order_vw.xlsx"


def load_work_orders(path: str | Path | None = None) -> pd.DataFrame:
    """Load, clean, and return the work order DataFrame.

    Filters applied:
    - ``completed_flag == 1``
    - ``actual_start_timestamp <= now (UTC)`` — removes future-dated anomalies
    - ``model`` is not null (known fleet types only)

    Added columns:
    - ``model``          — short model key, e.g. ``"Cat_793F"``, ``"EX3600"``
    - ``equip_type``     — ``"truck"`` or ``"shovel"``
    - ``order_type_group`` — ``"corrective"``, ``"preventive"``, or ``"other"``
    """
    source = Path(path) if path is not None else _DEFAULT_PATH

    df = pd.read_excel(source)

    df["actual_start_timestamp"] = pd.to_datetime(
        df["actual_start_timestamp"], utc=True
    )
    df["actual_finish_timestamp"] = pd.to_datetime(
        df["actual_finish_timestamp"], utc=True, errors="coerce"
    )

    # Map model short key and equip_type
    _mapped = df["level_4_asset_description"].map(_FLEET_MAP)
    df["model"]      = _mapped.map(lambda x: x[0] if isinstance(x, tuple) else None)
    df["equip_type"] = _mapped.map(lambda x: x[1] if isinstance(x, tuple) else None)

    # Derive order type group
    df["order_type_group"] = (
        df["order_type_description"].map(_ORDER_TYPE_MAP).fillna("other")
    )

    # Keep only completed orders
    df = df[df["completed_flag"] == 1].copy()

    # Exclude future-dated anomalies (planned orders incorrectly marked complete)
    now_utc = pd.Timestamp.now(tz="UTC")
    df = df[df["actual_start_timestamp"] <= now_utc].copy()

    # Drop rows with unknown fleet type
    df = df.dropna(subset=["model"]).copy()

    df = df.reset_index(drop=True)
    return df
