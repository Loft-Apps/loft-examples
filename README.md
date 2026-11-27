# Loft examples: tools that take Loft tokens

Working apps that use **Pay with Loft**. Studios sign in to your tool with
their Loft account, pay for each run with their studio's Loft tokens, and get
the results straight into their Loft project. You don't build accounts,
billing, invoices or storage.

**Using an AI coding assistant?** Tell it:

> Look at github.com/Loft-Apps/loft-examples and add Pay with Loft to my app.

It reads [AGENTS.md](AGENTS.md), asks you what each thing your app does should
cost, and wires in the rest. You do one step yourself: register the tool in
Loft and paste its client ID.

| Example | Language | What it shows |
|---|---|---|
| [denoiser](denoiser/) | Python (Flask) | Sign in with Loft, pick a frame from Loft, reserve → run → deliver → charge, refusals, the monthly limit |

Each example's Loft integration is one small file (`loft.py` in Denoiser).
Copy it into your own tool.

## How it works

1. **Register your tool** in Loft: sign in (or sign up) at
   `https://app.loftapps.com`, go to `https://app.loftapps.com/user/developer`,
   click **Register a tool**, and give it your return address (for example `https://yourtool.com/loft/callback`).
   It works in your own organization straight away, so you can build and test.
   From then on, **Developers** is in your organization's app menu.
   Other studios can use it once Loft has reviewed it.
2. **A studio enables it once.** The first time someone from a studio clicks
   **Sign in with Loft**, the studio's owner or an admin chooses which
   projects your tool may charge and a monthly token limit.
3. **Each artist signs in as themselves.** Your tool gets a key that acts as
   that person, for your tool only: it can reserve and charge tokens, read the
   files the person picks for it, and deliver files. Nothing else in Loft.
4. **Around each run**, your tool calls Loft three or four times:

```
pick     POST /tokens/picks                   optional: the person chooses input files in Loft
reserve  POST /tokens/holds                   before the work: Loft says yes or no
deliver  POST /tokens/holds/<hold>/files      the results, into the studio's project
charge   POST /tokens/holds/<hold>/charge     what the run used (never more than reserved)
release  POST /tokens/holds/<hold>/release    instead of charge, if the run didn't happen
```

Your tool sets its own prices. If a studio thinks a charge is wrong it can
dispute it in Loft; you see the dispute in Developers and can refund it.

## Sign in with Loft

Standard OAuth 2.1, authorization code with PKCE (S256). There is no client
secret: your client ID and your registered return address identify your tool.

| | |
|---|---|
| Authorize | `GET https://app.loftapps.com/oauth/authorize?response_type=code&client_id=…&redirect_uri=…&code_challenge=…&code_challenge_method=S256&state=…` |
| Token | `POST https://app.loftapps.com/oauth/token` (form: `grant_type=authorization_code`, `code`, `client_id`, `redirect_uri`, `code_verifier`) |
| Refresh | `POST https://app.loftapps.com/oauth/token` (form: `grant_type=refresh_token`, `refresh_token`, `client_id`) |
| Discovery | `https://app.loftapps.com/.well-known/oauth-authorization-server` |

The token response tells you where to call and who the customer is:

```json
{
  "access_token": "…",
  "refresh_token": "…",
  "token_type": "Bearer",
  "expires_in": 2592000,
  "scope": "loft",
  "api_base": "https://app.loftapps.com/<organization>/<app>/api/v1",
  "organization": {
    "code": "…",
    "name": "Northlight Animation",
    "contact": { "name": "Alex Chen", "email": "alex@northlight.example" }
  }
}
```

`contact` is the studio's contact for your tool: its owner, unless the studio
named someone else. Send every call to `api_base` with
`Authorization: Bearer <access_token>`. On a 401, refresh and retry once.

The artist stays private: you see the studio, not who in it ran your tool.
`GET /tokens` gives you `artist`, a stable id for that person, for your tool
only.

