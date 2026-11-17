"""Age-segment and compatibility rules for KuperMeet.

Teen profiles can be represented in the data model from day one, but the teen
segment must remain unavailable until a real age-verification flow and the
required safety controls are implemented and enabled.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgePolicy:
    min_age: int = 14
    max_age: int = 99


DEFAULT_POLICY = AgePolicy()


def age_segment(age: int) -> str | None:
    """Return a user's age segment, or None when the age is outside policy."""
    if not DEFAULT_POLICY.min_age <= age <= DEFAULT_POLICY.max_age:
        return None
    return "teen" if age < 18 else "adult"


def max_age_gap(age_a: int, age_b: int) -> int:
    """Return the allowed age gap for a pair, based on the younger person's age."""
    younger_age = min(age_a, age_b)
    if younger_age < 14:
        return -1
    if younger_age < 18:
        return 2
    if younger_age <= 20:
        return 3
    if younger_age <= 24:
        return 4
    if younger_age <= 29:
        return 6
    if younger_age <= 39:
        return 8
    if younger_age <= 49:
        return 12
    return 15


def are_ages_compatible(
    age_a: int,
    age_b: int,
    *,
    teen_segment_enabled: bool = False,
    both_ages_verified: bool = False,
) -> bool:
    """Check segment isolation and the age-gap rule.

    Adults can match with adults. Teen-to-teen compatibility is prepared in
    code, but is denied by default until the teen segment and age verification
    are explicitly enabled. Cross-segment matching is always denied.
    """
    segment_a = age_segment(age_a)
    segment_b = age_segment(age_b)
    if segment_a is None or segment_b is None or segment_a != segment_b:
        return False

    if segment_a == "teen" and not (teen_segment_enabled and both_ages_verified):
        return False

    return abs(age_a - age_b) <= max_age_gap(age_a, age_b)
