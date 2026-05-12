"""Smoke tests for the fitting pipeline."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

# Make sure the fitting package under src/ is importable
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

ACTUALS_PATH = Path(__file__).parents[2] / "actuals" / "am_work_order_vw.xlsx"
pytestmark = pytest.mark.skipif(
    not ACTUALS_PATH.exists(),
    reason="actuals/am_work_order_vw.xlsx not present",
)


@pytest.fixture(scope="module")
def df():
    from fitting.load import load_work_orders
    return load_work_orders(ACTUALS_PATH)


@pytest.fixture(scope="module")
def ifts(df):
    from fitting.ift import compute_ifts
    return compute_ifts(df)


@pytest.fixture(scope="module")
def weibull_df(ifts):
    from fitting.weibull_fit import fit_weibull
    return fit_weibull(ifts)


@pytest.fixture(scope="module")
def dur_df(df):
    from fitting.duration_fit import fit_durations
    return fit_durations(df)


# ── load.py ───────────────────────────────────────────────────────────────────

def test_load_returns_dataframe(df):
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_load_no_future_dates(df):
    now = pd.Timestamp.now(tz="UTC")
    assert (df["actual_start_timestamp"] <= now).all()


def test_load_completed_only(df):
    assert (df["completed_flag"] == 1).all()


def test_load_known_equip_type_only(df):
    assert df["equip_type"].notna().all()
    assert set(df["equip_type"].unique()) <= {"truck", "shovel"}


def test_load_model_column(df):
    assert "model" in df.columns
    assert df["model"].notna().all()
    assert set(df["model"].unique()) <= {"Cat_793F", "EH4000", "EH5000", "EX3600", "EX5600", "EX8000", "L9800"}


def test_load_order_type_group_values(df):
    assert set(df["order_type_group"].unique()) <= {"corrective", "preventive", "other"}


# ── ift.py ────────────────────────────────────────────────────────────────────

def test_ifts_positive(ifts):
    assert (ifts["ift_hrs"] > 0).all()


def test_ifts_columns(ifts):
    assert {"model", "equip_type", "order_type_group", "activity_group", "ift_hrs"} <= set(ifts.columns)


def test_ifts_order_type_groups(ifts):
    assert set(ifts["order_type_group"].unique()) <= {"corrective", "preventive"}


def test_ifts_above_floor(ifts):
    assert (ifts["ift_hrs"] > 0.5).all()


def test_ifts_groups_present(ifts):
    groups = set(zip(ifts["model"], ifts["order_type_group"], ifts["activity_group"]))
    assert ("Cat_793F", "corrective", "RPR") in groups
    assert ("Cat_793F", "corrective", "RPL") in groups
    assert ("Cat_793F", "preventive", "SVC") in groups


# ── weibull_fit.py ────────────────────────────────────────────────────────────

def test_weibull_shape_positive(weibull_df):
    assert (weibull_df["shape"] > 0).all()


def test_weibull_scale_positive(weibull_df):
    assert (weibull_df["scale_fleet_cal"] > 0).all()
    assert (weibull_df["scale_individual_cal"] > 0).all()
    assert (weibull_df["scale_op"] > 0).all()


def test_weibull_scale_individual_gt_fleet(weibull_df):
    # scale_individual = scale_fleet * N_units (N_units >= 1)
    assert (weibull_df["scale_individual_cal"] >= weibull_df["scale_fleet_cal"]).all()


def test_weibull_truck_rpr_rpl_ins_present(weibull_df):
    groups = set(zip(weibull_df["model"], weibull_df["order_type_group"], weibull_df["activity_group"]))
    assert ("Cat_793F", "corrective", "RPR") in groups, "Cat_793F/corrective/RPR Weibull fit must be present"
    assert ("Cat_793F", "corrective", "RPL") in groups, "Cat_793F/corrective/RPL Weibull fit must be present"
    assert ("Cat_793F", "preventive", "SVC") in groups, "Cat_793F/preventive/SVC Weibull fit must be present"


def test_weibull_sufficient_samples(weibull_df):
    assert (weibull_df["n"] >= 30).all()


# ── duration_fit.py ───────────────────────────────────────────────────────────

def test_duration_mean_positive(dur_df):
    assert (dur_df["dur_mean"] > 0).all()


def test_duration_sd_positive(dur_df):
    assert (dur_df["dur_sd"] > 0).all()


def test_duration_columns(dur_df):
    assert {"model", "equip_type", "order_type_group", "activity_group", "dur_mean", "dur_sd", "n"} <= set(dur_df.columns)


# ── export_config.py ──────────────────────────────────────────────────────────

def test_export_config_importable(weibull_df, dur_df, tmp_path):
    from fitting.export_config import export_config
    out = export_config(weibull_df, dur_df, output_path=tmp_path / "fitted_config.py")
    assert out.exists()
    spec = importlib.util.spec_from_file_location("fitted_config", out)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "PREMATURE_FAILURE_FITTED")
    assert isinstance(mod.PREMATURE_FAILURE_FITTED, dict)
    # Must be 3-level: model → order_type_group → activity_group → entry
    first_model = next(iter(mod.PREMATURE_FAILURE_FITTED))
    first_otg = next(iter(mod.PREMATURE_FAILURE_FITTED[first_model]))
    assert first_otg in ("corrective", "preventive")
    first_ag_entry = next(iter(mod.PREMATURE_FAILURE_FITTED[first_model][first_otg].values()))
    assert "shape" in first_ag_entry
    assert "scale" in first_ag_entry
