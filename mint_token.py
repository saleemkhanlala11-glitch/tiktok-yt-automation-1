import sys
import os
import json
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
cred_file = "credentials/channel_1_client_secret.json"
token_file = "tokens/channel_1_token.json"

os.makedirs("tokens", exist_ok=True)

flow = InstalledAppFlow.from_client_secrets_file(cred_file, scopes=SCOPES, redirect_uri="http://localhost:8080/")
auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")

print(f"AUTH_URL_START: {auth_url} :AUTH_URL_END", flush=True)

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            code = query["code"][0]
            try:
                flow.fetch_token(code=code)
                creds = flow.credentials
                with open(token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authentication successful! YouTube Token saved. You can close this window now.</h1>")
                print("TOKEN_SAVED_SUCCESSFULLY", flush=True)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"<h1>Error exchanging token: {e}</h1>".encode("utf-8"))
                print(f"ERROR_FETCHING_TOKEN: {e}", flush=True)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>No authorization code received.</h1>")
            print("ERROR_NO_CODE_RECEIVED", flush=True)

server = HTTPServer(("localhost", 8080), CallbackHandler)
print("SERVER_READY", flush=True)
server.handle_request()
