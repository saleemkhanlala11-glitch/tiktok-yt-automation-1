import requests
import re

url = "https://www.youtube.com/watch?v=HATNlPmHKjY"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
resp = requests.get(url, headers=headers)
print("HTTP status:", resp.status_code)

channel_match = re.search(r'"channelId":"([^"]+)"', resp.text)
author_match = re.search(r'"author":"([^"]+)"', resp.text)
owner_match = re.search(r'"ownerChannelName":"([^"]+)"', resp.text)

print("Channel ID:", channel_match.group(1) if channel_match else "None")
print("Author:", author_match.group(1) if author_match else "None")
print("Owner Channel Name:", owner_match.group(1) if owner_match else "None")
