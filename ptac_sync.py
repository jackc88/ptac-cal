#!/usr/bin/env python3
"""
PTAC Calendar Generator
- Creates all.ics (full unfiltered)
- Creates one .ics per group (AG1.ics, AG2.ics, etc.)
- Past events are excluded by default
- X-WR-CALNAME is set for each file
- Optional --with-addresses for GPS-friendly locations
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, time as dtime
import re
import uuid
import argparse
import sys
from pathlib import Path

# ==================== CONFIG ====================
ADDRESS_MAP = {
    "Denunzio": "DeNunzio Pool, Stadium Dr, Princeton, NJ 08540",
    "WAC": "Windsor Athletic Club, 70 Palmer Drive, East Windsor, NJ 08520",
    "MCCC": "Mercer County Community College Pool, 1200 Old Trenton Road, West Windsor, NJ 08550",
    "Princeton MS": "Princeton Middle School Pool, 217 Walnut Lane, Princeton, NJ 08540",
    "Waterworks": "Waterworks Park Pool, Princeton, NJ 08540",
    "PMS": "Princeton Middle School Pool, 217 Walnut Lane, Princeton, NJ 08540",
}

GROUPS = ["AG1", "AG2", "AG3", "SR", "JR", "VAR"]

# ===============================================

def ical_escape(text: str) -> str:
    return (
        text.replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\n', '\\n')
    )


def parse_arguments():
    parser = argparse.ArgumentParser(description="PTAC Calendar Generator")
    parser.add_argument('--with-addresses', action='store_true',
                        help='Convert locations to full street addresses for GPS/maps')
    parser.add_argument('--future-only', action='store_true', default=True,
                        help='Exclude past events (default: True)')
    parser.add_argument('--debug', action='store_true', help='Show debug output')
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


def parse_events(raw_text: str, allowed_groups: set = None, debug: bool = False):
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

        date_m = re.match(r'^(\*?\*?)?(\d{1,2})/(\d{1,2})(\*?\*?)?$', line)
        if date_m:
            if current_date:
                flush_day(events, year, current_date, current_location, current_notes)
            month, day = int(date_m.group(2)), int(date_m.group(3))
            current_date = (month, day)
            current_location = ""
            current_notes = []
            i += 1
            continue

        if not current_date:
            i += 1
            continue

        loc_m = re.match(r'^[A-Z][a-zA-Z& ]{2,}$', line)
        if loc_m and not re.search(r'\d', line):
            if current_notes:
                flush_day(events, year, current_date, current_location, current_notes)
            current_location = loc_m.group(0).strip()
            current_notes = []
            i += 1
            continue

        workout_m = re.match(r'^([A-Z0-9]+)\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*([AP]M)?$', line)
        if workout_m:
            group = workout_m.group(1).upper()
            start_str = workout_m.group(2)
            end_str = workout_m.group(3)
            ampm = workout_m.group(4) or ''

            if allowed_groups and group not in allowed_groups:
                i += 1
                continue

            try:
                start_t = parse_time_str(start_str, end_ampm_hint=ampm)
                end_t = parse_time_str(end_str, end_ampm_hint=ampm)

                start_dt = datetime(year, current_date[0], current_date[1], start_t.hour, start_t.minute)
                end_dt = datetime(year, current_date[0], current_date[1], end_t.hour, end_t.minute)

                if end_dt < start_dt:
                    start_dt = start_dt.replace(hour=start_dt.hour - 12)
                    if start_dt.hour < 0:
                        start_dt = start_dt.replace(day=start_dt.day - 1, hour=start_dt.hour + 24)

                events.append({
                    'summary': f"{group} Workout",
                    'start': start_dt,
                    'end': end_dt,
                    'location': current_location,
                    'description': "\n".join(current_notes)
                })
                current_notes = []
            except:
                current_notes.append(line)
            i += 1
            continue

        current_notes.append(line)
        i += 1

    if current_date:
        flush_day(events, year, current_date, current_location, current_notes)
    return events


def parse_time_str(tstr: str, end_ampm_hint: str = '', debug: bool = False) -> dtime:
    tstr = tstr.strip().upper()
    ampm_match = re.search(r'(AM|PM)', tstr)
    clean = re.sub(r'(AM|PM)', '', tstr, re.IGNORECASE).strip()

    h, m = map(int, clean.split(':'))
    ampm = ''
    if ampm_match:
        ampm = ampm_match.group(0).upper()
        if ampm == 'PM' and h < 12:
            h += 12
        elif ampm == 'AM' and h == 12:
            h = 0
    else:
        # Use end time hint first
        if end_ampm_hint == 'PM' and h <= 12:
            h += 12
            ampm = 'PM (from end)'
        elif end_ampm_hint == 'AM' and h == 12:
            h = 0
            ampm = 'AM (from end)'
        else:
            # Only assume PM for 4–10
            # NEVER assume PM for 11 or 12
            if 4 <= h <= 10:
                h += 12
                ampm = 'PM (assumed)'
            else:
                ampm = 'AM/midday'

    if debug:
        print(f"[DEBUG] Parsed '{tstr}' → {h:02d}:{m:02d} ({ampm})")

    return dtime(h % 24, m)


def flush_day(events, year, date_tuple, location, notes):
    if not notes:
        return
    month, day = date_tuple
    summary = " → ".join(notes[:3]) if len(notes) > 3 else " → ".join(notes)
    events.append({
        'summary': summary or "Special Event",
        'start': datetime(year, month, day, 0, 0),
        'end': datetime(year, month, day, 23, 59, 59),
        'location': location,
        'description': "\n".join(notes)
    })


def generate_ics(events, filename, calendar_name: str, with_addresses: bool = False):
    # Filter past events
    now = datetime.now()
    events = [ev for ev in events if ev['end'] >= now]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"X-WR-CALNAME:{calendar_name}",   # ← Calendar name for proper display
        "PRODID:-//PTAC Calendar Generator//EN",
        "CALSCALE:GREGORIAN",
    ]

    for ev in events:
        loc = ev.get('location', '')
        if with_addresses and loc in ADDRESS_MAP:
            loc = ADDRESS_MAP[loc]

        uid = str(uuid.uuid4())
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{ev['start'].strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{ev['end'].strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{ical_escape(ev['summary'])}",
            f"LOCATION:{ical_escape(loc)}",
            f"DESCRIPTION:{ical_escape(ev['description'])}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"Created: {filename} ({len(events)} future events) → {calendar_name}")


def main():
    args = parse_arguments()

    print("Fetching latest PTAC calendar...")
    raw_text = fetch_page()

    OUTPUT = Path("output")
    OUTPUT.mkdir(exist_ok=True)

    print("Generating files...\n")

    # 1. Full unfiltered
    events = parse_events(raw_text, debug=args.debug)
    generate_ics(events, OUTPUT / "all.ics", "PTAC All Workouts", args.with_addresses)

    # 2. One file per group
    for group in GROUPS:
        group_events = parse_events(raw_text, allowed_groups={group}, debug=args.debug)
        filename = OUTPUT / f"{group}.ics"
        calendar_name = f"PTAC {group} Workouts"
        generate_ics(group_events, filename, calendar_name, args.with_addresses)

    print("\n✅ All files generated successfully!")
    print("📁 Location: ./output/")
    print("   • all.ics")
    print("   • AG1.ics, AG2.ics, AG3.ics, SR.ics, JR.ics, VAR.ics")


if __name__ == '__main__':
    main()
