"""Fake-traffic generator for the "Sparkle Engine Engagement" experiment.

!! SIMULATED DATA, DELIBERATELY RIGGED !!
Every visitor is fake, and sparkle-engine visitors are scripted to place
more stickers than classic visitors, so the experiment dashboard shows a
clear winner within minutes. Label any screenshots accordingly — this
forces a visual, it does not measure anything real.

How it works (the honest machinery):
  1. Each visitor is a multi-kind context: `user` (the experiment's
     randomization unit) + `artist` (the attributes targeting matches).
  2. Evaluating the flag registers the visitor's EXPOSURE and lets
     LaunchDarkly bucket them 50/50 into classic vs sparkle.
  3. client.track("sticker-placed", ...) registers CONVERSIONS, with the
     sparkle cohort rigged to decorate more.

Visitors on the free plan match the free-tier segment rule, not the
fallthrough the experiment runs on, so they are exposed but NOT in the
experiment — which is also a nice thing to point out in a demo.

Usage:
    python simulate_traffic.py --visitors 300
"""

import argparse
import os
import random
import time

from dotenv import load_dotenv

import ldclient
from ldclient.config import Config
from ldclient.context import Context

FLAG_KEY = "sparkleStickerEngine"
EVENT_KEY = "sticker-placed"
COUNTRIES = ["US", "JP", "CA", "FR", "BR", "KR", "DE", "AU"]
DEVICES = ["desktop", "tablet", "phone"]


def visitor_context(run_id, i):
    # Unique key per run so re-running creates fresh experiment units.
    key = f"sim-{run_id}-{i:05d}"
    plan = "pro" if random.random() < 0.8 else "free"
    user = Context.builder(key).kind("user").name(f"Sim Visitor {i}").build()
    artist = (
        Context.builder(key)
        .kind("artist")
        .name(f"Sim Visitor {i}")
        .set("plan", plan)
        .set("country", random.choice(COUNTRIES))
        .set("device", random.choice(DEVICES))
        .set("simulated", True)
        .build()
    )
    return Context.create_multi(user, artist), plan


def stickers_for(sparkle):
    """The rigged part: sparkle visitors decorate more, by design."""
    if sparkle:
        return random.randint(2, 8) if random.random() < 0.85 else 0
    return random.randint(1, 4) if random.random() < 0.55 else 0


def main():
    parser = argparse.ArgumentParser(description="Send fake experiment traffic.")
    parser.add_argument("--visitors", type=int, default=300)
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    sdk_key = os.environ.get("LD_SDK_KEY", "")
    if not sdk_key.startswith("sdk-"):
        raise SystemExit("LD_SDK_KEY missing — set it in .env (see README).")

    ldclient.set_config(Config(sdk_key))
    client = ldclient.get()
    if not client.is_initialized():
        raise SystemExit("LaunchDarkly client failed to initialize.")

    run_id = int(time.time())
    tallies = {"sparkle": [0, 0], "classic": [0, 0]}  # [visitors, stickers]

    print(f"releasing {args.visitors} fake visitors into the booth…")
    for i in range(args.visitors):
        ctx, plan = visitor_context(run_id, i)
        sparkle = bool(client.variation(FLAG_KEY, ctx, False))  # exposure
        placed = stickers_for(sparkle)
        for _ in range(placed):
            client.track(EVENT_KEY, ctx)  # conversion
        bucket = "sparkle" if sparkle else "classic"
        tallies[bucket][0] += 1
        tallies[bucket][1] += placed
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{args.visitors} visitors sent…")
        time.sleep(0.01)

    client.flush()
    time.sleep(2)  # give the event buffer a moment before closing
    client.close()

    print("\ndone! (simulated + rigged, remember)")
    for bucket, (visitors, stickers) in tallies.items():
        avg = stickers / visitors if visitors else 0
        print(f"  {bucket:>8}: {visitors:4d} visitors, {stickers:5d} stickers "
              f"({avg:.2f} avg)")
    print("\nresults (allow a few minutes for processing):")
    print("  https://app.launchdarkly.com/projects/diane-demo/experiments/"
          "sparkle-engine-engagement/results?selected-env=test")


if __name__ == "__main__":
    main()
