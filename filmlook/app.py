#!/usr/bin/env python3
"""Film Look: give a frame a film grade and grain.

A small example app with NO Loft in it yet: its own upload, no sign-in, no
payment, results only as a download. It is the starting point for adding
Pay with Loft; see README.md.

    pip install -r requirements.txt
    python app.py               # http://localhost:9130
"""

import argparse
import html
import os
import secrets

import cv2
import numpy as np
from flask import Flask, abort, redirect, request, send_file

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "samples", "lamp-room.jpg")
WORK = os.path.join(HERE, "work")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

# ── the tool ────────────────────────────────────────────────────────────────

LOOKS = {
    # name: (shadow tint, highlight tint, saturation, contrast), tints in BGR
    "warm": ((-0.03, 0.0, 0.03), (-0.09, 0.0, 0.08), 1.0, 1.08),
    "cool": ((0.08, 0.03, -0.03), (0.05, 0.01, -0.04), 0.85, 1.05),
    "bleach": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.45, 1.25),
}


def film_look(src, dst, look, grain):
    """Grade the frame with a look, then add film grain (0 to 10)."""
    shadow, highlight, saturation, contrast = LOOKS[look]
    image = cv2.imread(src)
    if image is None:
        raise ValueError("That file isn't an image Film Look can read.")
    img = image.astype(np.float32) / 255.0
    luma = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[..., None]
    img = luma + (img - luma) * saturation                      # saturation
    img = (img - 0.5) * contrast + 0.5                          # contrast
    img = img + (1 - luma) * np.array(shadow) + luma * np.array(highlight)   # split tone
    if grain:
        rng = np.random.default_rng()
        noise = rng.normal(0, 0.012 * grain, img.shape[:2])[..., None]
        img = img + noise * (1.2 - luma)                        # more in the shadows
    cv2.imwrite(dst, np.clip(img * 255, 0, 255).astype(np.uint8))


# ── pages ───────────────────────────────────────────────────────────────────

STYLE = """
* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.5 Inter, system-ui, sans-serif; background: #111014; color: #ecebee; }
header { display: flex; align-items: center; padding: 14px 28px; border-bottom: 1px solid #26242b; }
.logo { font-weight: 700; font-size: 20px; letter-spacing: -0.02em; }
.logo span { color: #f0b46c; }
main { padding: 28px; max-width: 1500px; margin: 0 auto; }
.row { display: flex; gap: 22px; align-items: flex-start; }
.panel { background: #19171d; border: 1px solid #26242b; border-radius: 14px; padding: 18px; }
.controls { width: 340px; flex: none; display: flex; flex-direction: column; gap: 14px; }
label { font-size: 13px; color: #aaa7b0; display: block; margin-bottom: 4px; }
select, input[type=range], input[type=file] { width: 100%; }
select { background: #111014; color: #ecebee; border: 1px solid #312e37; border-radius: 8px; padding: 8px; font-size: 15px; }
.btn { width: 100%; padding: 12px; border-radius: 10px; border: 0; font-weight: 600; font-size: 16px;
       background: #f0b46c; color: #141217; cursor: pointer; }
.frames { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.frames figure { margin: 0; }
.frames img { width: 100%; border-radius: 10px; display: block; }
figcaption { font-size: 13px; color: #aaa7b0; margin-top: 6px; }
.notice { border-radius: 12px; padding: 14px 16px; margin-bottom: 18px; background: rgba(255,120,110,0.10); border: 1px solid #7a3a35; }
.empty { aspect-ratio: 16/9; border: 1px dashed #312e37; border-radius: 10px; display: flex;
         align-items: center; justify-content: center; color: #7d7a84; }
a { color: #f0b46c; }
"""


def page(body):
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Film Look</title><style>%s</style></head>"
            "<body><header><div class='logo'>Film <span>Look</span></div></header><main>%s</main></body></html>"
            % (STYLE, body))


def options(current):
    return "".join("<option value='%s'%s>%s</option>" % (k, " selected" if k == current else "",
                                                          {"warm": "Warm print", "cool": "Cool night",
                                                           "bleach": "Bleach bypass"}[k])
                   for k in LOOKS)


def tool_page(source=None, result=None, error=None, look="warm", grain=4):
    before = ("<img src='/files/%s'>" % html.escape(source)) if source else \
        "<img src='/sample'>"
    after = ("<img src='/files/%s'><figcaption><a href='/files/%s' download>Download</a></figcaption>"
             % (html.escape(result), html.escape(result))) if result else \
        "<div class='empty'>Result appears here</div>"
    notice = "<div class='notice'>%s</div>" % html.escape(error) if error else ""
    return page("""
%(notice)s
<div class='row'>
  <form class='panel controls' method='post' action='/run' enctype='multipart/form-data'>
    <div>
      <label for='image'>Frame (leave empty for the sample)</label>
      <input id='image' type='file' name='image' accept='image/*'>
      <input type='hidden' name='source' value='%(source)s'>
    </div>
    <div>
      <label for='look'>Look</label>
      <select id='look' name='look'>%(options)s</select>
    </div>
    <div>
      <label for='grain'>Grain</label>
      <input id='grain' type='range' name='grain' min='0' max='10' value='%(grain)d'>
    </div>
    <button class='btn'>Apply look</button>
  </form>
  <div class='frames'>
    <figure>%(before)s<figcaption>Before</figcaption></figure>
    <figure>%(after)s</figure>
  </div>
</div>""" % {"notice": notice, "source": html.escape(source or ""), "options": options(look),
             "grain": grain, "before": before, "after": after})


@app.route("/")
def home():
    return tool_page()


@app.route("/run", methods=["POST"])
def run():
    look = request.form.get("look") if request.form.get("look") in LOOKS else "warm"
    grain = max(0, min(10, int(request.form.get("grain") or 4)))
    os.makedirs(WORK, exist_ok=True)

    upload = request.files.get("image")
    source = os.path.basename(request.form.get("source") or "")
    if upload and upload.filename:
        ext = os.path.splitext(upload.filename)[1].lower() or ".png"
        source = "in-%s%s" % (secrets.token_hex(6), ext)
        upload.save(os.path.join(WORK, source))
    src = os.path.join(WORK, source) if source else SAMPLE

    result = "look-%s-%s.png" % (look, secrets.token_hex(6))
    try:
        film_look(src, os.path.join(WORK, result), look, grain)
    except Exception as e:
        return tool_page(source=source or None, error=str(e), look=look, grain=grain)
    return tool_page(source=source or None, result=result, look=look, grain=grain)


@app.route("/sample")
def sample():
    return send_file(SAMPLE)


@app.route("/files/<name>")
def files(name):
    path = os.path.join(WORK, os.path.basename(name))
    if not os.path.exists(path):
        abort(404)
    return send_file(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 9130)))
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port, threaded=True)
