# Adding Loft to an app: instructions for coding agents

You are here because someone asked you to "add Loft", "add Pay with Loft" or
"look at loft-examples and add the good stuff" to their app. Follow this page.
The person doesn't want to hear about OAuth, holds or endpoints. They want their
tool to take Loft tokens and put its results in their studio's Loft project.

What they get, without building any of it: sign-in for every studio and artist,
per-run payment in Loft tokens, limits and budgets the studio controls, results
stored and versioned in the studio's project, and a dashboard of who uses the
tool and what they're owed. **Do not build** accounts, passwords, billing,
invoices, usage tracking or file storage. Loft is all of those.

## 1. Ask the person one thing: what costs what

Read their app first. List every action a person can run in it that does real
work (a render, a conversion, a generation, a batch job), then ask, in plain
words, what each should cost. Suggest prices so they only have to say yes or
adjust:

> Your app does three things people would pay for. A Loft token is worth about
> a cent. I'd suggest:
>
> | Action | Price |
> |---|---|
> | Clean up one frame | 4 tokens a frame |
> | Upscale an image | 10 tokens an image |
> | Make a contact sheet | free |
>
> Change any of these, or say "go" and I'll use them.

Price by the unit the work grows with (per frame, per megapixel, per minute,
per image), in whole tokens. Free actions need no Loft calls and no sign-in.

Most prices are known before the run starts (5 frames at 4 tokens = 20): then
you reserve and charge the same number. Reserve more than you charge only when
the cost depends on what the run finds (it stops early, it skips frames that
are already clean): reserve the most it could cost, charge what it used.

Don't ask anything else. Decide the rest yourself from the app.

## 2. Wire it in

Copy [`denoiser/loft.py`](denoiser/loft.py) into the app. If the app isn't
Python, port it: it is about 130 lines and the port is mechanical. Keep the
same functions and behaviour: `sign_in_url`, `finish_sign_in`, and a client
with `tokens`, `reserve(project, tokens, run_id, description)`,
`deliver(hold, paths, note)`, `charge(hold, tokens, description)` and
`release(hold, description)`, refresh-and-retry-once on a 401, any reply that
isn't JSON treated as "unavailable", and a `release` that never throws. In a
port, build a multipart body afresh for the retry; a sent one can't be reused.
Read [`README.md`](README.md) only if you need an endpoint's exact shape.

Then, in the app:

1. **Sign in.** A **Sign in with Loft** button (to `sign_in_url`), a callback
   route at `<app url>/loft/callback` (calls `finish_sign_in`), and sign-out.
   Signing in replaces any login the app had. Use Loft's answer for the
   studio's name (`organization.name`).
2. **Keep the Loft key on the server.** Store what `finish_sign_in` returns
   (access token, refresh token, `api_base`) in the server-side session or the
   app's database, never in browser storage or a client-side bundle. All Loft
   calls are made from server code (Next.js: route handlers or server actions;
   serverless: keep it in the app's DB keyed by the session). If the app has
   no sessions, add the framework's standard ones with a store that survives a
   restart (its database, Redis, or a file store). An in-memory store is fine
   for trying it out; if you use one, tell the person that everyone is signed
   out when the app restarts.
3. **Show what's left.** After sign-in, call `tokens()`: show `month_left`
   and let the person pick one of `projects` (that's where results go and what
   gets charged). Remember the pick.
4. **Wrap every paid action**, exactly in this order:

   ```
   hold = reserve(project, most_it_could_cost, run_id)   # Loft says yes or no BEFORE any work
   try:
       do the work
       deliver(hold, all result files, note)              # one call, into the studio's project
       charge(hold, what_it_actually_cost)                # never more than reserved
   except anything:
       release(hold)                                      # a failed run costs nothing
   ```

   - `run_id`: a new unique id per run (e.g. `run-<random hex>`). Retrying with
     the same id is safe; it never reserves twice.
   - Reserve the most the run could cost (the full batch); charge what it used.
   - Deliver before charge, so a run that failed to save its result isn't paid.
   - Description: a few words for the action ("Upscale 2x"). The studio sees it
     on its bill.
   - After it's done, link the person to their result:
     `api_base` without `/api/v1`, then `/<project>/asset/<asset_code>`
     (`asset_code` is in `deliver`'s reply).
5. **When Loft says no, show its message as it is.** `reserve` (and the others)
   raise with a message written for the person ("This would take you over
   Northlight's monthly limit for your tool"). Show it where the result would
   have been. Don't rephrase it and don't retry it.

Inputs: a tool can't read files from the studio's Loft project yet. Keep
whatever upload or input the app already has.

## 3. The one step only the person can do

Registering the tool needs their Loft login. Tell them exactly this, filling
in their app's address:

> 1. Go to https://app.loftapps.com/user/developer (sign up if you don't have
>    a Loft account) and click **Register a tool**.
> 2. Give it your app's name, and this return address:
>    `<app url>/loft/callback` (add `http://localhost:<port>/loft/callback`
>    too while you test).
> 3. Open the tool, copy the **client ID** under **Integrate**, and paste it
>    as `LOFT_CLIENT_ID` in `.env`.

Add `LOFT_CLIENT_ID`, `LOFT_URL=https://app.loftapps.com` and `APP_URL` to the
app's `.env.example`. There is no client secret.

The tool works in their own organization straight away; other studios can use
it once Loft has reviewed it. They don't need to do anything for the review.

## 4. Check it works

Run the app and walk the person through it (or do it yourself if you can drive
a browser):

- [ ] **Sign in with Loft** → Loft asks to enable the tool (pick a project, a
      monthly limit) → back in the app, signed in, tokens left shown.
- [ ] Run a paid action → it succeeds, and the result is in the project's
      **Tools** library in Loft, under the tool's name.
- [ ] **Developers** in Loft shows the run and the tokens charged.
- [ ] Set the monthly limit below one run's price (Loft › Outside Tools ›
      Change) and run again → the app shows Loft's refusal and does no work.
- [ ] Make a run fail on purpose (give it an input it can't read, such as a
      text file renamed `.png`) → the app shows the error, nothing is charged.

## Reference

- [`denoiser/`](denoiser/): a complete working app (Flask). `app.py`'s `run()`
  is the pattern for a paid action; `price()` is how it prices one.
- [`README.md`](README.md): every endpoint, response and refusal code.
