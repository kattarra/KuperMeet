"""Mutual gender-preference matching rules for KuperMeet."""


def are_genders_compatible(
    viewer_gender: str | None,
    viewer_looking_for: str | None,
    candidate_gender: str | None,
    candidate_looking_for: str | None,
) -> bool:
    """Both people must be interested in each other's gender."""
    valid_gender = {"male", "female"}
    valid_preference = {"male", "female", "all"}
    if viewer_gender not in valid_gender or candidate_gender not in valid_gender:
        return False
    if viewer_looking_for not in valid_preference or candidate_looking_for not in valid_preference:
        return False
    viewer_accepts = viewer_looking_for == "all" or viewer_looking_for == candidate_gender
    candidate_accepts = candidate_looking_for == "all" or candidate_looking_for == viewer_gender
    return viewer_accepts and candidate_accepts
