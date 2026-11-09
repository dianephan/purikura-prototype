/* A Beautiful Camera client: renders the shared canvas and the LaunchDarkly
 * control room. All flag decisions come from the server — this file only
 * reflects them. */

const socket = io();

const personaSelect = document.getElementById("persona");
const canvas = document.getElementById("canvas");
const classicPalette = document.getElementById("classic-palette");
const sparklePalette = document.getElementById("sparkle-palette");
const sparkleLock = document.getElementById("sparkle-lock");
const spookyPalette = document.getElementById("spooky-palette");
const spookyLock = document.getElementById("spooky-lock");
const yourStatus = document.getElementById("your-status");
const evalTbody = document.querySelector("#eval-table tbody");
const logEl = document.getElementById("log");
const toast = document.getElementById("toast");
const conn = document.getElementById("conn");
const photoImg = document.getElementById("photo-img");
const cameraVideo = document.getElementById("camera");
const openCameraBtn = document.getElementById("open-camera");
const snapBtn = document.getElementById("snap");
const cancelCameraBtn = document.getElementById("cancel-camera");
const saveGalleryBtn = document.getElementById("save-gallery");
const galleryEl = document.getElementById("gallery");

let selectedEmoji = "❤️";
let mySparkle = false;
let mySpooky = false;
let firstState = true;
let localStickers = []; // mirror of the shared canvas, for compositing saves
let cameraStream = null;

const SPARKLE_EMOJIS = [...sparklePalette.querySelectorAll(".sticker-btn")]
  .map((b) => b.dataset.emoji);
const SPOOKY_EMOJIS = [...spookyPalette.querySelectorAll(".sticker-btn")]
  .map((b) => b.dataset.emoji);

const saved = localStorage.getItem("persona");
if (saved && [...personaSelect.options].some((o) => o.value === saved)) {
  personaSelect.value = saved;
}

function join() {
  localStorage.setItem("persona", personaSelect.value);
  socket.emit("join", { persona: personaSelect.value });
}

socket.on("connect", () => {
  conn.classList.replace("offline", "online");
  join();
});
socket.on("disconnect", () => conn.classList.replace("online", "offline"));
personaSelect.addEventListener("change", join);

socket.on("booth_state", (state) => {
  canvas.querySelectorAll(".sticker").forEach((el) => el.remove());
  localStickers = state.stickers.slice();
  state.stickers.forEach(addSticker);
  setPhoto(state.photo);
  renderGallery(state.gallery || []);
  applyEvaluations(state.evaluations, !firstState);
  firstState = false;
});

socket.on("photo_updated", (data) => {
  setPhoto(data.image);
  canvas.querySelectorAll(".sticker").forEach((el) => el.remove());
  localStickers = [];
  showToast(`📷 ${data.by} took a new photo — decorate it!`);
});

socket.on("gallery_added", (item) => {
  addGalleryItem(item, true);
  showToast(`💾 ${item.by} saved a photo to the gallery`);
});

socket.on("flag_update", (update) => {
  applyEvaluations(update.evaluations, true);
  addLog(`${update.at} — flag changed in LaunchDarkly`);
});

socket.on("sticker_added", (st) => {
  localStickers.push(st);
  addSticker(st);
});
socket.on("canvas_cleared", () => {
  canvas.querySelectorAll(".sticker").forEach((el) => el.remove());
  localStickers = [];
});
socket.on("denied", (d) => showToast(d.message));

