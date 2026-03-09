import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
#import datetime
import os #debugging
import logging #debugging

URL = "https://www.gomotionapp.com/team/njptac/page/calendar1/all-groups"

POOLS = ["Denunzio","WAC","MCCC","PMS","Waterworks"]
GROUPS = ["AG1","AG2","AG3","JR","SR","VAR"]

date_pattern = re.compile(r"(\d{1,2})/(\d{1,2})$")
#time_pattern = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*(AM|PM)?",re.I)
time_pattern = re.compile(
    r"(\d{1,2}:\d{2})\s*(AM|PM)?\s*-\s*(\d{1,2}:\d{2})\s*(AM|PM)?",
    re.I
)

def detect_year(month):
    now = datetime.now()
    if month < now.month - 6:
        return now.year + 1
    return now.year

def parse_time(date,t,ampm):
    if not ampm:
        ampm="PM"
    return datetime.strptime(f"{date} {t} {ampm}","%Y-%m-%d %I:%M %p")

def fetch_lines():
    html=requests.get(URL).text
    soup=BeautifulSoup(html,"html.parser")
    text=soup.get_text("\n")
    lines=[l.strip() for l in text.split("\n") if l.strip()]
    return lines

def parse():
    lines=fetch_lines()
    events=[]
    #date_string = datetime.now()
    #current_date=datetime.strptime(date_string, "%Y-%m-%d")
    current_date=None
    current_pool=None
    current_group=None

    for line in lines:
        m=date_pattern.match(line)
        if m:
            month=int(m.group(1))
            day=int(m.group(2))
            year=detect_year(month)
            current_date=f"{year}-{month:02d}-{day:02d}"
            current_pool=None
            continue

        if line in POOLS:
            current_pool=line
            continue

        for g in GROUPS:
            if line.startswith(g):
                current_group=g

        t=time_pattern.search(line)
        if t and current_group and current_date:
            
            # Convert tuple to a list so it's mutable
            #start,end,ampm=t.groups()
            #start_dt = datetime.strptime(start_str, "%H:%M")
            #end_dt = datetime.strptime(end_str, "%H:%M")
            #fmt = "%I:%M" 
            #start_dt = datetime.strptime(start, fmt)
            #end_dt = datetime.strptime(end, fmt)
            #if end_dt > start_dt:
            #    logging.debug(f"Adjusted start to: {start}")
            #    start_dt -= timedelta(hours=12)
                # 3. Pass the adjusted time back to 'start' as a string
            #    start = start_dt.strftime(fmt)
            #    logging.debug(f"CHG: t: {t} g: {current_group} d: {current_date}")
            start, start_ampm, end, end_ampm = t.groups()

            # If only one AM/PM is provided (GoMotion common case)
            if not start_ampm and end_ampm:
                start_ampm = end_ampm
            if not end_ampm and start_ampm:
                end_ampm = start_ampm

            # Default fallback
            if not start_ampm:
                start_ampm = "PM"
            if not end_ampm:
                end_ampm = start_ampm

            start_dt = parse_time(current_date, start, start_ampm)
            end_dt = parse_time(current_date, end, end_ampm)

            # Handle overnight events
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
    
            #events.append({
                #"group":current_group,
                #"pool":current_pool,
                #"start":parse_time(current_date,start,ampm),
                #"end":parse_time(current_date,end,ampm),
                #"type":"practice"
            #})
            events.append({
                "group": current_group,
                "pool": current_pool,
                "start": start_dt,
                "end": end_dt,
                "type": "practice"
            })



        if "Meet" in line or "Championship" in line:
            #events.append({
                #"group":"ALL",
                #"pool":None,
                #"start":datetime.strptime(current_date,"%Y-%m-%d"),
                #"end":datetime.strptime(current_date,"%Y-%m-%d"),
                #"type":"meet",
                #"name":line
            #})
            pass
    return events
