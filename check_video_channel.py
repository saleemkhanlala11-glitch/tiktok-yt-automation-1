import requests
import re
import json

url = "https://www.youtube.com/watch?v=0VtBrEaGiMo"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
resp = requests.get(url, headers=headers)
print("HTTP status:", resp.status_code)

channel_match = re.search(r'"channelId":"([^"]+)"', resp.text)
author_match = re.search(r'"author":"([^"]+)"', resp.text)
title_match = re.search(r'"title":"([^"]+)"', resp.text)
owner_match = re.search(r'"ownerChannelName":"([^"]+)"', resp.text)

print("Channel ID:", channel_match.group(1) if channel_match else "None")
print("Author:", author_match.group(1) if author_match else "None")
print("Owner Channel Name:", owner_match.group(1) if owner_match else "None")
print("Title:", title_match.group(1) if title_match else "None")

# Also check YouTube channel @einepeperoni-y8m
resp_ch = requests.get("https://www.youtube.com/@einepeperoni-y8m", headers=headers)
ch_id = re.search(r'"channelId":"([^"]+)"', resp_ch.text)
print("Target Channel @einepeperoni-y8m ID:", ch_id.group(1) if ch_id else "None")