function applyEvaluations(evaluations, announce) {
  const mine = evaluations.find((e) => e.personaKey === personaSelect.value);
  const wasSparkle = mySparkle;
  const wasSpooky = mySpooky;
  mySparkle = mine ? mine.sparkle : false;
  mySpooky = mine ? mine.spooky : false;

  yourStatus.textContent = mySparkle
    ? "✨ sparkle engine ON for you"
    : "classic stickers for you";
  yourStatus.className =
    "status-chip " + (mySparkle ? "sparkle-chip" : "classic-chip");

  sparklePalette.classList.toggle("locked", !mySparkle);
  sparkleLock.textContent = mySparkle ? "✨" : "🔒";
  sparklePalette
    .querySelectorAll(".sticker-btn")
    .forEach((b) => (b.disabled = !mySparkle));
  spookyPalette.classList.toggle("locked", !mySpooky);
  spookyLock.textContent = mySpooky ? "🎃" : "🔒";
  spookyPalette
    .querySelectorAll(".sticker-btn")
    .forEach((b) => (b.disabled = !mySpooky));
  if (
    (!mySparkle && SPARKLE_EMOJIS.includes(selectedEmoji)) ||
    (!mySpooky && SPOOKY_EMOJIS.includes(selectedEmoji))
  ) {
    selectEmoji("❤️");
  }

  evalTbody.innerHTML = "";
  evaluations.forEach((e) => {
    const tr = document.createElement("tr");
    if (e.personaKey === personaSelect.value) tr.classList.add("you");
    const segment = e.segment || (e.plan === "pro" ? "premium-tier" : "free-tier");
    tr.innerHTML =
      `<td>${e.name}</td>` +
      `<td><span class="segment ${segment}">${segment === "premium-tier" ? "💎 premium" : "🌱 free"}</span></td>` +
      `<td>${e.sparkle ? "✨ sparkle" : "classic"}</td>` +
      `<td>${e.spooky ? "🎃" : "—"}</td>` +
      `<td><span class="reason ${e.reason.toLowerCase()}">${e.reason}</span></td>`;
    evalTbody.appendChild(tr);
  });

  if (announce && wasSparkle !== mySparkle) {
    showToast(
      mySparkle
        ? "✨ the sparkle engine just turned ON — no reload needed!"
        : "sparkle engine rolled back — stickers stay, new magic pauses"
    );
  } else if (announce && wasSpooky !== mySpooky) {
    showToast(
      mySpooky
        ? "🎃 the spooky pack just unlocked for you — premium perk!"
        : "spooky pack locked away — the ghosts rest for now"
    );
  }
}

function addSticker(st) {
  const el = document.createElement("span");
  el.className =
    "sticker" +
    (st.sparkle ? " sparkle-sticker" : "") +
    (st.spooky ? " spooky-sticker" : "");
  el.style.left = st.x + "%";
  el.style.top = st.y + "%";
  el.textContent = st.emoji;
  el.title = "by " + st.by;
  canvas.appendChild(el);
  if (st.sparkle || st.spooky) burst(st.x, st.y);
}

function burst(x, y) {
  for (let i = 0; i < 6; i++) {
    const p = document.createElement("span");
    p.className = "burst";
    p.textContent = "✦";
    p.style.left = x + "%";
    p.style.top = y + "%";
    p.style.setProperty("--dx", (Math.random() * 80 - 40).toFixed(0) + "px");
    p.style.setProperty("--dy", (Math.random() * 80 - 40).toFixed(0) + "px");
    canvas.appendChild(p);
    setTimeout(() => p.remove(), 700);
  }
}

function selectEmoji(emoji) {
  selectedEmoji = emoji;
  document
    .querySelectorAll(".sticker-btn")
    .forEach((b) => b.classList.toggle("selected", b.dataset.emoji === emoji));
}

document.querySelectorAll(".sticker-btn").forEach((btn) => {
  btn.addEventListener("click", () => selectEmoji(btn.dataset.emoji));
});
selectEmoji(selectedEmoji);

canvas.addEventListener("click", (ev) => {
  const rect = canvas.getBoundingClientRect();
  const x = ((ev.clientX - rect.left) / rect.width) * 100;
  const y = ((ev.clientY - rect.top) / rect.height) * 100;
  socket.emit("place_sticker", { emoji: selectedEmoji, x, y });
});

document.getElementById("clear").addEventListener("click", () => {
  socket.emit("clear_canvas");
});

const panicBtn = document.getElementById("panic");
panicBtn.addEventListener("click", async () => {
  panicBtn.disabled = true;
  try {
    const res = await fetch("/api/panic", { method: "POST" });
    const body = await res.json();
    showToast(
      body.ok
        ? "🚨 trigger fired — LaunchDarkly is turning the flag off"
        : body.error
    );
  } catch (err) {
    showToast("trigger request failed: " + err);
  } finally {
    panicBtn.disabled = false;
  }
});

