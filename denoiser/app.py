#!/usr/bin/env python3
"""Denoiser: an example tool that takes Loft tokens.

It cleans noise out of a render, and everything else is Loft's: sign-in, the
studio and its projects, paying for each run in the studio's tokens, and
keeping the result in the studio's project. All of that is in loft.py; this
file is the tool and its pages.

    pip install -r requirements.txt
    cp .env.example .env        # then set LOFT_CLIENT_ID
    python app.py

See README.md.
"""

import argparse
import html
import math
import os
import secrets
import time

import cv2
from dotenv import load_dotenv
from flask import Flask, abort, redirect, request, send_file

# .env next to this file, before loft.py reads its settings.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import loft  # noqa: E402
from loft import Loft, LoftRefused  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
WORK = os.path.join(HERE, "work")

app = Flask(__name__)

# The browser holds only a random id; the person's Loft key stays on the
# server. Kept in memory to keep the example short: a real tool keeps these in
# its own session store (and they are lost when this process restarts).
COOKIE = "denoiser_sid"
SESSIONS = {}


def session():
    sid = request.cookies.get(COOKIE)
    if sid not in SESSIONS:
        sid = secrets.token_urlsafe(24)
        SESSIONS[sid] = {"_sid": sid}
    return SESSIONS[sid]


def with_cookie(response, s):
    response.set_cookie(COOKIE, s["_sid"], httponly=True, samesite="Lax")
    return response


# ── the tool ────────────────────────────────────────────────────────────────

def price(path, batch=1):
    """(reserve, charge): a run reserves its estimate and is charged what it
    used. 5 tokens a megapixel to reserve, 4 to charge, per frame."""
    h, w = cv2.imread(path).shape[:2]
    mp = w * h / 1e6
    return math.ceil(mp * 5) * batch, math.ceil(mp * 4) * batch


def denoise(src, dst, strength):
    image = cv2.medianBlur(cv2.imread(src), 3)        # fireflies first
    clean = cv2.fastNlMeansDenoisingColored(image, None, strength, strength + 6, 7, 21)
    cv2.imwrite(dst, clean)


# ── pages ───────────────────────────────────────────────────────────────────

STYLE = """
* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.5 Inter, system-ui, sans-serif; background: #0f1115; color: #e8e9ec; }
a { color: #9fc2ff; }
header { display: flex; align-items: center; gap: 14px; padding: 14px 28px; border-bottom: 1px solid #23262d; }
.logo { font-weight: 700; font-size: 20px; letter-spacing: -0.02em; }
.logo span { color: #7dd3c0; }
.who { margin-left: auto; display: flex; gap: 18px; align-items: center; color: #a9adb6; font-size: 14px; }
.pill { background: #1a1d23; border: 1px solid #2b2f37; border-radius: 999px; padding: 5px 12px; }
main { padding: 28px; max-width: 1500px; margin: 0 auto; }
.hero { max-width: 760px; margin: 110px auto; text-align: center; }
.hero h1 { font-size: 46px; letter-spacing: -0.03em; margin: 0 0 12px; }
.hero p { color: #a9adb6; font-size: 19px; }
.loft-btn { display: inline-flex; align-items: center; gap: 10px; margin-top: 26px; padding: 13px 26px;
            background: #fff; color: #111; border-radius: 10px; font-weight: 600; font-size: 17px;
            text-decoration: none; border: 0; cursor: pointer; }
.loft-btn b { background: #111; color: #fff; border-radius: 6px; padding: 1px 7px; font-size: 13px; }
.accepts { margin-top: 18px; color: #7c818b; font-size: 14px; }
.row { display: flex; gap: 22px; align-items: flex-start; }
.panel { background: #161920; border: 1px solid #23262d; border-radius: 14px; padding: 18px; }
.controls { width: 340px; flex: none; display: flex; flex-direction: column; gap: 14px; }
label { font-size: 13px; color: #a9adb6; display: block; margin-bottom: 4px; }
select, input[type=range] { width: 100%; }
select { background: #0f1115; color: #e8e9ec; border: 1px solid #2b2f37; border-radius: 8px; padding: 8px; font-size: 15px; }
.btn { width: 100%; padding: 12px; border-radius: 10px; border: 0; font-weight: 600; font-size: 16px;
       background: #7dd3c0; color: #0b0d10; cursor: pointer; }
.btn.secondary { background: #262a32; color: #e8e9ec; }
.cost { font-size: 14px; color: #a9adb6; }
.cost b { color: #e8e9ec; }
.frames { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.frames figure { margin: 0; }
.frames img { width: 100%; border-radius: 10px; display: block; }
figcaption { font-size: 13px; color: #a9adb6; margin-top: 6px; }
.notice { border-radius: 12px; padding: 14px 16px; margin-bottom: 18px; font-size: 15px; }
.notice.ok { background: rgba(125,211,192,0.10); border: 1px solid #2f6f62; }
.notice.no { background: rgba(255,120,110,0.10); border: 1px solid #7a3a35; }
.notice small { display: block; color: #a9adb6; margin-top: 4px; }
.steps { font-size: 13px; color: #a9adb6; margin: 6px 0 0; padding-left: 18px; }
pre { background: #0b0d10; border: 1px solid #23262d; border-radius: 12px; padding: 18px; overflow: auto; font-size: 14px; line-height: 1.45; }
"""


