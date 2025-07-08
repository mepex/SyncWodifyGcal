import requests
import datetime
import json

from pytz import timezone, utc
import os.path
import argparse
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

***REMOVED*** = "***REMOVED***"

with open('settings.json', 'r') as file:
    settings = json.load(file)

def is_declined(event: dict) -> bool:
    if 'attendees' in event:
        for a in event['attendees']:
            if a['responseStatus'] == 'declined' and a['self'] == True:
                return True
        return False
    else:
        return False

# https://docs.wodify.com/docs/search#-syntax
def get_wodify_classes() -> dict:
    global settings
    wodify_url = "https://api.wodify.com/v1/classes/search"
    now = datetime.datetime.now().isoformat()
    today = str(datetime.date.today())
    headers = {"accept": "application/json", "x-api-key": ***REMOVED***}
    q = {"q": f"start_date|gte|{today};coach|eq|'{settings['wodify_me']}'", "sort": "start_date"}
    response = requests.get(wodify_url, headers=headers, params=q)
    return json.loads(response.text)

def find_gcal_entry(date: str, description: str) -> dict:
    global settings
    now = datetime.datetime.now(tz=datetime.timezone.utc)



# https://developers.google.com/workspace/calendar/api/v3/reference/events#resource
def make_gcal_entry(tz, wodify_class: dict) -> dict:
    global settings
    starttime = tz.localize(datetime.datetime.strptime(wodify_class['start_date_time'], "%Y-%m-%dT%H:%M:%SZ"))
    endtime = tz.localize(datetime.datetime.strptime(wodify_class['end_date_time'], "%Y-%m-%dT%H:%M:%SZ"))
    event = {
        "summary" : f"{settings["prefix"]}{wodify_class['name']}",
        "location" : wodify_class['location'],
        "start" : {
            "dateTime" : starttime.isoformat(),
        },
        "end" : {
            "dateTime": endtime.isoformat(),
        }
    }
    return event

def find_gcal_entry(events: dict, start: datetime, description: str) -> dict:
    found_entry = None
    for entry in events:
        try:
            gcal_start = datetime.datetime.fromisoformat(entry['start']['dateTime'])
            gcal_iso = gcal_start.isoformat()
            if gcal_start == start and entry['summary'] == description:
                found_entry = entry
                break
        except KeyError as error:
            pass
    return found_entry

def delete_declined(service, events):
    global settings
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        if is_declined(event):
            print(f'Deleting {start} -- {event["summary"]} - DECLINED')
            if not settings['print_only']:
                events_result = service.events().delete(calendarId='primary', eventId=event['id']).execute()
                if events_result:
                    print(events_result)
                time.sleep(0.5)

def delete_cfc_events(service, prefix, events):
    for event in events:
        if prefix in event["summary"]:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(f'Deleting {start} -- {event["summary"]}')
            if not settings['print_only']:
                events_result = service.events().delete(calendarId='primary', eventId=event['id']).execute()
                if events_result:
                    print(events_result)
                time.sleep(0.5)

def main():
    classes = get_wodify_classes()



    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        jan1 = datetime.datetime(year=2025, month=1, day=1).isoformat()
        #print("Getting the upcoming 10 events")
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=200,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
            return

        parser = argparse.ArgumentParser(description="A simple script with command-line arguments.")
        parser.add_argument("--delete-declined", help="Clear GCal of declined events")
        parser.add_argument("--delete-cfc", help="Clear GCal of CFC events")

        args = parser.parse_args()

        if args.delete_declined:
            delete_declined(service, events)
            return
        if args.delete_cfc:
            delete_cfc_events(service, events)
            return

        classtimes = []
        tz = timezone(settings['timezone'])

        for c in classes['classes']:
            dt = c['start_date_time']
            # Force to timezone, all wodify classes are in UTC
            start = tz.localize(datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ"))
            classtimes.append(start)
            name = f"{settings['prefix']}{c['name']}"
            found_entry_next = find_gcal_entry(events, start, name)
            if not found_entry_next:
                print(f"Creating new gcal entry : {start.isoformat()} {name}")
                event = make_gcal_entry(tz, c)
                print(event)
                if not settings['print_only']:
                    event = service.events().insert(calendarId='primary', body=event).execute()
            else:
                print(f"Found existing gcal entry : {start.isoformat()} {name}")



    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    main()