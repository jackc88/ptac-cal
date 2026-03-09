from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json
from scraper import parse

SCOPES=["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID="primary"

def sync():
    creds=Credentials.from_authorized_user_file("token.json",SCOPES)
    service=build("calendar","v3",credentials=creds)
    events=parse()
    for e in events:
        body={
            "summary":f"{e['group']} Practice",
            "location":e["pool"],
            "start":{"dateTime":e["start"].isoformat()},
            "end":{"dateTime":e["end"].isoformat()}
        }
        service.events().insert(
            calendarId=CALENDAR_ID,
            body=body
        ).execute()

if __name__=="__main__":
    sync()
