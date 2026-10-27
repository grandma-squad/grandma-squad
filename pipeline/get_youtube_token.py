"""Run ONCE on your computer to let the app upload to your YouTube channel.

  python pipeline/get_youtube_token.py YOUR_CLIENT_ID YOUR_CLIENT_SECRET

A browser opens; sign in with the Google account that owns the channel and pick the
Grandma Squad channel. The script prints a refresh token to save as the YT_REFRESH_TOKEN secret.
"""
import http.server
import json
import sys
import urllib.parse
import urllib.request
import webbrowser

PORT = 8765
REDIRECT = f"http://localhost:{PORT}"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    cid, secret = sys.argv[1], sys.argv[2]
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent select_account"})
    code = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code["v"] = q.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Done! You can close this tab and go back to the terminal.</h2>")

        def log_message(self, *a):
            pass

    print("Opening your browser... If it does not open, paste this link:\n", url)
    webbrowser.open(url)
    srv = http.server.HTTPServer(("localhost", PORT), H)
    while not code.get("v"):
        srv.handle_request()
    data = urllib.parse.urlencode({"code": code["v"], "client_id": cid, "client_secret": secret,
                                   "redirect_uri": REDIRECT, "grant_type": "authorization_code"}).encode()
    resp = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data))
    if "refresh_token" not in resp:
        sys.exit(f"No refresh token returned: {resp}")
    print("\nYT_REFRESH_TOKEN =\n" + resp["refresh_token"])


if __name__ == "__main__":
    main()
