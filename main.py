import requests
import datetime
import json

from pytz import timezone
import os.path
import argparse
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import smtplib
from email.message import EmailMessage

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
with open(f'{script_directory}/settings.json', 'r') as file:
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
    print(now)
    today = str(datetime.date.today())
    headers = {"accept": "application/json", "x-api-key": settings["wodify_api_key"]}
    found = []
    for i in range(1,4):
        q = {"q": f"start_date|gte|{today};program_name|in|{{'CrossFit', 'Olympic Weightlifting'}}", "sort": "start_date", "page": i}
        response = requests.get(wodify_url, headers=headers, params=q)
        r_obj = json.loads(response.text)
        #print(response.url)
        for c in r_obj['classes']:
            id = c['id']
            url = f"https://api.wodify.com/v1/classes/{id}"
            response = requests.get(url, headers=headers)
            obj2 = json.loads(response.text)
            coaches = obj2['coaches']
            if coaches:
                coach = f"{coaches[0]['coach']}"
            else:
                coach = ""
            if coach == settings["wodify_me"]:
                dt = c['start_date_time']
                # Force to timezone, all Wodify classes are in UTC
                found.append({'name': c['name'], 'start_date_time': c['start_date_time'], 'end_date_time': c['end_date_time'],'location': c['location'] })
                name = f"{settings['prefix']}{c['name']}"
    print(f"Found {len(found)} classes")
    return found



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
            if gcal_start == start and description in entry['summary']:
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

def delete_wodify_events(service, prefix, events):
    deleted = 0
    for event in events:
        if prefix in event["summary"]:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(f'Deleting {start} -- {event["summary"]}')
            if not settings['print_only']:
                events_result = service.events().delete(calendarId='primary', eventId=event['id']).execute()
                deleted += 1
                if events_result:
                    print(events_result)
                time.sleep(0.5)
    print(f'Deleted {deleted} events')

def main():
    try:
        classes = get_wodify_classes()

        """Shows basic usage of the Google Calendar API.
        Prints the start and name of the next 10 events on the user's calendar.
        """
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(f"{script_directory}/token.json"):
            creds = Credentials.from_authorized_user_file(f"{script_directory}/token.json", SCOPES)
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
            with open(f"{script_directory}/token.json", "w") as token:
                token.write(creds.to_json())

        try:
            service = build("calendar", "v3", credentials=creds)
            tz = timezone(settings['timezone'])
            # Call the Calendar API
            now = datetime.datetime.now(tz=tz)
            # get_wodify_classes gets all classes starting from today
            midnight_today = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, 0, tzinfo=tz)
            #print(now.isoformat())
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=midnight_today.isoformat(),
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

            parser = argparse.ArgumentParser(description="Sync wodify coaching events to Google Calendar")
            parser.add_argument("--delete-declined", help="Clear GCal of declined events")
            parser.add_argument("--delete-wodify-events", help=f"Clear GCal of '{settings['prefix']}' events")

            args = parser.parse_args()

            if args.delete_declined:
                delete_declined(service, events)
                return
            if args.delete_wodify_events:
                delete_wodify_events(service, events)
                return

            classtimes = []
            tz = timezone(settings['timezone'])

            #
            #  First, add Wodify classes to Gcal that don't already exist
            #
            created = 0
            #for c in classes['classes']:
            for c in classes:
                dt = c['start_date_time']
                # Force to timezone, all Wodify classes are in UTC
                start = tz.localize(datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ"))
                classtimes.append(start.isoformat())
                name = f"{settings['prefix']}{c['name']}"
                found_entry_next = find_gcal_entry(events, start, name)
                if not found_entry_next:
                    print(f"New GCal event : {start.isoformat()} {name}")
                    event = make_gcal_entry(tz, c)
                    #print(event)
                    if not settings['print_only']:
                        event = service.events().insert(calendarId='primary', body=event).execute()
                        time.sleep(0.5)
                        created += 1
                else:
                    pass
                    #print(f"Found existing GCal event : {start.isoformat()} {name}")
            print(f"Created {created} new GCal events")

            #
            # Last, check for Wodify entries in GCal that aren't in Wodify and delete them
            #
            deleted = 0
            for event in events:
                try:
                    gcal_start = datetime.datetime.fromisoformat(event['start']['dateTime']).isoformat()
                except KeyError as error:
                    continue
                if settings["prefix"] in event["summary"] and gcal_start not in classtimes:
                    print(f"Deleting : {gcal_start} {event["summary"]}")
                    if not settings['print_only']:
                        events_result = service.events().delete(calendarId='primary', eventId=event['id']).execute()
                        deleted += 1
                        if events_result:
                            print(events_result)
            print(f"Deleted {deleted} GCal events")


        except HttpError as error:
            print(f"An error occurred: {error}")
    except Exception as e:
        f = open(f'{script_directory}/error.log', 'a')
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        f.write(f'{now} {e}\n')
        f.close()



if __name__ == "__main__":
    main()