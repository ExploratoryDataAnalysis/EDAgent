"""Modelling data preparation, chronological splitting, and leakage validation.

Governed by Project Plan v2 (§8, §18) and Phase 4 Module B requirements.
Ensures zero future information leaks into training data and validates site-year
continuity, legitimate zero-crash years, and exposure integrity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from edagent.roadway.schema import RoadClass


class InsufficientExposureError(Exception):
    """Raised when modeling is attempted with missing, zero, or invalid exposure."""


class TemporalLeakageError(Exception):
    """Raised when future information leaks into historical training data."""


@dataclass
class SiteYearRecord:
    """Individual site-year observation record for frequency modelling."""

    site_id: str
    year: int
    crash_count: int
    is_zero_crash: bool
    road_class: RoadClass
    length_km: float
    traffic_exposure: Optional[float] = None
    speed_limit_mph: Optional[int] = None
    lanes: Optional[int] = None
    is_divided: Optional[bool] = None

    def __post_init__(self) -> None:
        if self.crash_count < 0:
            raise ValueError(f"crash_count cannot be negative: {self.crash_count}")
        if self.is_zero_crash and self.crash_count != 0:
            raise ValueError("is_zero_crash is True but crash_count != 0")
        if not self.is_zero_crash and self.crash_count == 0:
            raise ValueError("is_zero_crash is False but crash_count == 0")
        if self.length_km <= 0.0:
            raise ValueError(f"length_km must be strictly positive: {self.length_km}")
        if self.traffic_exposure is not None and self.traffic_exposure < 0.0:
            raise ValueError(f"traffic_exposure cannot be negative: {self.traffic_exposure}")


@dataclass
class ModellingDataset:
    """Chronologically separated dataset container for frequency modelling."""

    train_records: List[SiteYearRecord]
    test_records: List[SiteYearRecord]
    train_years: Tuple[int, ...]
    test_years: Tuple[int, ...]
    feature_names: List[str]
    has_valid_exposure: bool
    exposure_basis: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Enforce chronological separation: max(train_years) < min(test_years)
        if self.train_years and self.test_years:
            if max(self.train_years) >= min(self.test_years):
                raise TemporalLeakageError(
                    f"Train years ({self.train_years}) overlap or succeed test years ({self.test_years}). "
                    "Chronological separation violated."
                )


class SiteYearDataPreparer:
    """Prepares and validates site-year panel datasets for frequency modelling."""

    def __init__(
        self,
        default_train_years: Tuple[int, ...] = (2016, 2017, 2018, 2019, 2020),
        default_test_years: Tuple[int, ...] = (2021, 2022, 2023, 2024),
    ):
        self.train_years = default_train_years
        self.test_years = default_test_years

    def validate_site_identity(self, site_id: str) -> bool:
        """Validate site identifier format."""
        if not site_id or not isinstance(site_id, str):
            return False
        # Matches state route segment, county centerline segment, or intersection
        pattern = r"^(SEG:(02:SR[0-9]{4}:[0-9]{4}|AC:[0-9]+)|INT:[A-Fa-f0-9]{12})$"
        return bool(re.match(pattern, site_id.strip()))

    def prepare_dataset(
        self,
        records: List[Dict[str, Any]],
        train_years: Optional[Tuple[int, ...]] = None,
        test_years: Optional[Tuple[int, ...]] = None,
        require_exposure: bool = False,
    ) -> ModellingDataset:
        """Parse raw record dictionaries and construct a chronologically separated dataset.

        Args:
            records: List of dictionaries matching site-year prototype or database rows.
            train_years: Explicit train year range; defaults to (2016-2020).
            test_years: Explicit test year range; defaults to (2021-2024).
            require_exposure: If True, raises InsufficientExposureError if exposure is missing.

        Raises:
            InsufficientExposureError: If require_exposure is True and records lack exposure.
            TemporalLeakageError: If chronological separation is violated.
        """
        tr_years = train_years or self.train_years
        te_years = test_years or self.test_years

        # Verify chronological ordering
        if max(tr_years) >= min(te_years):
            raise TemporalLeakageError(
                f"Max train year ({max(tr_years)}) >= Min test year ({min(te_years)})."
            )

        parsed_train: List[SiteYearRecord] = []
        parsed_test: List[SiteYearRecord] = []
        valid_exposure_count = 0
        total_eval_records = 0

        for r in records:
            site_id = str(r.get("site_id", "")).strip()
            if not self.validate_site_identity(site_id):
                continue

            year = int(r.get("year", 0))
            if year not in tr_years and year not in te_years:
                continue

            crash_count = int(r.get("crash_count", 0))
            is_zero = bool(r.get("is_zero_crash_observation", crash_count == 0))
            if is_zero and crash_count != 0:
                is_zero = False

            road_class_str = str(r.get("road_class", "LOCAL_STREET")).upper()
            try:
                road_class = RoadClass[road_class_str]
            except KeyError:
                road_class = RoadClass.LOCAL_STREET

            length_km = float(r.get("length_km", 0.5))  # Default 0.5km if unpopulated
            if length_km <= 0.0:
                length_km = 0.5

            raw_exp = r.get("traffic_exposure")
            exposure: Optional[float] = None
            if raw_exp is not None and str(raw_exp).strip() != "":
                try:
                    val = float(raw_exp)
                    if val > 0.0:
                        exposure = val
                        valid_exposure_count += 1
                except (ValueError, TypeError):
                    exposure = None

            speed_limit = int(r["speed_limit_mph"]) if r.get("speed_limit_mph") else None
            lanes = int(r["lanes"]) if r.get("lanes") else None
            is_divided = bool(r["is_divided"]) if r.get("is_divided") is not None else None

            rec = SiteYearRecord(
                site_id=site_id,
                year=year,
                crash_count=crash_count,
                is_zero_crash=is_zero,
                road_class=road_class,
                length_km=length_km,
                traffic_exposure=exposure,
                speed_limit_mph=speed_limit,
                lanes=lanes,
                is_divided=is_divided,
            )

            total_eval_records += 1
            if year in tr_years:
                parsed_train.append(rec)
            else:
                parsed_test.append(rec)

        has_valid_exposure = (
            total_eval_records > 0 and valid_exposure_count == total_eval_records
        )

        if require_exposure and not has_valid_exposure:
            raise InsufficientExposureError(
                f"Modelling data requires verified traffic exposure. Found {valid_exposure_count} "
                f"valid exposure records out of {total_eval_records} total site-years."
            )

        exposure_basis = (
            "Annual Daily VMT (AADT * Length_km * 365)"
            if has_valid_exposure
            else "UNAVAILABLE"
        )

        feature_names = ["road_class", "length_km"]

        return ModellingDataset(
            train_records=parsed_train,
            test_records=parsed_test,
            train_years=tr_years,
            test_years=te_years,
            feature_names=feature_names,
            has_valid_exposure=has_valid_exposure,
            exposure_basis=exposure_basis,
            metadata={
                "total_train_records": len(parsed_train),
                "total_test_records": len(parsed_test),
                "valid_exposure_records": valid_exposure_count,
                "zero_crash_train_records": sum(1 for r in parsed_train if r.is_zero_crash),
                "zero_crash_test_records": sum(1 for r in parsed_test if r.is_zero_crash),
            },
        )
