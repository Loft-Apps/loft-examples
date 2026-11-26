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
    session["loft"] = _token({
        "grant_type": "authorization_code", "code": args["code"], "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI, "code_verifier": session.pop("verifier")})


def _token(form):
    r = requests.post(LOFT + "/oauth/token", data=form)
    body = _json(r)
    if r.status_code >= 400 or "access_token" not in body:
        raise LoftRefused(body.get("error_description") or "Sign-in with Loft failed.",
                          body.get("error", "sign_in_failed"))
    return body


def _json(r):
    try:
        return r.json()
    except ValueError:      # not JSON: a proxy's error page, a timeout ...
        return {"error": "unavailable", "message": "Loft is unavailable. Try again shortly."}


# ── 2. Around each run ─────────────────────────────────────────────────────

class Loft:
    def __init__(self, session):
        self.session = session
        self.me = session["loft"]       # access_token, refresh_token, api_base, organization

    def call(self, method, path, files=None, **kwargs):
        for attempt in (1, 2):
            opened = [("files", open(p, "rb")) for p in files] if files else None
            try:
                r = requests.request(method, self.me["api_base"] + path, files=opened, headers={
                    "Authorization": "Bearer " + self.me["access_token"]}, **kwargs)
            finally:
                for _, f in opened or []:
                    f.close()
            if r.status_code == 401 and attempt == 1:
                self._refresh()
                continue
            body = _json(r)
            if r.status_code >= 400 or "error" in body:
                raise LoftRefused(body.get("message") or "Loft refused", body.get("error", ""))
            return body

    def _refresh(self):
        try:
            new = _token({"grant_type": "refresh_token", "refresh_token": self.me["refresh_token"],
                          "client_id": CLIENT_ID})
        except LoftRefused:
            raise LoftRefused("Your Loft sign-in has expired. Sign in again.", "signed_out")
        self.me.update(new)
        self.session["loft"] = self.me

    def tokens(self):
        """Tokens left this month, and the projects this person may charge."""
        return self.call("GET", "/tokens")

    def reserve(self, project, tokens, run_id, description):
        """Before the work: the most this run could cost. Raises LoftRefused if
        the studio can't or won't pay; then do no work."""
        return self.call("POST", "/tokens/holds", json={
            "project": project, "tokens": tokens, "reference": run_id,
            "description": description})["hold"]

    def deliver(self, hold, paths, note=""):
        """The run's results, all in one call, into the studio's project."""
        return self.call("POST", "/tokens/holds/%s/files" % hold, files=paths, data={"note": note})

    def charge(self, hold, tokens, description=""):
        """What the run actually cost, at most what was reserved."""
        return self.call("POST", "/tokens/holds/%s/charge" % hold,
                         json={"tokens": tokens, "description": description})

    def release(self, hold, description=""):
        """The run failed: give everything back. Never raises, so it can't hide
        the error that made the run fail."""
        try:
            return self.call("POST", "/tokens/holds/%s/release" % hold,
                             json={"description": description})
        except Exception:
            return None     # an unreleased hold is released by Loft after 24 hours
