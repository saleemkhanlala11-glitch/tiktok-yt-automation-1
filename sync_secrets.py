import os
import re
import base64
import json
import requests
import subprocess
from nacl import encoding, public
from dotenv import load_dotenv

load_dotenv()

def get_github_pat() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT")
    if token:
        return token
    try:
        remote_url = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
        match = re.search(r"ghp_[a-zA-Z0-9]+", remote_url)
        if match:
            return match.group(0)
    except Exception:
        pass
    return ""

GITHUB_TOKEN = get_github_pat()
REPO = os.getenv("GITHUB_REPOSITORY", "saleemkhanlala11-glitch/tiktok-yt-automation-1")

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN or GH_PAT environment variable is required.")

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Fetch public key for repo
res = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=headers)
res.raise_for_status()
key_data = res.json()
public_key = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder)
key_id = key_data["key_id"]

def set_secret(secret_name, raw_content_b64):
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(raw_content_b64.encode("utf-8"))
    encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")
    
    url = f"https://api.github.com/repos/{REPO}/actions/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_b64,
        "key_id": key_id
    }
    r = requests.put(url, headers=headers, json=payload)
    print(f"Secret '{secret_name}' updated in {REPO}: HTTP {r.status_code}")

if __name__ == "__main__":
    if os.path.exists("credentials/channel_1_client_secret.json"):
        with open("credentials/channel_1_client_secret.json", "rb") as f:
            client_secret_b64 = base64.b64encode(f.read()).decode("utf-8")
            set_secret("CHANNEL_1_CLIENT_SECRET", client_secret_b64)

    if os.path.exists("tokens/channel_1_token.json"):
        with open("tokens/channel_1_token.json", "rb") as f:
            token_b64 = base64.b64encode(f.read()).decode("utf-8")
            set_secret("CHANNEL_1_TOKEN", token_b64)

    print("All secrets successfully synced to GitHub repository!")