/* ---- camera & gallery ---- */

function setPhoto(image) {
  if (image) {
    photoImg.src = image;
    photoImg.classList.remove("hidden");
  } else {
    photoImg.classList.add("hidden");
    photoImg.removeAttribute("src");
  }
}

function setCameraUi(active) {
  cameraVideo.classList.toggle("hidden", !active);
  snapBtn.classList.toggle("hidden", !active);
  cancelCameraBtn.classList.toggle("hidden", !active);
  openCameraBtn.classList.toggle("hidden", active);
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop());
    cameraStream = null;
  }
  cameraVideo.srcObject = null;
  setCameraUi(false);
}

openCameraBtn.addEventListener("click", async () => {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 } },
      audio: false,
    });
    cameraVideo.srcObject = cameraStream;
    setCameraUi(true);
  } catch (err) {
    showToast("camera unavailable: " + (err.name || err));
  }
});

cancelCameraBtn.addEventListener("click", stopCamera);

// Draw a source into the canvas with object-fit: cover semantics.
function drawCover(ctx, source, sw, sh, cw, ch) {
  const scale = Math.max(cw / sw, ch / sh);
  const dw = sw * scale;
  const dh = sh * scale;
  ctx.drawImage(source, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
}

snapBtn.addEventListener("click", () => {
  if (!cameraStream) return;
  const c = document.createElement("canvas");
  c.width = 800;
  c.height = 600;
  const ctx = c.getContext("2d");
  // Mirror to match the on-screen preview.
  ctx.translate(c.width, 0);
  ctx.scale(-1, 1);
  drawCover(ctx, cameraVideo, cameraVideo.videoWidth || 1280,
            cameraVideo.videoHeight || 960, c.width, c.height);
  socket.emit("set_photo", { image: c.toDataURL("image/jpeg", 0.85) });
  stopCamera();
});

saveGalleryBtn.addEventListener("click", () => {
  const c = document.createElement("canvas");
  c.width = 800;
  c.height = 600;
  const ctx = c.getContext("2d");
  if (!photoImg.classList.contains("hidden") && photoImg.src) {
    drawCover(ctx, photoImg, photoImg.naturalWidth || 800,
              photoImg.naturalHeight || 600, c.width, c.height);
  } else {
    // No photo yet: reproduce the pastel gradient backdrop.
    const g = ctx.createLinearGradient(0, 0, c.width, c.height);
    g.addColorStop(0, "#ffc1dd");
    g.addColorStop(0.6, "#c9b6f5");
    g.addColorStop(1, "#a9e8d2");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, c.width, c.height);
  }
  ctx.font = "48px serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  localStickers.forEach((st) => {
    if (st.sparkle) {
      ctx.shadowColor = "#ffb3f0";
      ctx.shadowBlur = 18;
    } else if (st.spooky) {
      ctx.shadowColor = "#9a5cff";
      ctx.shadowBlur = 18;
    } else {
      ctx.shadowBlur = 0;
    }
    ctx.fillText(st.emoji, (st.x / 100) * c.width, (st.y / 100) * c.height);
  });
  socket.emit("save_to_gallery", { image: c.toDataURL("image/jpeg", 0.85) });
});

function addGalleryItem(item, prepend) {
  const empty = document.getElementById("gallery-empty");
  if (empty) empty.remove();
  const a = document.createElement("a");
  a.href = item.url;
  a.target = "_blank";
  const img = document.createElement("img");
  img.src = item.url;
  img.alt = img.title = "saved by " + item.by;
  a.appendChild(img);
  if (prepend) galleryEl.prepend(a);
  else galleryEl.appendChild(a);
}

function renderGallery(items) {
  galleryEl.querySelectorAll("a").forEach((el) => el.remove());
  items.forEach((item) => addGalleryItem(item, false));
}

let toastTimer = null;
function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function addLog(message) {
  const placeholder = logEl.querySelector(".hint");
  if (placeholder) placeholder.remove();
  const li = document.createElement("li");
  li.textContent = message;
  logEl.prepend(li);
  while (logEl.children.length > 8) logEl.lastChild.remove();
}
