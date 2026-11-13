"""Version 1 of the hypothetical intervention scenario contract."""

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BeforeValidator, ConfigDict, Field, WithJsonSchema, model_validator
from pydantic_core import PydanticCustomError

from app.schemas.common import BaseSchema

DECIMAL_PATTERN = r"^-?[0-9]{1,12}(\.[0-9]{1,6})?$"


def decimal_text(value: object) -> str:
    # Decimal strings preserve the submitted digits through browser and JSON parsing.
    if not isinstance(value, str) or not re.fullmatch(DECIMAL_PATTERN, value):
        raise PydanticCustomError(
            "decimal_text", "Use a decimal string with up to 12 whole and 6 fractional digits."
        )
    return value


ScenarioDecimal = Annotated[
    Decimal,
    Field(allow_inf_nan=False),
    BeforeValidator(decimal_text),
    WithJsonSchema({"type": "string", "pattern": DECIMAL_PATTERN}, mode="validation"),
]
PositiveFactor = Annotated[ScenarioDecimal, Field(gt=0)]
CrashType = Literal["ALL", "PEDESTRIAN", "BICYCLIST", "REAR_END", "ANGLE", "NIGHTTIME"]


class ScenarioInput(BaseSchema):
    model_config = ConfigDict(extra="forbid")


class AnalysisPeriod(ScenarioInput):
    length: int = Field(strict=True, gt=0)
    unit: Literal["YEARS"]


class FactorBounds(ScenarioInput):
    lower: PositiveFactor
    upper: PositiveFactor


class HypotheticalFactor(ScenarioInput):
    origin: Literal["USER_ENTERED_HYPOTHETICAL"]
    crash_type: CrashType
    value: PositiveFactor
    bounds: FactorBounds | None = None


class EvidenceFactorRequest(ScenarioInput):
    origin: Literal["EVIDENCE_REGISTER"]
    evidence_id: str = Field(min_length=1)


class InterventionScenario(ScenarioInput):
    schema_version: Literal["1"]
    scenario_kind: Literal["HYPOTHETICAL"]
    hypothetical_baseline_n: Annotated[ScenarioDecimal, Field(ge=0)]
    crash_type: CrashType
    analysis_period: AnalysisPeriod
    units: Literal["CRASHES_PER_ANALYSIS_PERIOD"]
    cmf: HypotheticalFactor | EvidenceFactorRequest = Field(discriminator="origin")

    @model_validator(mode="after")
    def validate_factor(self):
        if isinstance(self.cmf, HypotheticalFactor):
            if self.cmf.crash_type != self.crash_type:
                raise PydanticCustomError("crash_type_mismatch", "Baseline and CMF crash types must match.")
            bounds = self.cmf.bounds
            if bounds and not bounds.lower <= self.cmf.value <= bounds.upper:
                raise PydanticCustomError("invalid_factor_bounds", "CMF bounds must bracket the factor.")
        return self


class CountInterval(BaseSchema):
    lower: Decimal
    upper: Decimal


class FactorSensitivity(BaseSchema):
    label: Literal["Hypothetical factor sensitivity range"] = "Hypothetical factor sensitivity range"
    after_n: CountInterval
    delta_n: CountInterval


class CrashCounts(BaseSchema):
    hypothetical_baseline_n: Decimal
    after_n: Decimal
    delta_n: Decimal
    sensitivity: FactorSensitivity | None = None


class IllustrativeResult(BaseSchema):
    status: Literal["ILLUSTRATIVE_ONLY"] = "ILLUSTRATIVE_ONLY"
    label: Literal["Illustrative scenario"] = "Illustrative scenario"
    change_label: str = "Hypothetical change in crash count"
    notice: str = "This calculation illustrates assumed inputs. It does not estimate a real-site or causal effect."
    scenario: InterventionScenario
    exact: CrashCounts
    display: CrashCounts
