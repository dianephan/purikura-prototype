# Purikura Booth ✨

A collaborative photo-decorating booth that demos LaunchDarkly's release, remediation, and targeting features **visually.**

The story: the booth is upgrading its sticker renderer to the new **Sparkle
Engine**. The `sparkleStickerEngine` feature flag controls who gets it, and
every toggle reaches all open browsers instantly — mid-session, no reload.


| Exercise requirement                                         | Where it lives in this app                                                        |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Feature flag around a feature                                | `sparkleStickerEngine` wraps the sparkle sticker pack (`app.py`)                  |
| Instant release/rollback listener                            | SDK `flag_tracker` listener → Socket.IO broadcast (`on_flag_change` in `app.py`)  |
| Remediate via trigger (could this be a kill switch instead?) | "🚨 emergency de-sparkle" button or `curl -X POST $LD_TRIGGER_URL`                |
| Context attributes                                           | `artist` contexts with `plan`, `country`, `device`                                |
| Individual targeting                                         | `diane-artist` is targeted into the sparkle engine despite being on the free plan |
| Rule-based targeting                                         | rule: `plan is "free"` → classic stickers; fallthrough → sparkle                  |
| Extra credit: experimentation                                | every sticker placement calls `track("sticker-placed", context)`                  |




## Prerequisites

- **Python 3.10+** (`python3 --version`)
- A LaunchDarkly account with a **server-side SDK key**
- macOS/Linux/Windows — no other services needed; state is in-memory



tl;dr try the live demo: 

