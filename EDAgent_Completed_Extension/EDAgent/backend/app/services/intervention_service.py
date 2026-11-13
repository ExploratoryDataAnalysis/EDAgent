"""Deterministic arithmetic on hypothetical counts and factors."""

from decimal import ROUND_HALF_UP, Context, Decimal, localcontext

from app.schemas.intervention import (
    CountInterval,
    CrashCounts,
    FactorSensitivity,
    HypotheticalFactor,
    IllustrativeResult,
    InterventionScenario,
)


def _display_count(count: Decimal) -> Decimal:
    rounded = count.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return rounded if rounded else rounded.copy_abs()


def _display_interval(interval: CountInterval) -> CountInterval:
    return CountInterval(lower=_display_count(interval.lower), upper=_display_count(interval.upper))


def calculate_scenario(scenario: InterventionScenario) -> IllustrativeResult:
    factor = scenario.cmf
    if not isinstance(factor, HypotheticalFactor):
        raise TypeError("The calculator requires a user-entered hypothetical factor.")

    baseline = scenario.hypothetical_baseline_n.copy_abs()
    # Two 18-digit inputs and the subtraction fit exactly at this precision.
    with localcontext(Context(prec=40)):
        after = baseline * factor.value
        # Positive delta means a reduction. CMFs over 1 yield a negative delta.
        delta = baseline * (1 - factor.value)
        sensitivity = display_sensitivity = None
        if bounds := factor.bounds:
            sensitivity = FactorSensitivity(
                after_n=CountInterval(lower=baseline * bounds.lower, upper=baseline * bounds.upper),
                # Delta falls as the factor rises, so its endpoints run in the opposite order.
                delta_n=CountInterval(
                    lower=baseline * (1 - bounds.upper), upper=baseline * (1 - bounds.lower)
                ),
            )
            display_sensitivity = FactorSensitivity(
                after_n=_display_interval(sensitivity.after_n),
                delta_n=_display_interval(sensitivity.delta_n),
            )
        return IllustrativeResult(
            scenario=scenario,
            exact=CrashCounts(
                hypothetical_baseline_n=baseline, after_n=after, delta_n=delta, sensitivity=sensitivity
            ),
            display=CrashCounts(
                hypothetical_baseline_n=_display_count(baseline),
                after_n=_display_count(after),
                delta_n=_display_count(delta),
                sensitivity=display_sensitivity,
            ),
        )
