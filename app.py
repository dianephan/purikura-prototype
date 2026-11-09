"""A Beautiful Camera

The `sparkleStickerEngine` flag wraps the booth's new sticker renderer:

  * Part 1 (Release & Remediate): a server-side flag listener pushes every
    toggle to all connected browsers over Socket.IO -- no reload. An optional
    LaunchDarkly trigger URL acts as the emergency kill switch.
  * Part 2 (Target): each browser joins as an "artist" context; the server
    evaluates the flag per-context, so individual targets and plan-based
    rules are visible side by side in the control room panel.

Setup: copy .env.example to .env and set LD_SDK_KEY to your server-side SDK
key (LaunchDarkly: Account settings -> Projects -> your environment).
See README.md for the full walkthrough.
"""

import base64
import os
import threading
import time
import urllib.request
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_socketio import SocketIO

import ldclient
from ldclient.config import Config
from ldclient.context import Context

load_dotenv()

# The feature flag wrapping the new sticker renderer. If you are recreating
# this demo in your own LaunchDarkly account, create a boolean flag with this
# exact key (see README.md, "Recreating the flag").
FLAG_KEY = "sparkleStickerEngine"
# Second flag: unlocks the spooky sticker pack for the premium-tier segment.
SPOOKY_FLAG_KEY = "spookyStickerPack"
SDK_KEY = os.environ.get("LD_SDK_KEY", "")
TRIGGER_URL = os.environ.get("LD_TRIGGER_URL", "")
PORT = int(os.environ.get("PORT", "5055"))

# Demo personas. Each becomes a LaunchDarkly context of kind "artist"; the
# attributes below are what the targeting rules match against.
PERSONAS = {
    "diane-artist": {"name": "Diane", "plan": "free", "country": "US",
                     "device": "desktop",
                     "blurb": "free plan, individually targeted beta friend"},
    "mika-pro": {"name": "Mika", "plan": "pro", "country": "JP",
                 "device": "tablet", "blurb": "pro plan"},
    "sam-free": {"name": "Sam", "plan": "free", "country": "CA",
                 "device": "phone", "blurb": "free plan"},
    "rin-pro": {"name": "Rin", "plan": "pro", "country": "JP",
                "device": "desktop", "blurb": "pro plan"},
}

CLASSIC_PACK = ["❤️", "⭐", "\U0001f338", "\U0001f642", "\U0001f380"]
SPARKLE_PACK = ["✨", "\U0001f496", "\U0001f31f", "\U0001f984", "\U0001fae7", "\U0001f308"]
SPOOKY_PACK = ["\U0001f383", "\U0001f47b", "\U0001f987", "\U0001f577️", "\U0001f480", "\U0001f578️"]

app = Flask(__name__)
# max_http_buffer_size raised so a camera snapshot (JPEG data URL) fits in
# one Socket.IO message.
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*",
                    max_http_buffer_size=8_000_000)

state_lock = threading.Lock()
clients = {}    # socket sid -> persona key
stickers = []   # shared canvas state: [{id, x, y, emoji, sparkle, spooky, by}]
photo = {"image": None}  # current shared backdrop as a data URL

# Saved photos live on disk; on Render's free tier the disk is ephemeral,
# so the gallery resets on each deploy/restart (fine for a demo).
GALLERY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery")
os.makedirs(GALLERY_DIR, exist_ok=True)


def decode_data_url(data_url):
    """Return (bytes, ext) for a base64 image data URL, or (None, None)."""
    if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
        return None, None
    header, _, b64 = data_url.partition(",")
    if ";base64" not in header or not b64 or len(b64) > 6_000_000:
        return None, None
    ext = "png" if "png" in header else "jpg"
    try:
        return base64.b64decode(b64), ext
    except Exception:
        return None, None


def gallery_items(limit=24):
    items = []
    try:
        filenames = sorted(os.listdir(GALLERY_DIR), reverse=True)
    except OSError:
        return items
    for fn in filenames:
        if fn.rsplit(".", 1)[-1] not in ("jpg", "png"):
            continue
        stem = fn.rsplit(".", 1)[0]
        by = stem.split("-", 1)[1] if "-" in stem else "?"
        items.append({"url": f"/gallery/{fn}", "by": by})
        if len(items) >= limit:
            break
    return items


