#!/usr/bin/env python3
"""
PTAC Calendar Generator
- Denunzio address: DeNunzio Pool, Faculty Road
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


def 
