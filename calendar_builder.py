from ics import Calendar, Event
from pathlib import Path
import json
from scraper import parse
import os #debugging
import logging #debugging
logging.basicConfig(level=logging.DEBUG)

OUTPUT = Path("output")
OUTPUT.mkdir(exist_ok=True)

def build():
    events = parse()
    #events = Component.serialize()
    swimmers = json.load(open("swimmers.json"))
    master = Calendar()
    groups = {}
    swimmers_cal = {}

    for e in events:
        ev = Event()
        logging.debug(f"Event: {ev}")
        if e["type"] == "practice":
            #logging.debug(f"The GitHub reference is: {type}")
            ev.name = f"{e['group']} Practice"
            #logging.debug(f"The GitHub reference is: {group}")
        #else:
            #ev.name = e.get("name","Swim Meet")
        if isinstance(ev.end, str):
            logging.debug(f"Ignore end (str): {ev}")
            continue
        if isinstance(ev.begin, str):
            logging.debug(f"Ignore begin (str): {ev}")
            continue
        #if "VEVENT" in ev.end.casefold():
            #logging.debug(f"Ignore (VEVENT): {ev}")
            #continue
        if ev.begin > ev.end:
            print(f"Error: {ev.name} ends before it starts.")
        # Check for 0-length events
        elif ev.begin == ev.end:
             print(f"Warning: {ev.name} {ev.begin} has 0 duration.")
             # Optional: Fix 0-length event
             ev.end = ev.begin.shift(hours=1)
        ev.begin = e["start"]
        logging.debug(f"Start is: {ev.begin}")
        ev.end = e["end"]
        logging.debug(f"End is: {ev.end}")
        ev.location = e["pool"]
        #logging.debug(f"The GitHub reference is: {location}")
        master.events.add(ev)
        g = e["group"]
        if g not in groups:
            groups[g] = Calendar()
        groups[g].events.add(ev)
        for swimmer,sgroups in swimmers.items():
            if g in sgroups:
                if swimmer not in swimmers_cal:
                    swimmers_cal[swimmer] = Calendar()
                swimmers_cal[swimmer].events.add(ev)

    # subscription feeds
    (OUTPUT/"ptac_master.ics").write_text(str(master))
    for g,c in groups.items():
        (OUTPUT/f"ptac_{g.lower()}.ics").write_text(str(c))

    # import copies for iOS
    (OUTPUT/"ptac_master_import.ics").write_text(str(master))
    for g,c in groups.items():
        (OUTPUT/f"ptac_{g.lower()}_import.ics").write_text(str(c))

    for s,c in swimmers_cal.items():
        (OUTPUT/f"swimmer_{s}.ics").write_text(str(c))

if __name__=="__main__":
    build()
