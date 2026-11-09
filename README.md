# Purikura Booth ✨

A collaborative photo-decorating booth that demos LaunchDarkly's release, remediation, and targeting features **visually.**

The story: the booth is upgrading its sticker renderer to the new **Sparkle
Engine**. The `sparkleStickerEngine` feature flag controls who gets it, and
every toggle reaches all open browsers instantly — mid-session, no reload.


| Exercise requirement              | Where it lives in this app                                                        |
| --------------------------------- | --------------------------------------------------------------------------------- |
| Feature flag around a feature     | `sparkleStickerEngine` wraps the sparkle sticker pack (`app.py`)                  |
| Instant release/rollback listener | SDK `flag_tracker` listener → Socket.IO broadcast (`on_flag_change` in `app.py`)  |
| Remediate via trigger             | "🚨 emergency de-sparkle" button or `curl -X POST $LD_TRIGGER_URL`                |
| Context attributes                | `artist` contexts with `plan`, `country`, `device`                                |
| Individual targeting              | `diane-artist` is targeted into the sparkle engine despite being on the free plan |
| Rule-based targeting              | rule: `plan is "free"` → classic stickers; fallthrough → sparkle                  |
| Extra credit: experimentation     | every sticker placement calls `track("sticker-placed", context)`                  |




## Prerequisites

- **Python 3.10+** (`python3 --version`)
- A LaunchDarkly account with a **server-side SDK key**
- macOS/Linux/Windows — no other services needed; state is in-memory



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

On the flag: **Settings → Triggers → Add trigger** → type *Generic trigger*,
action *Turn flag targeting off*. Copy the one-time URL into `.env` as
`LD_TRIGGER_URL`. This enables the in-app 🚨 button; the same URL works from
a terminal:

```bash
curl -X POST "$LD_TRIGGER_URL"
```



## Run

```bash
python app.py
# → Purikura Booth running at http://localhost:5055
```

## Extra credit: experimentation

A live experiment — **Sparkle Engine Engagement** — runs on
`sparkleStickerEngine` in the `test` environment, measuring the custom
metric **`sticker-placed`** (stickers per user, higher is better). Real
booth usage already feeds it: every placement calls `client.track`.

Real traffic takes days to be significant, so to **force fake data and see
a visual right away**, run:

```bash
python simulate_traffic.py --visitors 300
```

Then open the results dashboard (allow a few minutes for event processing):

<https://app.launchdarkly.com/projects/diane-demo/experiments/sparkle-engine-engagement/results?selected-env=test>

What the simulator does — and what it rigs — is documented in
`simulate_traffic.py`: each fake visitor is a `user` + `artist` multi-kind
context; evaluating the flag registers their exposure (LaunchDarkly buckets
them 50/50 on the fallthrough), and the sparkle cohort is scripted to place
more stickers so the dashboard shows a decisive lift. **Simulated + rigged —
label any screenshots as such.** Re-running mints fresh visitor keys, so
each run adds more units. Free-plan visitors match the free-tier segment
rule instead of the fallthrough, so they're served the flag but excluded
from the experiment — a nice detail to narrate in a demo.



# purikura-prototype
