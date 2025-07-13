# SyncWodifyGcal

Will sync coaching entries from Wodify to GCal. Requires Google Authorization to create and delete
calendar events.

## Features

- Will check for Wodify events in GCal, and add or delete events as necessary
- Separate command-line option to delete declined events (Wodify sometimes creates a lot of these)
- Separate command-line option to delete all events with the given prefix

## Installation

After the script is installed, modify the settings.json file.  
- Add your Wodify API key for 'wodify_api_key'
- Include the name you use in the Wodify system as 'wodify_me'
- Add a prefix- this string will be used at the beginning of all Google Calendar events created, so they can
be properly identified (and possibly deleted later)
- Include your timezone- Wodify uses UTC, but Google will use your local timezone, the script will account 
for that
- Specify which Google Calendar you want to access via 'calendar'. 
- Use the 'print_only' setting to only query the databases, and print out what will happen without actually
modifying the calendar.  Recommended to run set to 'true' initally before settings to 'false', which will 
your calendar

