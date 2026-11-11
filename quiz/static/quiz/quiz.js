(function () {
  const started = performance.now();
  let ws = null;
  // White background, dark marks (Macaulay-style); tuned for peak-normalized audio.
  const SPECTRO_COLORS = Array.from({ length: 256 }, (_, i) => {
    const v = 1 - Math.pow(i / 255, 0.9);
    return [v, v, v, 1];
  });

  // Audio + spectrogram. Recordings vary wildly in level; the spectrogram plugin uses absolute dB,
  // so decode, peak-normalize, and hand wavesurfer a WAV blob (also evens out playback volume).
  const SAMPLE_RATE = 22050; // wavesurfer's default 8000 would cap the spectrogram at 4 kHz

  async function normalizedWavUrl(src) {
    const raw = await (await fetch(src)).arrayBuffer();
    const ctx = new OfflineAudioContext(1, 1, SAMPLE_RATE);
    const buf = await ctx.decodeAudioData(raw);
    const data = buf.getChannelData(0);
    let peak = 0;
    for (let i = 0; i < data.length; i++) peak = Math.max(peak, Math.abs(data[i]));
    const gain = peak > 0 ? 0.95 / peak : 1;
    // 16-bit mono PCM WAV
    const out = new DataView(new ArrayBuffer(44 + data.length * 2));
    const str = (o, t) => [...t].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
    str(0, "RIFF"); out.setUint32(4, 36 + data.length * 2, true); str(8, "WAVE"); str(12, "fmt ");
    out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true);
    out.setUint32(24, buf.sampleRate, true); out.setUint32(28, buf.sampleRate * 2, true);
    out.setUint16(32, 2, true); out.setUint16(34, 16, true); str(36, "data"); out.setUint32(40, data.length * 2, true);
    for (let i = 0; i < data.length; i++) {
      const v = Math.max(-1, Math.min(1, data[i] * gain));
      out.setInt16(44 + i * 2, v * 32767, true);
    }
    return URL.createObjectURL(new Blob([out], { type: "audio/wav" }));
  }

  const box = document.querySelector(".audio");
  if (box && window.WaveSurfer) {
    const style = getComputedStyle(document.documentElement);
    ws = WaveSurfer.create({
      container: box.querySelector(".wave"),
      height: 48,
      sampleRate: SAMPLE_RATE,
      normalize: true,
      waveColor: style.getPropertyValue("--muted").trim() || "#999",
      progressColor: style.getPropertyValue("--accent").trim() || "#2f6d4f",
      plugins: [WaveSurfer.Spectrogram.create({
        container: box.querySelector(".spec"), labels: true, height: 240, scale: "linear", fftSamples: 1024,
        frequencyMin: 0, frequencyMax: 11000, gainDB: 15, rangeDB: 60, colorMap: SPECTRO_COLORS,
        labelsColor: "#333", labelsHzColor: "#333", labelsBackground: "rgba(255,255,255,0.6)",
      })],
    });
    normalizedWavUrl(box.dataset.src)
      .then((url) => ws.load(url))
      .catch(() => ws.load(box.dataset.src)); // fall back to the raw file
    const btn = box.querySelector(".play");
    btn.addEventListener("click", () => ws.playPause());
    ws.on("play", () => (btn.textContent = "❚❚ Pause"));
    ws.on("pause", () => (btn.textContent = "▶ Play"));
    ws.on("finish", () => (btn.textContent = "▶ Play"));
  }

  const form = document.getElementById("answer-form");
  const rt = document.getElementById("response_ms");
  if (form) form.addEventListener("submit", () => (rt.value = Math.round(performance.now() - started)));

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === " " && ws) { e.preventDefault(); ws.playPause(); return; }
    const next = document.getElementById("next");
    if (e.key === "Enter" && next) { e.preventDefault(); next.click(); return; }
    const buttons = form ? [...form.querySelectorAll("button[name=choice]")] : [];
    if (!buttons.length || buttons[0].disabled) return;
    let btn = null;
    if (e.key === "0" || e.key.toLowerCase() === "o") btn = buttons[buttons.length - 1];
    else if (/^[1-9]$/.test(e.key)) btn = buttons[parseInt(e.key, 10) - 1];
    if (btn) {
      e.preventDefault(); rt.value = Math.round(performance.now() - started); form.requestSubmit(btn);
    }
  });
})();