[https://purikura-booth.onrender.com/](https://purikura-booth.onrender.com/)

## Setup

```bash
git clone <this repo>
cd purikura-booth
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then edit .env
```

In `.env`, set `LD_SDK_KEY` to your **server-side** SDK key
(LaunchDarkly → Account settings → Projects → your project → copy the key
for the environment you'll demo in).

### Recreating the flag (fresh LaunchDarkly account)

Create a **boolean** flag with key exactly `sparkleStickerEngine`
(the key the code evaluates — see `FLAG_KEY` in `app.py`), variations
`true` (sparkle) / `false` (classic), off variation `false`. Then configure
targeting in your demo environment:

1. **Segments** (Segments → Create segment): `free-tier` with rule
  `artist` `plan` is one of `free`, and `premium-tier` with rule
   `artist` `plan` is one of `pro`
2. **Individual target:** context kind `artist`, key `diane-artist` → serve `true`
3. **Rule:** if context matches segment `free-tier` → serve `false`
4. **Default (fallthrough):** serve `true` (this is what `premium-tier` gets)
5. Leave the flag **off** — turning it on is the first demo beat

There is also a second flag, `spookyStickerPack`, showing **segment reuse**:
boolean, rule "matches segment `premium-tier`" → `true`, fallthrough `false`,
and it starts **on** — premium artists have the 🎃 pack unlocked from the
moment the page loads, before the sparkle demo even begins.

The four demo personas (defined in `app.py`) and what they should get while
the flag is ON:


| persona key    | plan | expected  | why                                |
| -------------- | ---- | --------- | ---------------------------------- |
| `diane-artist` | free | ✨ sparkle | individual target (beats the rule) |
| `mika-pro`     | pro  | ✨ sparkle | fallthrough                        |
| `sam-free`     | free | classic   | free-tier segment rule             |
| `rin-pro`      | pro  | ✨ sparkle | fallthrough                        |




### Optional: the remediation trigger

The 🚨 button is off until you create a trigger on **your** `sparkleStickerEngine` flag and paste its URL into `.env`. The URL is a secret for that flag in one environment. It has to be the same project and environment as the `LD_SDK_KEY` you set above. Someone else's URL turns off their flag, so each account creates its own.

1. In LaunchDarkly, open the project you copied the SDK key from.
2. Switch the environment picker (top of the page) to that same environment.
3. Open the flag `**sparkleStickerEngine**`.
4. Go to **Settings → Triggers → Add trigger**.
5. Type: **Generic trigger**. Action: **Turn flag targeting off**. Save.
6. Copy the URL LaunchDarkly shows. It looks like `https://app.launchdarkly.com/webhook/triggers/...` and appears when the trigger is created. If you already created one and closed that dialog, open the trigger and **reset the URL** to get a new copy. The previous URL stops working.
7. In `.env`, add the line and save:
  ```bash
   LD_TRIGGER_URL=https://app.launchdarkly.com/webhook/triggers/...
  ```
8. Restart `python app.py`. The server reads `.env` at startup, and the 🚨 button enables only when `LD_TRIGGER_URL` is set.

The same URL works from a terminal:

```bash
curl -X POST "$LD_TRIGGER_URL"
```



## Run

```bash
python app.py
# → Purikura Booth running at http://localhost:5055
```



## Camera & gallery

It's a real photobooth now: tap **📷 camera** (the browser will ask
permission), strike a pose, and **📸 snap!** — your photo becomes the shared
backdrop for *everyone* in the booth, mirrored like a proper purikura
machine, and the canvas resets for fresh decorating. When the masterpiece
is ready, **💾 save** composites the photo + stickers (sparkle and spooky
glows included) into a JPEG and adds it to the **gallery ♡** strip below the
booth, visible to every visitor. Click a thumbnail to open it full size.

Notes:

- Camera access requires HTTPS or localhost — both `python app.py` locally
and Render qualify. If you deny permission, the pastel backdrop stays.
- Gallery files are saved to a local `gallery/` folder (gitignored). On
Render's free tier the disk is **ephemeral**: the gallery resets on each
deploy or restart. For a persistent gallery, attach a Render disk or
upload to S3 (see `SYSTEM_DESIGN.md` — this is exactly the blob-storage
box in the diagram).



## Optional Diane Bit: Deploy to Render (share the booth across machines)

The repo ships a `render.yaml` blueprint, so the booth can run on
[Render](https://render.com) and be opened from any machine — which makes
the collaborative canvas *actually* collaborative across laptops and phones.

1. Push this repo to GitHub (remember: `.env` is gitignored and stays local).
2. In Render: **New → Blueprint**, pick the repo. Render reads `render.yaml`
  and proposes the `purikura-booth` web service.
3. When prompted, paste your **server-side SDK key** as `LD_SDK_KEY`
  (`LD_TRIGGER_URL` is optional — add it later to arm the 🚨 button).
4. Deploy. Your booth lives at `https://purikura-booth.onrender.com`
  (or similar). Open it on two different devices, pick different personas,
   and decorate the same photo together.

Notes:

- **Free tier sleeps** after ~15 idle minutes; the first visit after a nap
takes ~30–60 s to cold-start. Fine for demos — just warm it up before one.
- Render supports **WebSockets** on all plans, so the instant flag toggles
work exactly like local.
- The server still reaches LaunchDarkly over its streaming connection, so
toggling a flag in the dashboard updates every connected device at once —
the same demo, now multi-machine.
- The URL is public: anyone who has it can place stickers. For a take-home
demo that's a feature, not a bug.



## Extra credit: experimentation

A live experiment — **Sparkle Engine Engagement** — runs on
`sparkleStickerEngine` in the `test` environment, measuring the custom
metric `**sticker-placed**` (stickers per user, higher is better). Real
booth usage already feeds it: every placement calls `client.track`.

Real traffic takes days to be significant, so to **force fake data and see
a visual right away**, run:

```bash
python simulate_traffic.py --visitors 300
```

Then open the results dashboard (allow a few minutes for event processing):

[https://app.launchdarkly.com/projects/diane-demo/experiments/sparkle-engine-engagement/results?selected-env=test](https://app.launchdarkly.com/projects/diane-demo/experiments/sparkle-engine-engagement/results?selected-env=test)

What the simulator does — and what it rigs — is documented in  
`simulate_traffic.py`: each fake visitor is a `user` + `artist` multi-kind  
context; evaluating the flag registers their exposure (LaunchDarkly buckets  
them 50/50 on the fallthrough), and the sparkle cohort is scripted to place  
more stickers so the dashboard shows a decisive lift. **Simulated + rigged —**  
**label any screenshots as such.** Re-running mints fresh visitor keys, so  
each run adds more units. Free-plan visitors match the free-tier segment  
rule instead of the fallthrough, so they're served the flag but excluded  
from the experiment — a nice detail to narrate in a demo.

