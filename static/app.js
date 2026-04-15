/*Receipt Reader · Simplified Flow*/
(function () {
  "use strict";

  // DOM refs
  const dropZone      = document.getElementById("dropZone");
  const fileInput      = document.getElementById("fileInput");
  const previewWrap    = document.getElementById("previewWrap");
  const previewImg     = document.getElementById("previewImg");
  const previewName    = document.getElementById("previewName");
  const removeBtn      = document.getElementById("removeBtn");

  const btnSheets      = document.getElementById("btnSheets");
  const btnExcel       = document.getElementById("btnExcel");
  const sheetsUrl      = document.getElementById("sheetsUrl");
  const urlInput       = document.getElementById("urlInput");
  const connectBtn     = document.getElementById("connectBtn");
  const connectedInfo  = document.getElementById("connectedInfo");
  const connectedTitle = document.getElementById("connectedTitle");
  const disconnectBtn  = document.getElementById("disconnectBtn");

  const btnAppend      = document.getElementById("btnAppend");
  const btnNew         = document.getElementById("btnNew");
  const actionCard     = document.getElementById("actionCard");

  const submitBtn      = document.getElementById("submitBtn");
  const statusEl       = document.getElementById("status");
  const resultArea     = document.getElementById("resultArea");

  // ── State ──
  let selectedFile   = null;
  let parsedRecord   = null;
  let rawData        = null;
  let destination    = null;   // "sheets" | "excel"
  let action         = null;   // "append" | "new"
  let sheetsLinked   = false;

  // ── File pick / drop ──
  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => { if (e.target.files[0]) handleFile(e.target.files[0]); });

  dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("hover"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("hover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault(); dropZone.classList.remove("hover");
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });

  function handleFile(file) {
    const ok = ["image/png", "image/jpeg", "image/webp", "image/gif"];
    if (!ok.includes(file.type)) { showStatus("Please upload an image file.", "error"); return; }
    selectedFile = file;
    parsedRecord = null; rawData = null;
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewWrap.style.display = "block";
      previewName.textContent = file.name;
      dropZone.style.display = "none";
    };
    reader.readAsDataURL(file);
    updateUI();
  }

  removeBtn.addEventListener("click", () => {
    selectedFile = null; parsedRecord = null; rawData = null;
    previewWrap.style.display = "none";
    dropZone.style.display = "block";
    fileInput.value = "";
    updateUI();
  });

  // ── Destination choice ──
  btnSheets.addEventListener("click", () => setDest("sheets"));
  btnExcel.addEventListener("click", () => setDest("excel"));

  function setDest(d) {
    destination = d;
    btnSheets.classList.toggle("active", d === "sheets");
    btnExcel.classList.toggle("active", d === "excel");
    sheetsUrl.classList.toggle("show", d === "sheets" && !sheetsLinked);
    // Show action card for sheets, hide for excel (excel always = new file)
    if (d === "sheets" && sheetsLinked) {
      actionCard.style.display = "block";
    } else if (d === "sheets" && !sheetsLinked) {
      actionCard.style.display = "none";
    } else {
      actionCard.style.display = "none";
      action = "new";
    }
    updateUI();
  }

  // ── Action choice ──
  btnAppend.addEventListener("click", () => setAction("append"));
  btnNew.addEventListener("click", () => setAction("new"));

  function setAction(a) {
    action = a;
    btnAppend.classList.toggle("active", a === "append");
    btnNew.classList.toggle("active", a === "new");
    updateUI();
  }

  // ── Google Sheets connect ──
  connectBtn.addEventListener("click", connectSheets);
  disconnectBtn.addEventListener("click", disconnectSheets);

  async function connectSheets() {
    const url = urlInput.value.trim();
    if (!url) return;
    connectBtn.textContent = "…";
    try {
      const res = await fetch("/sheets/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) { showStatus(data.error || "Connection failed", "error"); return; }
      sheetsLinked = true;
      connectedTitle.textContent = data.title;
      connectedInfo.style.display = "flex";
      sheetsUrl.classList.remove("show");
      actionCard.style.display = "block";
      action = "append";
      btnAppend.classList.add("active");
      btnNew.classList.remove("active");
      updateUI();
    } catch (e) {
      showStatus("Network error: " + e.message, "error");
    } finally {
      connectBtn.textContent = "Link";
    }
  }

  async function disconnectSheets() {
    await fetch("/sheets/disconnect", { method: "POST" });
    sheetsLinked = false;
    connectedInfo.style.display = "none";
    actionCard.style.display = "none";
    if (destination === "sheets") sheetsUrl.classList.add("show");
    action = null;
    btnAppend.classList.remove("active");
    btnNew.classList.remove("active");
    updateUI();
  }

  // Check if already connected on load
  fetch("/sheets/status").then(r => r.json()).then(s => {
    if (s.connected) {
      sheetsLinked = true;
      connectedInfo.style.display = "flex";
      urlInput.value = s.sheet_url || "";
    }
  });

  // ── Submit ──
  submitBtn.addEventListener("click", runFlow);

  async function runFlow() {
    if (!selectedFile) return;
    resultArea.innerHTML = "";
    hideStatus();

    // Step 1: parse
    showStatus('<span class="spinner"></span> Reading receipt…', "loading");
    submitBtn.disabled = true;

    const fd = new FormData();
    fd.append("file", selectedFile);
    try {
      const res = await fetch("/parse", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) { showStatus(data.error || "Parse failed", "error"); submitBtn.disabled = false; return; }
      parsedRecord = data.record;
      rawData = data.raw;
    } catch (e) {
      showStatus("Network error: " + e.message, "error"); submitBtn.disabled = false; return;
    }

    // Step 2: send to destination
    const dest = destination === "sheets" && action === "append" ? "sheets" : "excel";
    const act  = action || "new";
    showStatus('<span class="spinner"></span> Saving…', "loading");

    try {
      const res = await fetch("/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ record: parsedRecord, destination: dest, action: act }),
      });
      const data = await res.json();
      if (!res.ok) { showStatus(data.error || "Save failed", "error"); submitBtn.disabled = false; return; }

      // Success
      let msg = data.message || "Done!";
      showStatus("✓ " + msg, "success");

      // Show parsed record preview
      renderRecord(parsedRecord);

      // Download link for Excel
      if (data.download) {
        const a = document.createElement("a");
        a.href = data.download; a.className = "download-link"; a.textContent = "⬇ Download Excel";
        resultArea.appendChild(a);
      }
    } catch (e) {
      showStatus("Network error: " + e.message, "error");
    }
    submitBtn.disabled = false;
  }

  function renderRecord(r) {
    const fields = [
      ["Date", r.date],
      ["Month", r.month],
      ["Amount", "$" + Number(r.amount).toFixed(2)],
      ["Type", r.type_of_expense],
      ["Description", r.description],
    ];
    let html = '<div class="record-preview"><table>';
    for (const [k, v] of fields) html += `<tr><th>${k}</th><td>${v || "—"}</td></tr>`;
    html += "</table></div>";
    resultArea.innerHTML = html + resultArea.innerHTML;
  }

  // ── Helpers ──
  function showStatus(msg, cls) {
    statusEl.className = "status show " + cls;
    statusEl.innerHTML = msg;
  }
  function hideStatus() { statusEl.className = "status"; }

  function updateUI() {
    const ready = selectedFile && destination &&
      (destination === "excel" || (destination === "sheets" && sheetsLinked && action));
    submitBtn.disabled = !ready;
  }
})();
