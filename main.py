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

# Get environment variables
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# Initialize client (will fail later if token is missing)
try:
    client = WebClient(token=SLACK_BOT_TOKEN)
except Exception as e:
    app.logger.error(f"Failed to initialize Slack client: {e}")
    client = None

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
                TIMEZONE = new_tz
                client.chat_postMessage(channel=channel, text=f"Timezone updated to: {TIMEZONE}")
            except pytz.exceptions.UnknownTimeZoneError:
                client.chat_postMessage(channel=channel, text=f"Error: '{new_tz}' is not a valid timezone. Use format like 'America/New_York', 'China/Shanghai'")
 

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
