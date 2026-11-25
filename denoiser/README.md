# Denoiser

A small web app that cleans render noise out of a frame and takes Loft tokens
for it. Denoiser and its maker, Grainless Labs, are fictional; the Loft side
is real.

It has no accounts, no billing and no storage of its own:

- **Sign in with Loft** is its only door.
- Each run **reserves** tokens first, **delivers** the result into the
  studio's Loft project, then **charges** what it used (reserve 5 tokens a
  megapixel, charge 4). If anything fails, it **releases** the reservation.
- **Denoise the whole shot** asks for 120 frames, more than a small monthly
  limit allows, to show Loft refusing a run before anything happens.

Everything Denoiser knows about Loft is in [`loft.py`](loft.py), about 100
lines. The app shows it at `/code`.

## Run it

You need Python 3.10 or newer and a Loft account.

1. **Register the tool.** Sign in to Loft, go to
   `https://app.loftapps.com/user/developer`, click **Register a tool**, and set its return address to
   `http://localhost:9120/loft/callback`. Open the tool and copy its
   **client ID** from **Integrate**.
2. **Configure and start it:**

   ```sh
   cd denoiser
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env          # set LOFT_CLIENT_ID
   python app.py
   ```

3. Open `http://localhost:9120` and click **Sign in with Loft**. As the owner
   of your organization you enable the tool (pick a project and a monthly
   limit), then you're back in Denoiser, signed in.
4. Click **Denoise frame**. The result is in your project's **Tools**
   library, and the run shows in **Developers**.

Until Loft has reviewed your tool, it works only in your own organization,
which is all you need to build and test.

## What to copy

- `loft.py`: sign-in (`sign_in_url`, `finish_sign_in`) and the `Loft` client
  (`tokens`, `reserve`, `deliver`, `charge`, `release`, refresh on 401).
- The order in `app.py`'s `run()`: reserve → work → deliver → charge, and
  release on failure.

What's here only to keep the example short: sessions live in memory (a real
tool keeps the person's Loft key in its own session store), and the "work" is
two OpenCV filters on a sample image.
