#!/usr/bin/env python3
"""
PTAC Calendar Generator
- Denunzio address updated to Faculty Road
- Start time AM/PM assumption based on duration < 6 hours
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, time as dtime, timezone, timedelta
import re
import uuid
import argparse
import sys
from pathlib import Path

ADDRESS_MAP = {
    "Denunzio": "DeNunzio Pool, Faculty Road, Princeton, NJ 08540",
    "DeNunzio": "DeNunzio Pool, Faculty Road, Princeton, NJ 08540",
    "DeNuzio": "DeNunzio Pool, Faculty Road, Princeton, NJ 08540",
    "WAC": "Windsor Athletic Club, 70 Palmer Drive, East Windsor, NJ 08520",
    "MCCC": "Mercer County Community College Pool, 1200 Old Trenton Road, West Windsor, NJ 08550",
    "Princeton MS": "Princeton Middle School Pool, 217 Walnut Lane, Princeton, NJ 08540",
    "Waterworks": "Waterworks Park Pool, Princeton, NJ 08540",
    "PMS": "Princeton Middle School Pool, 217 Walnut Lane, Princeton, NJ 08540",
}

GROUPS = ["AG1", "AG2", "AG3", "SR", "JR", "VAR"]


def ical_escape(text: str) -> str:
    return (
        text.replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\n', '\\n')
    )


def parse_arguments():
    parser = argparse.ArgumentParser(description="PTAC Calendar Generator")
    parser.add_argument('--with-addresses', action='store_true', help='Use full addresses')
    parser.add_argument('--debug', action='store_true', default=False, help='Debug output')
    return parser.parse_args()


def fetch_page():
    url = 'https://www.gomotionapp.com/team/njptac/page/calendar1/all-groups'
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        print(f"Fetch failed: {e}")
        sys.exit(1)


def parse_time_str(tstr: str, debug: bool = False) -> dtime:
    """Parse a single time string that may or may not contain AM/PM."""
    tstr = tstr.strip().upper()
    ampm_match = re.search(r'(AM|PM)', tstr)
    clean = re.sub(r'(AM|PM)', '', tstr, flags=re.IGNORECASE).strip()

    try:
        h_str, m_str = clean.split(':')
        h = int(h_str)
        m = int(m_str or '0')
    except Exception:
        if debug:
            print(f"[DEBUG] Time split failed: '{tstr}'")
        raise

    if ampm_match:
        ampm = ampm_match.group(0).upper()
        if ampm == 'PM' and h < 12:
            h += 12
        elif ampm == 'AM' and h == 12:
            h = 0

    return dtime(h % 24, m)


def choose_best_start(start_str: str, end_dt: datetime, year: int, month: day, day: int, debug: bool = False):
    """
    If start time has no AM/PM, try both possibilities and pick the one
    that results in a duration less than 6 hours.
    """
    start_has_ampm = bool(re.search(r'(AM|PM)', start_str, re.IGNORECASE))

    # First try the natural parse
    try:
        start_t = parse_time_str(start_str, debug=debug)
        start_dt = datetime(year, month, day, start_t.hour, start_t.minute)
        duration = (end_dt - start_dt).total_seconds() / 3600

        if start_has_ampm or (0 < duration < 6):
            if debug:
                print(f"[DEBUG] Using start {start_dt.strftime('%I:%M %p')} (duration {duration:.1f}h)")
            return start_dt
    except Exception:
        pass

    # Try forcing AM and PM versions
    candidates = []
    for force_pm in [False, True]:
        try:
            tstr = start_str
            # Remove any existing AM/PM then force one
            clean = re.sub(r'(AM|PM)', '', tstr, flags=re.IGNORECASE).strip()
            h, m = map(int, clean.split(':'))
            if force_pm and h < 12:
                h += 12
            elif not force_pm and h == 12:
                h = 0
            candidate = datetime(year, month, day, h % 24, m)
            duration = (end_dt - candidate).total_seconds() / 3600
            candidates.append((candidate, duration, force_pm))
        except Exception:
            continue

    # Prefer the candidate with duration between 0 and 6 hours
    valid = [c for c in candidates if 0 < c[1] < 6]
    if valid:
        best = min(valid, key=lambda x: abs(x[1] - 2.0))  # prefer ~2h practices
        if debug:
            print(f"[DEBUG] Chose {'PM' if best[2] else 'AM'} start → {best[0].strftime('%I:%M %p')} (duration {best[1]:.1f}h)")
        return best[0]

    # Fallback: original parse
    start_t = parse_time_str(start_str, debug=debug)
    return datetime(year, month, day, start_t.hour, start_t.minute)


def parse_events(raw_text: str, allowed_groups: set = None, only_all_day: bool = False, debug: bool = False):
    if not raw_text:
        return []

    if allowed_groups is None:
        allowed_groups = set()

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    events = []
    year = datetime.today().year
    current_date = None
    current_location = ""
    current_notes = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Date
        date_m = re.search(