import os
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from slack_sdk.web import WebClient
import pytz
import requests
from icalendar import Calendar

app = Flask(__name__)

TIMEZONE = "America/Chicago"
CALENDAR_URL = "https://calendar.google.com/calendar/ical/075a102c47c915f5617b04d1d9b947c302f33e8a848567712ad3e3461e8206c9%40group.calendar.google.com/public/basic.ics"

# Get environment variables
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# Initialize client (will fail later if token is missing)
try:
    client = WebClient(token=SLACK_BOT_TOKEN)
except Exception as e:
    app.logger.error(f"Failed to initialize Slack client: {e}")
    client = None

def get_calendar_events(days=7):
    """Fetch calendar events from iCal feed"""
    try:
        response = requests.get(CALENDAR_URL, timeout=10)
        response.raise_for_status()
        
        cal = Calendar.from_ical(response.content)
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        end_date = now + timedelta(days=days)
        
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                dtstart = component.get('dtstart').dt
                summary = str(component.get('summary', 'No title'))
                
                # Convert to timezone-aware datetime if needed
                if isinstance(dtstart, datetime):
                    if dtstart.tzinfo is None:
                        dtstart = tz.localize(dtstart)
                    else:
                        dtstart = dtstart.astimezone(tz)
                    
                    # Only include future events within the date range
                    if now <= dtstart <= end_date:
                        events.append({
                            'start': dtstart,
                            'summary': summary
                        })
        
        # Sort by start time
        events.sort(key=lambda x: x['start'])
        return events
    except Exception as e:
        print(f"Error fetching calendar: {e}")
        return None

def verify_slack_request(req):
    """Verify that the request is from Slack"""
    timestamp = req.headers.get("X-Slack-Request-Timestamp")
    slack_signature = req.headers.get("X-Slack-Signature")
    
    if not timestamp or not slack_signature:
        app.logger.warning("Missing Slack signature headers")
        return False
    
    try:
        # Check timestamp is recent (within 5 minutes)
        if abs(time.time() - int(timestamp)) > 60 * 5:
            app.logger.warning(f"Request timestamp too old: {timestamp}")
            return False
    except (ValueError, TypeError) as e:
        app.logger.warning(f"Invalid timestamp: {timestamp}, error: {e}")
        return False

    if not SLACK_SIGNING_SECRET:
        app.logger.error("SLACK_SIGNING_SECRET not configured")
        return False

    sig_basestring = f"v0:{timestamp}:{req.get_data().decode('utf-8')}"
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, slack_signature)

###########################
# Health check endpoint
###########################
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

###########################
# Main slack messaging code 
###########################
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    
    # Handle URL verification challenge BEFORE signature check
    # (Slack doesn't sign the initial challenge request)
    if "challenge" in data:
        app.logger.info("Responding to Slack URL verification challenge")
        return jsonify({"challenge": data["challenge"]})
    
    # Signature check for all other events
    if not verify_slack_request(request):
        app.logger.error(f"Signature verification failed")
        app.logger.error(f"Headers: {dict(request.headers)}")
        return jsonify({"error": "invalid signature"}), 403

    event = data.get("event", {})

    # Avoid bot replying to itself
    if event.get("subtype") == "bot_message":
        return jsonify({"ok": True})

    # Handle @snuffles mentions
    if event.get("type") == "app_mention":
        global TIMEZONE
        text = event.get("text", "").lower()
        channel = event["channel"]
        
        app.logger.info(f"Received app_mention: {text}")

        try:
            if "hi" in text or "hello" in text: #test function
                response = client.chat_postMessage(channel=channel, text="Hi there! I am Snuffles.")
                app.logger.info(f"Sent greeting response: {response['ok']}")
            if "date" in text or "time" in text or "day" in text: #test time function
                try:
                    tz = pytz.timezone(TIMEZONE)
                    now = datetime.now(tz)
                    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S %Z")
                    client.chat_postMessage(channel=channel, text=f"The current date and time is: {formatted_time}")
                except pytz.exceptions.UnknownTimeZoneError:
                    client.chat_postMessage(channel=channel, text=f"Error: Invalid timezone '{TIMEZONE}'")
            if "timezone" in text:
                new_tz = text.split("timezone")[-1].strip()
                try:
                    pytz.timezone(new_tz)
                    TIMEZONE = new_tz
                    client.chat_postMessage(channel=channel, text=f"Timezone updated to: {TIMEZONE}")
                except pytz.exceptions.UnknownTimeZoneError:
                    client.chat_postMessage(channel=channel, text=f"Error: '{new_tz}' is not a valid timezone. Use format like 'America/New_York', 'China/Shanghai'")
            
            # Calendar commands
            if "next event" in text:
                events = get_calendar_events(days=30)
                if events is None:
                    client.chat_postMessage(channel=channel, text="Sorry, I couldn't fetch the calendar.")
                elif len(events) == 0:
                    client.chat_postMessage(channel=channel, text="No upcoming events found.")
                else:
                    event = events[0]
                    time_str = event['start'].strftime("%A, %B %d at %I:%M %p")
                    client.chat_postMessage(channel=channel, text=f"📅 Next event: *{event['summary']}*\n🕐 {time_str}")
            
            elif "today" in text and ("event" in text or "calendar" in text):
                events = get_calendar_events(days=1)
                if events is None:
                    client.chat_postMessage(channel=channel, text="Sorry, I couldn't fetch the calendar.")
                elif len(events) == 0:
                    client.chat_postMessage(channel=channel, text="No events today.")
                else:
                    msg = "📅 *Today's events:*\n"
                    for event in events:
                        time_str = event['start'].strftime("%I:%M %p")
                        msg += f"• {time_str} - {event['summary']}\n"
                    client.chat_postMessage(channel=channel, text=msg)
            
            elif "this week" in text and ("event" in text or "calendar" in text):
                events = get_calendar_events(days=7)
                if events is None:
                    client.chat_postMessage(channel=channel, text="Sorry, I couldn't fetch the calendar.")
                elif len(events) == 0:
                    client.chat_postMessage(channel=channel, text="No events this week.")
                else:
                    msg = "📅 *This week's events:*\n"
                    for event in events:
                        time_str = event['start'].strftime("%a %b %d, %I:%M %p")
                        msg += f"• {time_str} - {event['summary']}\n"
                    client.chat_postMessage(channel=channel, text=msg)
            
            elif "calendar" in text and "next event" not in text:
                events = get_calendar_events(days=7)
                if events is None:
                    client.chat_postMessage(channel=channel, text="Sorry, I couldn't fetch the calendar.")
                elif len(events) == 0:
                    client.chat_postMessage(channel=channel, text="No upcoming events in the next 7 days.")
                else:
                    msg = "📅 *Upcoming events (next 7 days):*\n"
                    for event in events:
                        time_str = event['start'].strftime("%a %b %d, %I:%M %p")
                        msg += f"• {time_str} - {event['summary']}\n"
                    client.chat_postMessage(channel=channel, text=msg)
        except Exception as e:
            app.logger.error(f"Error handling app_mention: {e}")
            app.logger.error(f"Client: {client}, Token set: {bool(SLACK_BOT_TOKEN)}")
 

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
