from ics import Calendar, Event
from pathlib import Path
import json
from scraper import parse

OUTPUT = Path("output")
OUTPUT.mkdir(exist_ok=True)

def build():
    events = parse()
    swimmers = json.load(open("swimmers.json"))
    master = Calendar()
    groups = {}
    swimmers_cal = {}

    for e in events:
        ev = Event()
        if e["type"] == "practice":
            ev.name = f"{e['group']} Practice"
        else:
            ev.name = e.get("name","Swim Meet")
        ev.begin = e["start"]
        ev.end = e["end"]
        ev.location = e["pool"]
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