def page(body, s=None, title="Denoiser"):
    who = ""
    if s and s.get("loft"):
        org = (s["loft"].get("organization") or {}).get("name") or ""
        who = ("<div class='who'><span class='pill' data-who>%s · signed in with Loft</span>"
               "<a href='/code'>How it uses Loft</a><a href='/sign-out'>Sign out</a></div>") % html.escape(org)
    out = ("<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head>"
           "<body><header><div class='logo'>De<span>noiser</span></div>%s</header><main>%s</main></body></html>"
           % (html.escape(title), STYLE, who, body))
    return out


@app.route("/")
def home():
    s = session()
    if not loft.CLIENT_ID:
        return page("<div class='notice no'><b>Almost there.</b> Set <code>LOFT_CLIENT_ID</code> in "
                    "<code>.env</code> to your tool's client ID (Loft › Developers › your tool › "
                    "Integrate), then restart. See README.md.</div>")
    if not s.get("loft"):
        return with_cookie(app.response_class(page("""
<div class='hero'>
  <h1>Clean renders in seconds.</h1>
  <p>Denoiser removes render noise from your frames, so you can render with fewer samples.
     Pay per frame with your studio's Loft tokens. Results go straight into your Loft project.</p>
  <a class='loft-btn' href='/sign-in' data-signin><b>L</b> Sign in with Loft</a>
  <div class='accepts'>We accept Loft Tokens</div>
</div>""")), s)
    return with_cookie(app.response_class(tool_page(s)), s)


def tool_page(s, result=None, refused=None):
    try:
        status = Loft(s).tokens()
    except LoftRefused as e:
        return page("<div class='notice no' data-notice>%s</div>" % html.escape(str(e)), s)
    sample = os.path.join(SAMPLES, "lamp-room-noisy.png")
    reserve, charge = price(sample)
    projects = "".join("<option value='%s'%s>%s</option>" % (
        html.escape(p["code"]), " selected" if p["code"] == s.get("project") else "", html.escape(p["name"]))
        for p in status["projects"])

    notice = ""
    if refused:
        notice = "<div class='notice no' data-notice><b>Loft said no.</b> %s</div>" % html.escape(refused)
    elif result:
        notice = ("<div class='notice ok' data-notice><b>Done.</b> Charged %d tokens (%d reserved). "
                  "Saved to your Loft project: <a href='%s' target='_top' data-saved>%s › Tools › Denoiser › %s</a>"
                  "</div>") % (result["charged"], result["reserved"], html.escape(result["link"]),
                               html.escape(result["project_name"]), html.escape(result["file"]))

    after = ("<figure data-after><img src='/work/%s'><figcaption>Denoised</figcaption></figure>"
             % html.escape(result["file"])) if result else \
        "<figure data-after><div style='aspect-ratio:1280/714;border:1px dashed #2b2f37;border-radius:10px;" \
        "display:flex;align-items:center;justify-content:center;color:#7c818b'>Result appears here</div></figure>"

    return page("""
%(notice)s
<div class='row'>
  <form class='panel controls' method='post' action='/run' data-controls>
    <div data-tokens>
      <label>%(org)s</label>
      <div class='pill' style='display:inline-block'><b>%(left)s</b> of %(limit)s tokens left this month</div>
    </div>
    <div>
      <label for='project'>Charge and save to project</label>
      <select id='project' name='project' data-project>%(projects)s</select>
    </div>
    <div>
      <label for='strength'>Strength</label>
      <input id='strength' type='range' name='strength' min='3' max='21' value='%(strength)s'>
    </div>
    <div class='cost' data-cost>This frame: <b>%(charge)d tokens</b> (reserves %(reserve)d, charges what it uses)</div>
    <button class='btn' name='batch' value='1' data-run>Denoise frame</button>
    <button class='btn secondary' name='batch' value='120' data-batch>Denoise the whole shot (120 frames)</button>
  </form>
  <div class='frames'>
    <figure data-before><img src='/sample'><figcaption>Render, 16 samples: lamp-room.png</figcaption></figure>
    %(after)s
  </div>
</div>""" % {
        "notice": notice, "org": html.escape((s["loft"].get("organization") or {}).get("name") or ""),
        "left": "{:,}".format(status["month_left"]), "limit": "{:,}".format(status["month_limit"]),
        "projects": projects, "strength": s.get("strength", 9), "charge": charge, "reserve": reserve,
        "after": after}, s)


