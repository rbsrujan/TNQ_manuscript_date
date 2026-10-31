"""
Tests for date format parsing, normalization, leap years, and calendar validation.
"""

import pytest
from manusure.date_validator import parse_candidate_date_string


class TestDateFormats:
    """Test candidate date format parsing and calendar validation."""

    @pytest.mark.parametrize(
        "date_str, expected_iso",
        [
            ("15 January 2025", "2025-01-15"),
            ("15 Jan 2025", "2025-01-15"),
            ("15-Jan-2025", "2025-01-15"),
            ("15th January 2025", "2025-01-15"),
            ("1st February 2025", "2025-02-01"),
            ("2nd March 2024", "2024-03-02"),
            ("3rd April 2025", "2025-04-03"),
            ("21st May 2025", "2025-05-21"),
            ("22nd June 2025", "2025-06-22"),
            ("23rd July 2025", "2025-07-23"),
            ("31st August 2025", "2025-08-31"),
            ("January 15, 2025", "2025-01-15"),
            ("Jan 15, 2025", "2025-01-15"),
            ("Jan. 15, 2025", "2025-01-15"),
            ("January 15th, 2025", "2025-01-15"),
            ("2025-01-15", "2025-01-15"),
            ("2025/01/15", "2025-01-15"),
            ("2025.01.15", "2025-01-15"),
            ("15/01/2025", "2025-01-15"),  # Day 15 > 12: unambiguous DD/MM/YYYY
            ("25-12-2024", "2024-12-25"),  # Day 25 > 12: unambiguous DD-MM-YYYY
            ("05/05/2025", "2025-05-05"),  # Day == Month: unambiguous
        ],
    )
    def test_valid_date_formats(self, date_str: str, expected_iso: str):
        res = parse_candidate_date_string(date_str)
        assert res.is_usable, f"Expected usable date for '{date_str}'"
        assert res.normalized_date == expected_iso

    def test_leap_year_handling(self):
        # 2024 is a leap year
        res_leap = parse_candidate_date_string("29 February 2024")
        assert res_leap.is_usable
        assert res_leap.normalized_date == "2024-02-29"

        # 2023 is not a leap year
        res_non_leap = parse_candidate_date_string("29 February 2023")
        assert not res_non_leap.is_usable
        assert not res_non_leap.is_calendar_valid

        # Century leap year rule (2000 is leap, 1900 is not)
        res_2000 = parse_candidate_date_string("29 February 2000")
        assert res_2000.is_usable
        assert res_2000.normalized_date == "2000-02-29"

    @pytest.mark.parametrize(
        "invalid_str",
        [
            "35 January 2025",     # Invalid day 35
            "31 April 2025",       # April only has 30 days
            "31 June 2025",        # June only has 30 days
            "31 September 2025",   # September only has 30 days
            "31 November 2025",    # November only has 30 days
            "00 January 2025",     # Day 0 does not exist
            "15 UnknownMonth 2025",# Unrecognized month
            "15 January",          # Missing year
            "99/99/2025",          # Invalid numbers
        ],
    )
    def test_invalid_calendar_dates(self, invalid_str: str):
        res = parse_candidate_date_string(invalid_str)
        assert not res.is_usable
        assert not res.is_calendar_valid

    def test_ambiguous_numeric_date(self):
        # 01/02/2025 could be 1 Feb or 2 Jan
        res = parse_candidate_date_string("01/02/2025")
        assert not res.is_usable
        assert res.is_ambiguous_numeric

        # 04/10/2024 could be 4 Oct or 10 Apr
        res2 = parse_candidate_date_string("04/10/2024")
        assert not res2.is_usable
        assert res2.is_ambiguous_numeric

    def test_whitespace_and_casing(self):
        res_upper = parse_candidate_date_string("15 JANUARY 2025")
        assert res_upper.is_usable
        assert res_upper.normalized_date == "2025-01-15"

        res_lower = parse_candidate_date_string("15 january 2025")
        assert res_lower.is_usable
        assert res_lower.normalized_date == "2025-01-15"

        res_ws = parse_candidate_date_string("   15   January   2025   ")
        assert res_ws.is_usable
        assert res_ws.normalized_date == "2025-01-15"
