import time
import requests
from plyer import notification

BACKEND_URL = "http://127.0.0.1:5000/reminder-pop"   # your backend reminder API

def show_toast(msg):
    try:
        notification.notify(
            title="🔔 Reminder",
            message=msg,
            timeout=10,        # notification stays 10 seconds
            app_name="BrainBox Assistant"
        )
    except Exception as e:
        print("Notification Error:", e)

print("✅ Reminder notifier started! Waiting for reminders...\n")

while True:
    try:
        r = requests.get(BACKEND_URL).json()

        if r.get("pop"):
            tasks = r.get("messages", [])
            for t in tasks:
                show_toast(t)

        time.sleep(10)   # check every 10 seconds

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
