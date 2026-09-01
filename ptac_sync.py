def choose_best_start(start_str: str, end_dt: datetime, year: int, month: int, day: int, debug: bool = False):
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

    # Fallback
    start_t = parse_time_str(start_str, debug=debug)
    return datetime(year, month, day, start_t.hour, start_t.minute)
