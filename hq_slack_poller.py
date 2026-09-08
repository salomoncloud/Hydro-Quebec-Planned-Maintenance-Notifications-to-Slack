import json
import os
import requests

# Hydro-Québec Laurentides Region ID (Saint-Jérôme = Region 15)
HQ_REGION_URL = (
    "https://pannes.hydroquebec.com/pannes/donnees/v3_0/bis/regions/15.json"
)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
STATE_FILE = "notified_events.json"
TARGET_MUNICIPALITY = "Saint-Jérôme"
TARGET_POSTAL_PREFIX = "J7Y"


def load_notified_events():
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r") as f:
        return set(json.load(f))
    except Exception:
      return set()
  return set()


def save_notified_events(notified_set):
  with open(STATE_FILE, "w") as f:
    json.dump(list(notified_set), f)


def check_hq_maintenance():
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Referer": "https://pannes.hydroquebec.com/pannes/",
  }

  try:
    response = requests.get(HQ_REGION_URL, headers=headers, timeout=15)
    if response.status_code != 200:
      print(f"HQ API returned status {response.status_code}")
      return
    data = response.json()
  except Exception as e:
    print(f"Failed to query HQ endpoint: {e}")
    return

  notified = load_notified_events()

  # Inspect active outages and scheduled interruptions
  events = data.get("pannes", []) + data.get("interruptionPrevue", [])

  for event in events:
    event_id = str(
        event.get("noBillet") or event.get("id") or event.get("code")
    )
    municipality = event.get("municipalite", "")
    postal_code = event.get("codePostal", "")

    # Filter for Saint-Jérôme or J7Y postal area
    if (
        TARGET_MUNICIPALITY.lower() in municipality.lower()
        or postal_code.startswith(TARGET_POSTAL_PREFIX)
    ):
      if event_id and event_id not in notified:
        send_slack_alert(event)
        notified.add(event_id)

  save_notified_events(notified)


def send_slack_alert(event):
  title = event.get("titre") or "Hydro-Québec Service Notice"
  status = event.get("statut") or "Planned Maintenance / Interruption"
  start_time = event.get("heureDebut") or "Pending"
  est_end = event.get("heureFinPrevue") or "TBD"
  affected = event.get("nbClientsAffectes") or "N/A"

  blocks = [
      {
          "type": "header",
          "text": {
              "type": "plain_text",
              "text": "⚡ Hydro-Québec Advisory — YUL (Saint-Jérôme / J7Y 3L8)",
          },
      },
      {
          "type": "section",
          "fields": [
              {"type": "mrkdwn", "text": f"*Event:* {title}"},
              {"type": "mrkdwn", "text": f"*Status:* {status}"},
              {"type": "mrkdwn", "text": f"*Start Time:* {start_time}"},
              {"type": "mrkdwn", "text": f"*Est. Recovery:* {est_end}"},
              {"type": "mrkdwn", "text": f"*Affected Customers:* {affected}"},
              {
                  "type": "mrkdwn",
                  "text": "*Location:* Saint-Jérôme (Enovum STJ01 Zone)",
              },
          ],
      },
      {
          "type": "actions",
          "elements": [{
              "type": "button",
              "text": {
                  "type": "plain_text",
                  "text": "View HQ Outage Map ↗",
              },
              "url": "https://pannes.hydroquebec.com/pannes/",
          }],
      },
  ]

  if SLACK_WEBHOOK_URL:
    requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks})
  else:
    print("SLACK_WEBHOOK_URL not set. Outputting payload:")
    print(json.dumps(blocks, indent=2))


if __name__ == "__main__":
  check_hq_maintenance()
