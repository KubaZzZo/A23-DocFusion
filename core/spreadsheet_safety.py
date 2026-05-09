"""Spreadsheet export safety helpers."""

FORMULA_PREFIXES = ("=", "+", "-", "@")


def escape_formula_value(value):
    """Prefix spreadsheet formulas so Excel treats them as literal text."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value
