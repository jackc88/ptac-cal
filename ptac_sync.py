#!/usr/bin/env python3
"""
PTAC Calendar Generator - Final Fixed Version
- Correctly parses 11:45 AM / 6:30 PM etc.
- Separates timed workouts and all-day events
- Proper calendar names
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, time as dtime, timezone
import re
import uuid
import argparse
import sys
from pathlib import Path

# ==================== CONFIG ====================
ADDRESS_MAP = {
    "Denunzio": "Stadium Dr, Princeton, NJ 08540",
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
                        help='Convert locations to full street addresses')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Show debug output')
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
    clean = re.sub(r'(AM|PM)', '', tstr, re.IGNORECASE).strip()

    try:
        h_str, m_str = clean.split(':')
        h = int(h_str)
        m = int(m_str or '0')
    except:
        if debug:
            print(f"[DEBUG] Time split failed: '{tstr}'")
        raise

    if ampm_match:
        ampm = ampm_match.group(0).upper()
        if ampm == 'PM' and h < 12:
            h += 12
        elif ampm == 'AM' and h == 12:
            h = 0
    else:
        # Only assume PM for typical evening hours (4-10). 11 and 12 stay as AM/midday.
        if 4 <= h <= 10:
            h += 12

    if debug:
        print(f"[DEBUG] Parsed '{tstr}' → {h:02d}:{m:02d}")

    return dtime(h % 24, m)


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

        # Date detection
        date_m = re.match(r'^(\*?\*?)?(\d{1,2})/(\d{1,2})(\*?\*?)?$', line)
        if date_m:
            if current_date:
                flush_day(events, year, current_date, current_location, current_notes, only_all_day, debug)
            month, day = int(date_m.group(2)), int(date_m.group(3))
            current_date = (month, day)
            current_location = ""
            current_notes = []
            i += 1
            continue

        if not current_date:
            i += 1
            continue

        # Location
        loc_m = re.match(r'^[A-Z][a-zA-Z& ]{2,}$', line)
        if loc_m and not re.search(r'\d', line):
            if current_notes:
                flush_day(events, year, current_date, current_location, current_notes, only_all_day, debug)
            current_location = loc_m.group(0).strip()
            current_notes = []
            i += 1
            continue

        # Workout detection - improved to catch "AG3 11:45-2:00PM", "AG3 Zones - 6:30 - 8:30 PM", etc.
        workout_m = re.search(r'([A-Z0-9]+).*?(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*([AP]M)?', line)
        if workout_m:
            if only_all_day:
                i += 1
                continue

            group = workout_m.group(1).upper()
            start_str = workout_m.group(2)
            end_str = workout_m.group(3)
            ampm = workout_m.group(4) or ''

            if allowed_groups and group not in allowed_groups:
                i += 1
                continue

            try:
                start_t = parse_time_str(start_str, debug=debug)
                end_t = parse_time_str(end_str, debug=debug)

                start_dt = datetime(year, current_date[0], current_date[1], start_t.hour, start_t.minute)
                end_dt = datetime(year, current_date[0], current_date[1], end_t.hour, end_t.minute)

                # Fix invalid time order (most common bug)
                if end_dt < start_dt:
                    if debug:
                        print(f"[DEBUG] Invalid order detected – forcing start to AM for {group}")
                    start_dt = start_dt.replace(hour=start_dt.hour - 12)
                    if start_dt.hour < 0:
                        start_dt = start_dt.replace(day=start_dt.day - 1, hour=start_dt.hour + 24)

                duration_hours = (end_dt - start_dt).total_seconds() / 3600
                if debug:
                    print(f"[DEBUG] Final event: {group} {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')} @ {current_location} (duration: {duration_hours:.1f} h)")

                events.append({
                    'summary': f"{group} Workout",
                    'start': start_dt,
                    'end': end_dt,
                    'location': current_location,
                    'description': line
                })
                current_notes = []
            except Exception as e:
                if debug:
                    print(f"[DEBUG] Parse error on '{line}': {e}")
                current_notes.append(line)
            i += 1
            continue

        # All other lines are notes/all-day
        current_notes.append(line)
        i += 1

    if current_date:
        flush_day(events, year, current_date, current_location, current_notes, only_all_day, debug)
    return events


def flush_day(events, year, date_tuple, location, notes, only_all_day: bool, debug: bool):
    if not notes or (not only_all_day and len(notes) == 0):
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
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = [ev for ev in events if ev['start'].date() >= now.date()]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"X-WR-CALNAME:{calendar_name}",
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
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
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
    print(f"Created: {filename} ({len(events)} events) → {calendar_name}")


def main():
    args = parse_arguments()

    print("Fetching latest PTAC calendar...")
    raw_text = fetch_page()

    OUTPUT = Path("output")
    OUTPUT.mkdir(exist_ok=True)

    print("Generating files...\n")

    # 1. Everything (timed + all-day)
    events = parse_events(raw_text, debug=args.debug)
    generate_ics(events, OUTPUT / "all.ics", "PTAC All Events", args.with_addresses)

    # 2. Per group - timed workouts only
    for group in GROUPS:
        group_events = parse_events(raw_text, allowed_groups={group}, only_all_day=False, debug=args.debug)
        filename = OUTPUT / f"{group}.ics"
        calendar_name = f"PTAC {group} Workouts"
        generate_ics(group_events, filename, calendar_name, args.with_addresses)

    # 3. All-day events only
    all_day_events = parse_events(raw_text, only_all_day=True, debug=args.debug)
    generate_ics(all_day_events, OUTPUT / "all-day.ics", "PTAC All-Day Events & Meets", args.with_addresses)

    print("\nAll files generated in ./output/")


if __name__ == '__main__':
    main()
