import sys
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def main():
    if len(sys.argv) < 2:
        print("Usage: python reauth_nobrowser.py <channel_id>")
        sys.exit(1)

    channel_id = sys.argv[1]
    cred_file = os.path.join("credentials", f"{channel_id}_client_secret.json")
    token_file = os.path.join("tokens", f"{channel_id}_token.json")

    if not os.path.exists(cred_file):
        print(f"Error: Client secret file not found at {cred_file}")
        sys.exit(1)

    os.makedirs("tokens", exist_ok=True)

    flow = InstalledAppFlow.from_client_secrets_file(cred_file, scopes=SCOPES)
    flow.redirect_uri = "http://localhost:8088/"
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    
    print(f"AUTH_URL_START: {auth_url} :AUTH_URL_END", flush=True)
    print("Starting local server on port 8088 to capture callback...", flush=True)
    
    creds = flow.run_local_server(
        port=8088,
        prompt="consent",
        access_type="offline",
        open_browser=False
    )

    token_json = creds.to_json()
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(token_json)

    token_data = json.loads(token_json)
    if "refresh_token" in token_data:
        print(f"SUCCESS: Token generated and saved to {token_file} with refresh_token!", flush=True)
    else:
        print(f"WARNING: Token saved to {token_file}, but NO refresh_token found.", flush=True)

if __name__ == "__main__":
    main()
