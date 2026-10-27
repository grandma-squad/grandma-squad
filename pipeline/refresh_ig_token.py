"""Instagram tokens last 60 days. This prints a fresh one; the monthly workflow saves it as a secret."""
import os
import sys

import requests

r = requests.get("https://graph.instagram.com/refresh_access_token", timeout=60, params={
    "grant_type": "ig_refresh_token", "access_token": os.environ["IG_ACCESS_TOKEN"]})
if r.status_code != 200:
    sys.exit(f"Refresh failed: {r.text[:300]}")
print(r.json()["access_token"])
