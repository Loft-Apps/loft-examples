# Film Look (no Loft yet)

A small web app that gives a frame a film grade and grain: warm print, cool
night or bleach bypass. Film Look and its maker are fictional.

It is the **starting point** for adding Pay with Loft. As it is, it has its
own upload, no sign-in, no payment, and its results are only a download. The
tutorial "Connect your tool to Loft" turns it into a tool studios pay for in
Loft tokens, by asking a coding agent:

> Look at github.com/Loft-Apps/loft-examples and add Pay with Loft to my app.

The agent follows [AGENTS.md](../AGENTS.md). For a finished app to compare
with, see [denoiser](../denoiser/).

## Run it

You need Python 3.10 or newer.

```
cd filmlook
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:9130. Leave the file empty to try it on the sample
frame.
