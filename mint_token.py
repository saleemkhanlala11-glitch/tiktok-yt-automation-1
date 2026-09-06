import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

cred_file = "credentials/channel_1_client_secret.json"
token_file = "tokens/channel_1_token.json"
os.makedirs("tokens", exist_ok=True)
os.makedirs("scratch", exist_ok=True)

flow = InstalledAppFlow.from_client_secrets_file(
    cred_file,
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
    redirect_uri="http://localhost:8080/"
)

auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
with open("scratch/auth_url.txt", "w", encoding="utf-8") as f:
    f.write(auth_url)
print("AUTH_URL_SAVED", flush=True)

creds = flow.run_local_server(
    port=8080,
    prompt="consent",
    access_type="offline",
    open_browser=False,
    authorization_prompt_message="AUTH_URL_START: {url} :AUTH_URL_END\n"
)

with open(token_file, "w", encoding="utf-8") as f:
    f.write(creds.to_json())

with open("scratch/done.txt", "w", encoding="utf-8") as f:
    f.write("DONE")

print("TOKEN_MINTED_SUCCESSFULLY", flush=True)

