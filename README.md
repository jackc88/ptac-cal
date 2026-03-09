# PTAC Calendar Sync

Automatically converts the PTAC GoMotion calendar into clean iOS/Google compatible `.ics` feeds.

Features:

* Scrapes GoMotion calendar
* Creates ICS feeds
* Master calendar
* Group calendars
* Individual swimmer calendars
* Meet detection
* Automatic updates via GitHub Actions
* Google Calendar sync option

## Install

```bash
pip install -r requirements.txt
```

## Run locally

```bash
python calendar_builder.py
```

Generated calendars appear in:

```
output/
```

## Example feeds

```
ptac_master.ics
ptac_ag1.ics
ptac_ag2.ics
ptac_jr.ics
ptac_sr.ics
ptac_var.ics
```

These files can be subscribed to in:

* Apple Calendar
* Google Calendar
* Outlook
* iOS devices

## Automatic updates

GitHub Actions runs the scraper every hour and commits updated calendars automatically.

## iPhone subscription

Open the ICS URL in Safari and tap **Subscribe**.

