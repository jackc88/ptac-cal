#!/usr/bin/env python3
"""
PTAC Calendar Generator
- Exits early if website content has not changed (content hash)
- Automatically forces regeneration if any ICS file is missing or empty
- Writes short timestamped debug lines to run.log
- Denunzio address: DeNunzio Pool, Faculty Road
- Start time AM/PM chosen so duration < 6 hours
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, time as dtime, timezone, timedelta
import re
import uuid
import argparse
import sys
import hashlib
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

HASH_FILE = Path("last_content_hash.txt")
LOG_FILE = Path("run.log")


def log(msg: str):
    """Append a short timestamped line to run.log and also print it."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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
    parser.add_argument('--debug', action='store_true', default=False, help='Verbose debug output')
    parser.add_argument('--force', action='store_true', help='Ignore hash and always regenerate')
    return parser.parse_args()


def fetch_page():
    url = 'https://www.gomotionapp.com/team/njptac/page/calendar1/all-groups'
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        log(f"Fetch failed: {e}")
        sys.exit(1)


def get_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ics_files_ok() -> bool:
    """Return True only if all expected ICS files exist and have content."""
    expected = ["all.ics", "all-day.ics"] + [f"{g}.ics" for g in GROUPS]
    output_dir = Path("output")

    if not output_dir.exists():
        log("output/ directory missing")
        return False

    for name in expected:
        f = output_dir / name
        if not f.exists():
            log(f"Missing ICS file: {name}")
            return False
        if f.stat().st_size == 0:
            log(f"Empty ICS file: {name}")
            return False
    return True


def has_changed(raw_text: str, force: bool = False) -> bool:
    current_hash = get_content_hash(raw_text)
    log(f"Content hash: {current_hash[:16]}...")

    if force:
        log("Force regeneration requested")
        HASH_FILE.write_text(current_hash)
        return True

    if HASH_FILE.exists():
        previous_hash = HASH_FILE.read_text().strip()
        if current_hash == previous_hash:
            log("No content changes detected")
            return False
        log("Content has changed since last run")
    else:
        log("No previous hash found (first run)")

    HASH_FILE.write_text(current_hash)
    return True


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
            i += 1
            continue

        if not current_date:
            i += 1
            continue

        loc_m = re.match(r'^[A-Z][a-zA-Z& ]{2,}$', line)
        if loc_m and not re.search(r'\d', line):
            loc = loc_m.group(0).strip()
            if loc.lower() in {
                "august training", "group", "gym and swim",
                "dryland only!", "suit fitting!", "labor day", "no practices!"
            }:
                i += 1
                continue
            if current_notes:
                flush_day(events, year, current_date, current_location, current_notes, only_all_day, debug)
            current_location = loc
            current_notes = []
            i += 1
            continue

        # Group workout or pure time line
        workout_m = re.search(
            r'([A-Z0-9]+)\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*([AP]M)?',
            line, re.IGNORECASE
        )
        pure_time_m = re.search(
            r'^(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*([AP]M)?$',
            line, re.IGNORECASE
        )

        if workout_m or pure_time_m:
            if only_all_day:
                i += 1
                continue

            if workout_m:
                group = workout_m.group(1).upper()
                start_str = workout_m.group(2)
                end_str = workout_m.group(3)
                end_ampm = (workout_m.group(4) or '').upper()
            else:
                group = "Workout"
                start_str = pure_time_m.group(1)
                end_str = pure_time_m.group(2)
                end_ampm = (pure_time_m.group(3) or '').upper()

            if allowed_groups and group not in allowed_groups and group != "Workout":
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

                events.append({
                    'summary': f"PTAC {group} Workout" if group != "Workout" else "PTAC Workout",
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

    log("Starting PTAC calendar sync")

    print("Fetching latest PTAC calendar...")
    raw_text = fetch_page()
    log(f"Fetched {len(raw_text)} characters")

    # Automatically force if any ICS file is missing or empty
    force_needed = args.force or not ics_files_ok()

    if not has_changed(raw_text, force=force_needed):
        log("Done (no changes)")
        sys.exit(0)

    OUTPUT = Path("output")
    OUTPUT.mkdir(exist_ok=True)

    log("Generating ICS files...")
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

    log("Generation complete")
    print("\nAll files generated in ./output/")


if __name__ == '__main__':
    main()
