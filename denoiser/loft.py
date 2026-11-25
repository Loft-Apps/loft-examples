"""Everything Denoiser knows about Loft.

Denoiser has no accounts, no billing and no file storage of its own. Studios
sign in with Loft, each run is paid for in the studio's Loft tokens, and the
results go back into the studio's Loft project.

    1. Sign in with Loft     standard OAuth 2.1 + PKCE
    2. Around each run       reserve tokens, deliver the files, charge what it used
"""

import base64
import hashlib
import os
import secrets
import urllib.parse

import requests

LOFT = os.environ.get("LOFT_URL", "https://app.loftapps.com").rstrip("/")
CLIENT_ID = os.environ.get("LOFT_CLIENT_ID", "")     # from Loft's Developers app
REDIRECT_URI = os.environ.get("APP_URL", "http://localhost:9120").rstrip("/") + "/loft/callback"


class LoftRefused(Exception):
    """Loft said no (out of tokens, over the monthly limit ...). The message
    is written for the person using the tool: show it as it is."""

    def __init__(self, message, error=""):
        super().__init__(message)
        self.error = error


# ── 1. Sign in with Loft ───────────────────────────────────────────────────

def sign_in_url(session):
    """Where the "Sign in with Loft" button goes."""
    session["verifier"] = secrets.token_urlsafe(48)
    session["state"] = secrets.token_urlsafe(16)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(session["verifier"].encode()).digest()).rstrip(b"=").decode()
    return LOFT + "/oauth/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": session["state"]})


def finish_sign_in(session, args):
    """Loft sent the person back: swap the code for their key. The answer
    also says where to call (api_base) and who the studio is."""
    if args.get("error") or args.get("state") != session.pop("state", None):
        raise LoftRefused("Sign-in was cancelled.")
    session["loft"] = requests.post(LOFT + "/oauth/token", data={
        "grant_type": "authorization_code", "code": args["code"], "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI, "code_verifier": session.pop("verifier")}).json()


# ── 2. Around each run ─────────────────────────────────────────────────────

class Loft:
    def __init__(self, session):
        self.session = session
        self.me = session["loft"]       # access_token, refresh_token, api_base, organization

    def call(self, method, path, **kwargs):
        for attempt in (1, 2):
            r = requests.request(method, self.me["api_base"] + path, headers={
                "Authorization": "Bearer " + self.me["access_token"]}, **kwargs)
            if r.status_code == 401 and attempt == 1:
                self._refresh()
                continue
            body = r.json()
            if r.status_code >= 400:
                raise LoftRefused(body.get("message") or "Loft refused", body.get("error", ""))
            return body

    def _refresh(self):
        new = requests.post(LOFT + "/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": self.me["refresh_token"],
            "client_id": CLIENT_ID}).json()
        self.me.update(new)
        self.session["loft"] = self.me

    def tokens(self):
        """Tokens left this month, and the projects this person may charge."""
        return self.call("GET", "/tokens")

    def reserve(self, project, tokens, run_id):
        return self.call("POST", "/tokens/holds", json={
            "project": project, "tokens": tokens, "reference": run_id,
            "description": "Denoise"})["hold"]

    def deliver(self, hold, path, note):
        with open(path, "rb") as f:
            return self.call("POST", "/tokens/holds/%s/files" % hold,
                             files={"files": f}, data={"note": note})

    def charge(self, hold, tokens):
        return self.call("POST", "/tokens/holds/%s/charge" % hold, json={"tokens": tokens})

    def release(self, hold):
        return self.call("POST", "/tokens/holds/%s/release" % hold, json={})