## The token API

All paths are under `api_base`. Bodies are JSON except file delivery.

**`GET /tokens`**: what this person may still charge.

```json
{ "vendor": "…", "organization": "…", "artist": "art_…", "wallet": 4610,
  "month_limit": 300, "month_used": 12, "month_left": 288,
  "projects": [ { "code": "JOB-…", "name": "The Keeper's Light" } ] }
```

**`POST /tokens/holds`** `{project, tokens, reference, description}`: reserve
before the run. `reference` is your own id for the run (letters, digits,
`. _ : -`, up to 80): reserving again with the same reference returns the same
hold, so retries are safe. At most 100,000 tokens per hold. A hold not
charged or released within 24 hours is released.
Returns `{hold, tokens, project}`.

**`POST /tokens/holds/<hold>/files`**: multipart, one or more `files`, an
optional `note`, and optionally `inputs`: the codes of picked files the
results were made from (repeat the field, or comma-separated), so Loft records
the lineage. Each must have been picked for your tool in the run's project. The files are checked into the studio's project (library
**Tools**, a folder named after your tool) as the artist's work, made with
your tool. Returns `{asset_code, project, items: [{code, name, version}]}`.
The files are in Loft at `<api_base without /api/v1>/<project>/asset/<asset_code>`:
link the person there.

### Files from the studio's project: picks

Your tool never browses a studio's project. It asks the person to pick:

**`POST /tokens/picks`** `{project, kind, return_to, state, multiple}`: `kind`
is `"image"`, `"video"`, `"audio"` or `""` (any); `return_to` must be on the
same site as one of your registered return addresses; `multiple` defaults to
true. Returns `{pick, url, project, kind, expires}`. Send the person's browser
to `url`: Loft shows them the project's published takes. When they're done,
Loft sends them to `return_to?pick=<pick>&state=<state>`, or with
`error=cancelled`. They have an hour to choose.

**`GET /tokens/picks/<pick>`**: `{pick, status, project, files: [{code, name,
asset, library, version, status}]}`. `status` is `open` (not chosen yet),
`picked`, `cancelled` or `expired`.

**`GET /tokens/files/<code>`**: a picked file's bytes. Your tool can download
what was picked for a day, while the file stays published, and nothing else.

**`POST /tokens/holds/<hold>/charge`** `{tokens, description}`: charge what the
run used, at most what was reserved; the rest goes back. Charging again
returns the first result. Returns `{hold, charged, returned, replayed}`.

**`POST /tokens/holds/<hold>/release`** `{description}`: the run didn't happen;
everything goes back.

### When Loft says no

A refusal is JSON with a stable `error` code and a `message` written for the
person using your tool. Show the message as it is.

| Status | `error` | Meaning |
|---|---|---|
| 402 | `insufficient_tokens` | The studio's wallet can't cover it |
| 402 | `monthly_limit` | Over what's left of the studio's monthly limit for your tool |
| 402 | `run_limit` | More than the studio lets your tool charge in one run |
| 402 | `budget` | Over a project budget or the person's allowance |
| 403 | `not_enabled` | The studio hasn't enabled your tool (or turned it off) |
| 403 | `project_not_allowed` | Not one of the projects the studio allowed |
| 403 | `paused` | The studio paused your tool for this person |
| 403 | `vendor_pending` | Your tool is waiting for Loft's review (works only in your own organization) |
| 404 | `no_such_hold` | No such reservation for this person |
| 404 | `no_such_pick` | No such pick for this person |
| 404 / 400 | `not_picked` | That file wasn't picked for your tool, the pick expired, or it's no longer published |
| 409 | `hold_closed` | Already charged or released |
| 429 | `too_fast` | Your tool is reserving faster than Loft allows; try again later |
| 400 | `more_than_reserved` / `bad_request` | Fix the request |
| 503 | `unavailable` | Try again shortly |

## License

MIT. See [LICENSE](LICENSE).
