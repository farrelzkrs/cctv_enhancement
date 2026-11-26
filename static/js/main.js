/* main.js — interaksi UI: upload, kontrol, proses, comparison slider, histogram, riwayat, deteksi. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const MAX_BYTES = 10 * 1024 * 1024, EXT = /\.(jpe?g|png)$/i;

  // ---------- util ----------
  const fmtBytes = b => b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(2)} MB`;
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function toast(msg, kind = "") {
    const t = document.createElement("div");
    t.className = `toast ${kind}`; t.textContent = msg;
    $("#toasts").appendChild(t); setTimeout(() => t.remove(), 5000);
  }
  function setStatus(state, text) {
    const el = $("#status"); el.dataset.state = state; $("span", el).textContent = text;
  }
  async function api(url, opts) {                       // fetch JSON dengan penanganan error seragam
    let res, data;
    try { res = await fetch(url, opts); } catch { throw new Error("Server tidak dapat dihubungi. Pastikan app.py masih berjalan."); }
    try { data = await res.json(); } catch { throw new Error(`Respons server tidak valid (HTTP ${res.status}).`); }
    if (!res.ok || data.ok === false) {
      const detail = (data.errors || []).map(e => `${e.name}: ${e.error}`).join(" | ");
      throw new Error(data.error || detail || `Permintaan gagal (HTTP ${res.status}).`);
    }
    return data;
  }

  // ---------- comparison slider (dipakai dashboard & halaman detail) ----------
  function initCompare(box) {
    const range = $(".cmp-range", box);
    const set = v => box.style.setProperty("--pos", v + "%");
    range.addEventListener("input", () => set(range.value));
    set(range.value);
  }
  $$(".compare").forEach(initCompare);

  // ---------- histogram ----------
  function drawHist(canvas, hist, mode) {
    const ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    const series = mode === "gray" ? [["gray", "rgba(34,211,238,.85)"]]
      : [["r", "rgba(248,113,113,.7)"], ["g", "rgba(52,211,153,.7)"], ["b", "rgba(96,165,250,.7)"]];
    // normalisasi dengan mengabaikan bin 0 dan 255 (sering sangat tinggi akibat clipping)
    const max = Math.max(1, ...series.flatMap(([k]) => hist[k].slice(1, 255)));
    ctx.strokeStyle = "#243551"; ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) { const x = (W / 4) * i; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H - 16); ctx.stroke(); }
    ctx.globalCompositeOperation = "lighter";
    series.forEach(([k, color]) => {
      ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(0, H - 16);
      hist[k].forEach((v, i) => ctx.lineTo((i / 255) * W, H - 16 - Math.min(1, v / max) * (H - 24)));
      ctx.lineTo(W, H - 16); ctx.closePath(); ctx.fill();
    });
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#8b9bb4"; ctx.font = "12px sans-serif";
    ["0", "64", "128", "192", "255"].forEach((t, i) => ctx.fillText(t, i === 4 ? W - 22 : (W / 4) * i + 2, H - 3));
  }

  // =====================================================================
  //  DASHBOARD
  // =====================================================================
  if ($("#dropzone")) {
    const state = { uploads: [], selected: null, result: null, histMode: "rgb" };
    const PRESETS = {
      ringan: { gamma: .8, clip_limit: 1.5, tile_grid: 8, amount: .5, sigma: 1.2, threshold: 3 },
      malam: { gamma: .65, clip_limit: 2.5, tile_grid: 8, amount: .8, sigma: 1.2, threshold: 3 },
      ekstrem: { gamma: .5, clip_limit: 3.5, tile_grid: 8, amount: 1.0, sigma: 1.5, threshold: 5 },
    };
    const DEFAULTS = { ...PRESETS.malam, gamma: .7, clip_limit: 2, amount: .8 };
    const SLIDERS = ["gamma", "clip_limit", "tile_grid", "amount", "sigma", "threshold"];

    // ----- kontrol -----
    function syncPresetState() {
      const cur = readParams();
      const active = Object.entries(PRESETS).find(([, vals]) =>
        Object.entries(vals).every(([k, v]) => Math.abs(cur[k] - v) < 1e-6)
      )?.[0] ?? null;
      $$("[data-preset]").forEach(b => {
        const on = b.dataset.preset === active;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", String(on));
      });
    }
    function refreshOutputs() {
      SLIDERS.forEach(id => {
        const v = $("#" + id).value;
        $(`#${id}-out`).textContent = id === "tile_grid" ? `${v}×${v}` : id === "gamma" || id === "amount" ? (+v).toFixed(2) : id === "clip_limit" || id === "sigma" ? (+v).toFixed(1) : v;
      });
      syncPresetState();
    }
    function applyValues(vals) {
      Object.entries(vals).forEach(([k, v]) => { const el = $("#" + k); if (el) el.value = v; });
      refreshOutputs();
    }
    function readParams() {
      const p = { use_gamma: true, use_clahe: true, use_sharpen: true };
      SLIDERS.forEach(id => p[id] = parseFloat($("#" + id).value));
      return p;
    }
    $$("input[type=range]", $(".controls")).forEach(el => el.addEventListener("input", refreshOutputs));
    $$("[data-preset]").forEach(b => b.addEventListener("click", () => applyValues({ ...PRESETS[b.dataset.preset] })));
    refreshOutputs();

    // ----- upload -----
    const dz = $("#dropzone"), input = $("#file-input");
    ["dragenter", "dragover"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.add("drag"); }));
    ["dragleave", "drop"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.remove("drag"); }));
    dz.addEventListener("drop", ev => upload([...ev.dataTransfer.files]));
    dz.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); input.click(); } });
    input.addEventListener("change", () => { upload([...input.files]); input.value = ""; });

    async function upload(files) {
      if (!files.length) return;
      const ok = [];
      files.forEach(f => {                                       // validasi awal di sisi klien
        if (!EXT.test(f.name)) toast(`${f.name}: format harus JPG, JPEG, atau PNG.`, "error");
        else if (f.size > MAX_BYTES) toast(`${f.name}: ukuran melebihi 10 MB.`, "error");
        else ok.push(f);
      });
      if (!ok.length) return;
      const fd = new FormData(); ok.forEach(f => fd.append("files", f));
      setStatus("working", "Mengunggah…");
      try {
        const data = await api("/api/upload", { method: "POST", body: fd });
        state.uploads = [...data.uploads, ...state.uploads];
        data.errors.forEach(e => toast(`${e.name}: ${e.error}`, "error"));
        select(data.uploads[0].id); renderThumbs();
        toast(`${data.uploads.length} gambar diunggah.`, "ok"); setStatus("idle", "Siap");
      } catch (e) { toast(e.message, "error"); setStatus("error", "Unggah gagal"); }
    }

    function renderThumbs() {
      const box = $("#thumbs"); box.innerHTML = "";
      $("#upload-count").textContent = state.uploads.length ? `${state.uploads.length} gambar${state.uploads.length < 2 ? " · tambahkan minimal 2 untuk pengujian" : ""}` : "Belum ada gambar";
      state.uploads.forEach(u => {
        const b = document.createElement("div");
        b.className = "thumb" + (u.id === state.selected ? " selected" : ""); b.tabIndex = 0; b.setAttribute("role", "button");
        b.setAttribute("aria-pressed", u.id === state.selected);
        b.innerHTML = `<img src="${u.url}" alt="${esc(u.name)}" loading="lazy">
          <div class="meta"><b title="${esc(u.name)}">${esc(u.name)}</b><span>${u.width}×${u.height} px · ${fmtBytes(u.size)}${u.resized ? " · diperkecil" : ""}</span></div>
          <button class="x" aria-label="Hapus ${esc(u.name)}" type="button">×</button>`;
        b.addEventListener("click", () => select(u.id));
        b.addEventListener("keydown", e => { if (e.target === b && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(u.id); } });
        $(".x", b).addEventListener("click", ev => { ev.stopPropagation(); removeUpload(u); });
        box.appendChild(b);
      });
    }
    function select(id) {
      state.selected = id;
      const u = state.uploads.find(x => x.id === id);
      $("#btn-process").disabled = !u;
      $("#select-info").textContent = u ? `Dipilih: ${u.name} (${u.width}×${u.height} px, ${fmtBytes(u.size)})` : "Pilih satu gambar pada daftar di kiri.";
      renderThumbs();
    }
    async function removeUpload(u) {
      try {
        await api(`/api/upload/${u.id}`, { method: "DELETE" });
        state.uploads = state.uploads.filter(x => x.id !== u.id);
        if (state.selected === u.id) select(state.uploads[0]?.id ?? null); else renderThumbs();
      } catch (e) { toast(e.message, "error"); }
    }

    // ----- proses -----
    $("#btn-process").addEventListener("click", async () => {
      const p = readParams();
      if (!p.use_gamma && !p.use_clahe && !p.use_sharpen) return toast("Aktifkan minimal satu metode.", "error");
      const btn = $("#btn-process"); btn.disabled = true; btn.textContent = "Memproses…";
      setStatus("working", "Memproses citra…");
      try {
        const data = await api("/api/process", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_id: state.selected, params: p }) });
        state.result = data; renderResult(data);
        setStatus("done", "Selesai"); toast("Pemrosesan selesai.", "ok");
      } catch (e) { toast(e.message, "error"); setStatus("error", "Gagal"); }
      finally { btn.disabled = !state.selected; btn.textContent = "Process Image"; }
    });

    $("#btn-reset").addEventListener("click", () => {
      applyValues(DEFAULTS); state.result = null; $("#results").hidden = true; setStatus("idle", "Siap");
    });

    // ----- tampilan hasil -----
    function renderResult(d) {
      $("#results").hidden = false;
      const cmp = $("#compare-main");
      cmp.style.setProperty("--ratio", d.width / d.height);
      $("#cmp-before").src = d.original_url; $("#cmp-after").src = d.result_url + "?t=" + Date.now();
      $("#side-before").src = d.original_url; $("#side-after").src = d.result_url;
      $("#steps-grid").innerHTML = `<figure><img src="${d.original_url}" alt="Asli"><figcaption>Citra asli</figcaption></figure>` +
        d.steps.map(s => `<figure><img src="${s.url}" alt="${esc(s.label)}"><figcaption>${esc(s.label)}</figcaption></figure>`).join("");
      $("#dl-png").href = `/download/${d.id}?fmt=png`; $("#dl-jpg").href = `/download/${d.id}?fmt=jpg`;

      const o = d.evaluation.original, e = d.evaluation.enhanced, dl = d.evaluation.delta;
      const cls = v => v > 0 ? "up" : v < 0 ? "down" : "";
      const sg = v => (v > 0 ? "+" : "") + v.toFixed(2);
      $("#eval-table").innerHTML = `<tr><th></th><th>Asli</th><th>Hasil</th><th>Selisih</th></tr>
        <tr><td>Brightness (mean)</td><td class="num">${o.brightness}</td><td class="num">${e.brightness}</td><td class="num ${cls(dl.brightness)}">${sg(dl.brightness)}</td></tr>
        <tr><td>Kontras (std)</td><td class="num">${o.contrast}</td><td class="num">${e.contrast}</td><td class="num ${cls(dl.contrast)}">${sg(dl.contrast)}</td></tr>
        <tr><td>Piksel sangat gelap</td><td class="num">${o.dark_pct}%</td><td class="num">${e.dark_pct}%</td><td></td></tr>
        <tr><td>Resolusi</td><td class="num" colspan="3">${o.width} × ${o.height} px</td></tr>
        <tr><td>Ukuran file</td><td class="num">${fmtBytes(o.file_size)}</td><td class="num">${fmtBytes(e.file_size)} (PNG)</td><td></td></tr>`;
      $("#warnings").innerHTML = d.evaluation.warnings.map(w => `<p class="warn">${esc(w)}</p>`).join("");
      $("#methods").innerHTML = d.methods.map(m => `<li><strong>${esc(m.name)}</strong><span>${esc(m.params)}</span></li>`).join("");
      drawHists();
      $("#results").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    }
    function drawHists() {
      if (!state.result) return;
      const h = state.result.evaluation.histograms;
      drawHist($("#hist-before"), h.original, state.histMode); drawHist($("#hist-after"), h.enhanced, state.histMode);
    }
    $("#view-tabs").addEventListener("click", ev => {
      const b = ev.target.closest("[data-view]"); if (!b) return;
      $$("#view-tabs .tab").forEach(t => { const on = t === b; t.classList.toggle("active", on); t.setAttribute("aria-selected", on); });
      ["slider", "side", "steps"].forEach(v => $("#view-" + v).hidden = v !== b.dataset.view);
    });
    $("#hist-tabs").addEventListener("click", ev => {
      const b = ev.target.closest("[data-mode]"); if (!b) return;
      $$("#hist-tabs .tab").forEach(t => t.classList.toggle("active", t === b));
      state.histMode = b.dataset.mode; drawHists();
    });

    // ----- muat unggahan yang tersimpan -----
    api("/api/uploads").then(d => { state.uploads = d.uploads; if (d.uploads.length) select(d.uploads[0].id); else renderThumbs(); })
      .catch(e => toast(e.message, "error"));
  }

  // =====================================================================
  //  RIWAYAT
  // =====================================================================
  $$("[data-del]").forEach(b => b.addEventListener("click", async () => {
    if (!confirm("Hapus hasil ini?")) return;
    try { await api(`/api/history/${b.dataset.del}`, { method: "DELETE" }); b.closest(".h-item").remove(); toast("Hasil dihapus.", "ok"); }
    catch (e) { toast(e.message, "error"); }
  }));
  $("#btn-cleanup")?.addEventListener("click", async () => {
    if (!confirm("Hapus SEMUA gambar unggahan, hasil, dan riwayat?")) return;
    try { await api("/api/cleanup", { method: "POST" }); location.reload(); } catch (e) { toast(e.message, "error"); }
  });

  // =====================================================================
  //  DETEKSI OBJEK (opsional)
  // =====================================================================
  const det = $("#btn-detect");
  if (det) {
    const conf = $("#det-conf");
    conf.addEventListener("input", () => $("#det-conf-out").textContent = (+conf.value).toFixed(2));
    det.addEventListener("click", async () => {
      det.disabled = true; det.textContent = "Mendeteksi…"; setStatus("working", "Mendeteksi objek…");
      try {
        const d = await api("/api/detect", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: $("#det-source").value, conf: +conf.value }) });
        $("#det-result").hidden = false; $("#det-img").src = d.url;
        $("#det-summary").textContent = `${d.total} objek terdeteksi`;
        $("#det-counts").innerHTML = Object.entries(d.counts).map(([k, v]) => `<span>${esc(k)}: ${v}</span>`).join("") || '<span>Tidak ada objek terdeteksi</span>';
        setStatus("done", "Selesai");
      } catch (e) { toast(e.message, "error"); setStatus("error", "Gagal"); }
      finally { det.disabled = false; det.textContent = "Jalankan deteksi"; }
    });
  }
})();
