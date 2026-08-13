"""
Maps a user-facing target year to DMI's 30-year climate periods.
Users think in terms of "2050" — DMI thinks in terms of 2041-2070.
"""


def year_to_dmi_period(target_year: int) -> str:
    if target_year < 2011:
        return "Reference"
    elif target_year <= 2040:
        return "Early century"
    elif target_year <= 2070:
        return "Mid century"
    else:
        return "Late century"


def period_label_to_range(period_label: str) -> str:
    ranges = {
        "Reference": "1981-2010",
        "Early century": "2011-2040",
        "Mid century": "2041-2070",
        "Late century": "2071-2100",
    }
    return ranges.get(period_label, "unknown")
