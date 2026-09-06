import os
import base64
import json
import requests
from nacl import encoding, public
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT")
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
    print(f"Secret '{secret_name}' updated: HTTP {r.status_code}")

if __name__ == "__main__":
    with open("credentials/channel_1_client_secret.json", "rb") as f:
        client_secret_b64 = base64.b64encode(f.read()).decode("utf-8")
        set_secret("CHANNEL_1_CLIENT_SECRET", client_secret_b64)

    with open("tokens/channel_1_token.json", "rb") as f:
        token_b64 = base64.b64encode(f.read()).decode("utf-8")
        set_secret("CHANNEL_1_TOKEN", token_b64)

    print("All secrets successfully updated in GitHub repository!")
