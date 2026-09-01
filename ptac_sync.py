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


def choose_best_start(start_str: str, end_dt: datetime, year: int, month: int, day: int, debug: bool = False):
    """
    If start time has no AM/PM, try both possibilities and pick the one
    that results in a duration less than 6 hours.
    """
    start_has_ampm = bool(re.search(r'(AM|PM)', start_str, re.IGNORECASE))

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

    candidates = []
    for force_pm in [False, True]:
        try:
            clean = re.sub(r'(AM|PM)', '', start_str, flags=re.IGNORECASE).strip()
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

    valid = [c for c in candidates if 0 < c[1] < 6]
    if valid:
        best = min(valid, key=lambda x: abs(x[1] - 2.0))
        if debug:
            print(f"[DEBUG] Chose {'PM' if best[2] else 'AM'} start → {best[0].strftime('%I:%M %p')} (duration {best[1]:.1f}h)")
        return best[0]

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

        date_m = re.search(r'(\d{1,2})/(\d{1,2})', line)
        if date_m:
            if current_date:
                flush_day(events, year, current_date, current_location, current_notes, only_all_day, debug)
            month, day = int(date_m.group(1)), int(date_m.group(2))
            current_date = (month, day)
            current_location = ""
            current_notes = []
            if debug:
                print(f"[DEBUG] New date: {month}/{day}")
            i += 1
            continue

        if not current_date:
            i += 1
            continue

        loc_m = re.match(r'^[A-Z][a-zA-Z& ]{2,}$', line)
        if loc_m and not re.search(r'\d', line):
            if current_notes:
                flush_day(events, year, current_date, current_location, current_notes, only_all_day, debug)
            current_location = loc_m.group(0).strip()
            current_notes = []
            if debug:
                print(f"[DEBUG] Location: {current_location}")
            i += 1
            continue

        workout_m = re.search(
            r'([A-Z0-9]+).*?(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*([AP]M)?',
            line, re.IGNORECASE
        )
        if workout_m:
            if only_all_day:
                i += 1
                continue

            group = workout_m.group(1).upper()
            start_str = workout_m.group(2)
            end_str = workout_m.group(3)
            end_ampm = (workout_m.group(4) or '').upper()

            if allowed_groups and group not in allowed_groups:
                i += 1
                continue

            try:
                end_t = parse_time_str(end_str + (' ' + end_ampm if end_ampm else ''), debug=debug)
                end_dt = datetime(year, current_date[0], current_date[1], end_t.hour, end_t.minute)

                start_dt = choose_best_start(
                    start_str, end_dt,
                    year, current_date[0], current_date[1],
                    debug=debug
                )

                duration = (end_dt - start_dt).total_seconds() / 3600
                if duration < 0:
                    end_dt += timedelta(days=1)
                    duration = (end_dt - start_dt).total_seconds() / 3600

                if debug:
                    print(f"[DEBUG] Final: {group} {start_dt.strftime('%I:%M %p')} → {end_dt.strftime('%I:%M %p')} "
                          f"@ {current_location} ({duration:.1f}h)")

                events.append({
                    'summary': f"PTAC {group} Workout",
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
        'summary': f"PTAC {summary}",
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
        loc_key = loc
        for key in ADDRESS_MAP:
            if key.lower() in loc.lower():
                loc_key = key
                break

        if with_addresses and loc_key in ADDRESS_MAP:
            loc = ADDRESS_MAP[loc_key]

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

    events = parse_events(raw_text, debug=args.debug)
    generate_ics(events, OUTPUT / "all.ics", "PTAC All Events", args.with_addresses)

    for group in GROUPS:
        group_events = parse_events(raw_text, allowed_groups={group}, only_all_day=False, debug=args.debug)
        filename = OUTPUT / f"{group}.ics"
        calendar_name = f"PTAC {group} Workouts"
        generate_ics(group_events, filename, calendar_name, args.with_addresses)

    all_day_events = parse_events(raw_text, only_all_day=True, debug=args.debug)
    generate_ics(all_day_events, OUTPUT / "all-day.ics", "PTAC All-Day Events & Meets", args.with_addresses)

    print("\nAll files generated in ./output/")


if __name__ == '__main__':
    main()