@app.route("/sign-in")
def sign_in():
    s = session()
    return with_cookie(redirect(loft.sign_in_url(s)), s)


@app.route("/loft/callback")
def callback():
    s = session()
    try:
        loft.finish_sign_in(s, request.args)
    except LoftRefused:
        pass
    return with_cookie(redirect("/"), s)


@app.route("/sign-out")
def sign_out():
    s = session()
    s.pop("loft", None)
    return with_cookie(redirect("/"), s)


@app.route("/run", methods=["POST"])
def run():
    s = session()
    if not s.get("loft"):
        return redirect("/")
    project = request.form.get("project") or ""
    batch = max(1, int(request.form.get("batch") or 1))
    strength = int(request.form.get("strength") or 9)
    s["project"], s["strength"] = project, strength
    sample = os.path.join(SAMPLES, "lamp-room-noisy.png")
    reserve, charge = price(sample, batch)
    run_id = "run-%s" % secrets.token_hex(6)
    client = Loft(s)

    try:
        hold = client.reserve(project, reserve, run_id, "Denoise")  # 1. reserve before it runs
    except LoftRefused as e:
        return with_cookie(app.response_class(tool_page(s, refused=str(e))), s)

    try:
        os.makedirs(WORK, exist_ok=True)
        name = "lamp-room_denoised.png"
        out = os.path.join(WORK, "%s_%s" % (run_id, name))
        denoise(sample, out, strength)                           # 2. the work
        final = os.path.join(WORK, run_id, name)
        os.makedirs(os.path.dirname(final), exist_ok=True)
        os.replace(out, final)
        saved = client.deliver(hold, [final],                    # 3. the result, into the project
                               "Denoised at strength %d" % strength)
        client.charge(hold, charge, "Denoise")                   # 4. charge what it used
    except Exception as e:
        client.release(hold)                                     # failed: give it all back
        return with_cookie(app.response_class(tool_page(s, refused="The run failed: %s" % e)), s)

    status = client.tokens()
    names = {p["code"]: p["name"] for p in status["projects"]}
    app_base = s["loft"]["api_base"][:-len("/api/v1")]
    result = {"charged": charge, "reserved": reserve, "file": os.path.join(run_id, name),
              "project_name": names.get(project, project),
              "link": "%s/%s/asset/%s" % (app_base, project, saved["asset_code"])}
    result["file"] = name
    s["last_file"] = final
    return with_cookie(app.response_class(tool_page(s, result=dict(result, file=name))), s)


@app.route("/sample")
def sample():
    return send_file(os.path.join(SAMPLES, "lamp-room-noisy.png"))


@app.route("/work/<name>")
def work(name):
    s = session()
    path = s.get("last_file")
    if not path or os.path.basename(path) != name:
        abort(404)
    return send_file(path)


@app.route("/code")
def code():
    """loft.py, its two parts side by side: everything this tool knows about Loft."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import PythonLexer
    s = session()
    with open(os.path.join(HERE, "loft.py")) as f:
        source = f.read()
    one = source.index("# ── 1.")
    two = source.index("# ── 2.")
    formatter = HtmlFormatter(style="github-dark", cssclass="code")
    show = lambda text: highlight(text.strip("\n") + "\n", PythonLexer(), formatter)
    lines = source.count("\n")
    body = ("<style>%s .code pre{background:#0b0d10;font-size:13.5px;margin:0} main{max-width:none}</style>"
            "<div style='display:flex;align-items:baseline;gap:14px;margin-bottom:12px'>"
            "<h2 style='margin:0'>loft.py</h2>"
            "<span class='cost'>%d lines: everything Denoiser knows about Loft</span>"
            "<a href='/' style='margin-left:auto'>Back to Denoiser</a></div>"
            "<div style='display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:16px' data-code>"
            "<div data-code-signin>%s</div><div data-code-run>%s</div></div>") % (
        formatter.get_style_defs(".code"), lines, show(source[one:two]), show(source[two:]))
    return with_cookie(app.response_class(page(body, s, "Denoiser · loft.py")), s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 9120)))
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port, threaded=True)