def build_context(persona_key):
    """Multi-kind context: the `user` kind is the experiment randomization
    unit; the `artist` kind carries the attributes targeting rules match."""
    p = PERSONAS[persona_key]
    artist = (
        Context.builder(persona_key)
        .kind("artist")
        .name(p["name"])
        .set("plan", p["plan"])
        .set("country", p["country"])
        .set("device", p["device"])
        .build()
    )
    user = Context.builder(persona_key).kind("user").name(p["name"]).build()
    return Context.create_multi(user, artist)


def evaluate(persona_key):
    """Evaluate the flag for one persona, including the evaluation reason
    (OFF, TARGET_MATCH, RULE_MATCH, FALLTHROUGH) so the UI can show *why*
    each artist got their variation."""
    ctx = build_context(persona_key)
    detail = ldclient.get().variation_detail(FLAG_KEY, ctx, False)
    spooky = bool(ldclient.get().variation(SPOOKY_FLAG_KEY, ctx, False))
    p = PERSONAS[persona_key]
    return {
        "personaKey": persona_key,
        "name": p["name"],
        "plan": p["plan"],
        "country": p["country"],
        "blurb": p["blurb"],
        # Mirrors the LaunchDarkly segment rules (free-tier: plan in [free];
        # premium-tier: plan in [pro]) so the UI can show membership.
        "segment": "premium-tier" if p["plan"] == "pro" else "free-tier",
        "sparkle": bool(detail.value),
        "spooky": spooky,
        "reason": (detail.reason or {}).get("kind", "UNKNOWN"),
    }


def evaluate_all():
    return [evaluate(k) for k in PERSONAS]


def on_flag_change(flag_change):
    """Runs on the SDK's stream thread the moment the flag changes in
    LaunchDarkly. Re-evaluates every persona and pushes the result to all
    connected browsers -- this is the "instant release/rollback" listener."""
    if flag_change.key not in (FLAG_KEY, SPOOKY_FLAG_KEY):
        return
    socketio.emit("flag_update", {
        "evaluations": evaluate_all(),
        "at": time.strftime("%H:%M:%S"),
    })


@app.route("/")
def index():
    return render_template(
        "index.html",
        personas=PERSONAS,
        classic_pack=CLASSIC_PACK,
        sparkle_pack=SPARKLE_PACK,
        spooky_pack=SPOOKY_PACK,
        flag_key=FLAG_KEY,
        trigger_configured=bool(TRIGGER_URL),
    )


@app.route("/gallery/<path:filename>")
def gallery_file(filename):
    return send_from_directory(GALLERY_DIR, filename)


