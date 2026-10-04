import re

_VERDICT = re.compile(r"\s*verdict:\s*(yes|no)\b", re.IGNORECASE)


def get_verdict(description: str) -> bool | None:
    """Return True for `Verdict: YES`, False for `Verdict: NO`, or None if the analysis has no verdict."""
    match = _VERDICT.match(description)
    if match is None:
        return None
    return match.group(1).lower() == "yes"
