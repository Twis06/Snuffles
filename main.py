import os
import hmac
import hashlib
import time
from datetime import datetime
from flask import Flask, request, jsonify
from slack_sdk.web import WebClient
import pytz

app = Flask(__name__)

TIMEZONE = "America/Chicago"

# Get environment variables with validation
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

if not SLACK_SIGNING_SECRET or not SLACK_BOT_TOKEN:
    raise ValueError("Missing required environment variables: SLACK_SIGNING_SECRET or SLACK_BOT_TOKEN")

client = WebClient(token=SLACK_BOT_TOKEN)

def verify_slack_request(req):
    timestamp = req.headers.get("X-Slack-Request-Timestamp")
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{req.get_data().decode('utf-8')}"
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    slack_signature = req.headers.get("X-Slack-Signature")

    return hmac.compare_digest(my_signature, slack_signature)

###########################
# Health check endpoint
###########################
@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

###########################
# Main slack messaging code 
###########################
@app.post("/slack/events")
def slack_events():
    # Signature check first (required even for challenge)
    if not verify_slack_request(request):
        app.logger.error(f"Signature verification failed")
        app.logger.error(f"Headers: {dict(request.headers)}")
        return jsonify({"error": "invalid signature"}), 403

    data = request.json
    
    # Verification challenge
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    event = data.get("event", {})

    # Avoid bot replying to itself
    if event.get("subtype") == "bot_message":
        return jsonify({"ok": True})

    # Handle @snuffles mentions
    if event.get("type") == "app_mention":
        text = event.get("text", "").lower()
        channel = event["channel"]

        if "hi" in text or "hello" in text: #test function
            client.chat_postMessage(channel=channel, text="Hi there! I am Snuffles.")
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
                global TIMEZONE
                TIMEZONE = new_tz
                client.chat_postMessage(channel=channel, text=f"Timezone updated to: {TIMEZONE}")
            except pytz.exceptions.UnknownTimeZoneError:
                client.chat_postMessage(channel=channel, text=f"Error: '{new_tz}' is not a valid timezone. Use format like 'America/New_York', 'China/Shanghai'")
 

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