@app.route("/api/panic", methods=["POST"])
def panic():
    """Emergency de-sparkle. Fires the LaunchDarkly trigger URL, which turns
    flag targeting off -- equivalent to `curl -X POST $LD_TRIGGER_URL`."""
    if not TRIGGER_URL:
        return jsonify({"ok": False,
                        "error": "Set LD_TRIGGER_URL in .env (create a trigger on the flag first)."}), 400
    req = urllib.request.Request(TRIGGER_URL, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return jsonify({"ok": True, "status": resp.status})


@socketio.on("join")
def handle_join(data):
    persona = (data or {}).get("persona")
    if persona not in PERSONAS:
        return
    with state_lock:
        clients[request.sid] = persona
        snapshot = list(stickers)
        current_photo = photo["image"]
    socketio.emit("booth_state", {
        "you": persona,
        "stickers": snapshot,
        "photo": current_photo,
        "gallery": gallery_items(),
        "evaluations": evaluate_all(),
    }, to=request.sid)


@socketio.on("set_photo")
def handle_set_photo(data):
    """A camera snapshot becomes the shared backdrop for everyone, and the
    canvas starts fresh for the new photo."""
    persona = clients.get(request.sid)
    if persona is None or not data:
        return
    image = data.get("image")
    raw, _ext = decode_data_url(image)
    if raw is None:
        return
    with state_lock:
        photo["image"] = image
        stickers.clear()
    socketio.emit("photo_updated", {
        "image": image,
        "by": PERSONAS[persona]["name"],
    })


@socketio.on("save_to_gallery")
def handle_save_to_gallery(data):
    """The client composites photo + stickers onto a canvas and sends the
    result; the server writes it to the gallery folder for everyone."""
    persona = clients.get(request.sid)
    if persona is None or not data:
        return
    raw, ext = decode_data_url(data.get("image"))
    if raw is None:
        return
    filename = f"{int(time.time() * 1000)}-{PERSONAS[persona]['name']}.{ext}"
    with open(os.path.join(GALLERY_DIR, filename), "wb") as f:
        f.write(raw)
    socketio.emit("gallery_added", {
        "url": f"/gallery/{filename}",
        "by": PERSONAS[persona]["name"],
    })


@socketio.on("place_sticker")
def handle_place_sticker(data):
    persona = clients.get(request.sid)
    if persona is None or not data:
        return
    emoji = data.get("emoji")
    if emoji not in CLASSIC_PACK and emoji not in SPARKLE_PACK and emoji not in SPOOKY_PACK:
        return
    # The server, not the browser, decides who gets which packs --
    # a client can't unlock a feature by poking at the DOM.
    is_sparkle = emoji in SPARKLE_PACK
    is_spooky = emoji in SPOOKY_PACK
    if is_sparkle or is_spooky:
        evaluation = evaluate(persona)
        blocked = ("sparkle engine" if is_sparkle and not evaluation["sparkle"]
                   else "spooky pack" if is_spooky and not evaluation["spooky"]
                   else None)
        if blocked:
            socketio.emit("denied", {
                "message": f"the {blocked} isn't enabled for {PERSONAS[persona]['name']} (◡‿◡ ) try a classic sticker!",
            }, to=request.sid)
            return
    sticker = {
        "id": uuid.uuid4().hex,
        "x": max(0.0, min(100.0, float(data.get("x", 50)))),
        "y": max(0.0, min(100.0, float(data.get("y", 50)))),
        "emoji": emoji,
        "sparkle": is_sparkle,
        "spooky": is_spooky,
        "by": PERSONAS[persona]["name"],
    }
    with state_lock:
        stickers.append(sticker)
    # Custom event for the extra-credit experiment (metric: sticker-placed).
    ldclient.get().track("sticker-placed", build_context(persona))
    socketio.emit("sticker_added", sticker)


@socketio.on("clear_canvas")
def handle_clear():
    with state_lock:
        stickers.clear()
    socketio.emit("canvas_cleared")


@socketio.on("disconnect")
def handle_disconnect(*_args):
    with state_lock:
        clients.pop(request.sid, None)


def main():
    if not SDK_KEY.startswith("sdk-"):
        raise SystemExit("LD_SDK_KEY is missing. Copy .env.example to .env and "
                         "paste your server-side SDK key.")
    # Optional endpoint overrides, e.g. for a non-SaaS LaunchDarkly instance.
    endpoint_overrides = {
        key: os.environ[env_var]
        for key, env_var in (("base_uri", "LD_BASE_URI"),
                             ("stream_uri", "LD_STREAM_URI"),
                             ("events_uri", "LD_EVENTS_URI"))
        if os.environ.get(env_var)
    }
    ldclient.set_config(Config(SDK_KEY, **endpoint_overrides))
    client = ldclient.get()
    if not client.is_initialized():
        raise SystemExit("LaunchDarkly client failed to initialize -- check the "
                         "SDK key and your network.")
    # The SDK keeps a streaming connection open to LaunchDarkly; this listener
    # fires within moments of anyone toggling the flag.
    client.flag_tracker.add_listener(on_flag_change)
    print(f"A Beautiful Camera running at http://localhost:{PORT} (flag: {FLAG_KEY})")
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False,
                 allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
