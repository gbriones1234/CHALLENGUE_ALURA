// ─────────────────────────────────────────
//  REFS
// ─────────────────────────────────────────

const chatBox    = document.getElementById("chatBox");
const userInput  = document.getElementById("userInput");
const sendBtn    = document.getElementById("sendBtn");

const docList    = document.getElementById("docList");
const dropzone   = document.getElementById("dropzone");
const fileInput  = document.getElementById("fileInput");
const fileSelected = document.getElementById("fileSelected");
const fileName   = document.getElementById("fileName");
const fileClear  = document.getElementById("fileClear");
const uploadBtn  = document.getElementById("uploadBtn");
const uploadBtnText = document.getElementById("uploadBtnText");
const progressWrap  = document.getElementById("progressWrap");
const barFill    = document.getElementById("barFill");
const barLabel   = document.getElementById("barLabel");
const toast      = document.getElementById("toast");

// ─────────────────────────────────────────
//  TOAST
// ─────────────────────────────────────────

let toastTimer;
function showToast(msg, type = "ok") {
  clearTimeout(toastTimer);
  toast.textContent = msg;
  toast.className = `show ${type}`;
  toastTimer = setTimeout(() => { toast.className = ""; }, 3200);
}

// ─────────────────────────────────────────
//  AUTO-RESIZE TEXTAREA
// ─────────────────────────────────────────

userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 140) + "px";
});

// ─────────────────────────────────────────
//  ENTER TO SEND  (Shift+Enter = newline)
// ─────────────────────────────────────────

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

// ─────────────────────────────────────────
//  SEND MESSAGE
// ─────────────────────────────────────────

let isSending = false;

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || isSending) return;

  isSending = true;
  sendBtn.disabled = true;

  addMsg("user", text);
  userInput.value = "";
  userInput.style.height = "auto";

  // Thinking bubble
  const { wrapper: thinkWrapper, steps } = addThinking();

  try {
    // Step 1 — embed
    activateStep(steps, 0);
    await delay(400);

    // Step 2 — vector search
    activateStep(steps, 1);

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text })
    });

    // Step 3 — generating
    doneStep(steps, 1);
    activateStep(steps, 2);
    await delay(300);

    const data = await res.json();

    doneStep(steps, 2);
    await delay(200);

    // Remove thinking bubble, add answer
    thinkWrapper.remove();
    addMsg("bot", marked.parse(data.answer));

    if (data.documents) renderDocs(data.documents);

  } catch (e) {
    thinkWrapper.remove();
    addMsg("bot", "❌ Error conectando con el servidor.");
    showToast("Error de conexión con el servidor", "err");
    console.error(e);
  } finally {
    isSending = false;
    sendBtn.disabled = false;
    userInput.focus();
  }
}

// ─────────────────────────────────────────
//  THINKING BUBBLE
// ─────────────────────────────────────────

const THINKING_STEPS = [
  { icon: "🔍", label: "Generando embedding de la consulta…" },
  { icon: "⚡", label: "Buscando en vectores (pgvector)…"    },
  { icon: "🧠", label: "Generando respuesta con el modelo…"  }
];

function addThinking() {
  const wrapper = document.createElement("div");
  wrapper.className = "msg bot";

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = "🤖";

  const bubble = document.createElement("div");
  bubble.className = "thinking-bubble";

  const stepEls = THINKING_STEPS.map(({ icon, label }) => {
    const row = document.createElement("div");
    row.className = "thinking-step";

    const iconEl = document.createElement("span");
    iconEl.className = "step-icon";
    iconEl.textContent = icon;

    const spinner = document.createElement("div");
    spinner.className = "spinner";
    spinner.style.display = "none";

    const check = document.createElement("span");
    check.className = "check";
    check.textContent = "✓";
    check.style.display = "none";

    const text = document.createElement("span");
    text.textContent = label;

    row.appendChild(iconEl);
    row.appendChild(spinner);
    row.appendChild(check);
    row.appendChild(text);
    bubble.appendChild(row);

    return { row, spinner, check };
  });

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  chatBox.appendChild(wrapper);
  scrollBottom();

  return { wrapper, steps: stepEls };
}

function activateStep(steps, index) {
  steps.forEach((s, i) => {
    if (i < index) return; // already done
    if (i === index) {
      s.row.classList.add("active");
      s.spinner.style.display = "block";
    }
  });
  scrollBottom();
}

function doneStep(steps, index) {
  const s = steps[index];
  s.spinner.style.display = "none";
  s.check.style.display   = "inline";
  s.row.classList.remove("active");
  s.row.classList.add("done");
}

// ─────────────────────────────────────────
//  MESSAGES
// ─────────────────────────────────────────

function addMsg(type, html) {
  const wrapper = document.createElement("div");
  wrapper.className = `msg ${type}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = type === "user" ? "👤" : "🤖";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = html;

  if (type === "user") {
    wrapper.appendChild(bubble);
    wrapper.appendChild(avatar);
  } else {
    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
  }

  chatBox.appendChild(wrapper);
  scrollBottom();
}

function scrollBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

// ─────────────────────────────────────────
//  DOCUMENTS
// ─────────────────────────────────────────

async function loadDocs() {
  try {
    const res  = await fetch("/api/embed/documents");
    const data = await res.json();
    renderDocs(data);
  } catch (e) {
    console.error("Error cargando docs:", e);
  }
}

function renderDocs(docs) {
  docList.innerHTML = "";

  const list = Array.isArray(docs)
    ? docs
    : (docs.documents || []).map(d => d.doc_name || d);

  if (!list.length) {
    docList.innerHTML = '<span class="no-docs">Sin documentos aún</span>';
    return;
  }

  list.forEach(name => {
    const badge = document.createElement("div");
    badge.className = "doc-badge";
    badge.innerHTML = `<span class="dot"></span><span title="${name}">${name}</span>`;
    docList.appendChild(badge);
  });
}

// ─────────────────────────────────────────
//  DROPZONE + FILE INPUT
// ─────────────────────────────────────────

// Click en dropzone abre el file picker
dropzone.addEventListener("click", () => fileInput.click());

// Drag events
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag-over");
});

["dragleave", "dragend"].forEach(evt =>
  dropzone.addEventListener(evt, () => dropzone.classList.remove("drag-over"))
);

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  const file = e.dataTransfer?.files?.[0];
  if (file) setFile(file);
});

// Selección manual
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

// Quitar archivo seleccionado
fileClear.addEventListener("click", (e) => {
  e.stopPropagation();
  clearFile();
});

function setFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showToast("Solo se aceptan archivos PDF", "err");
    return;
  }
  // Sincronizar con el input real para reusar el flujo XHR
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;

  fileName.textContent = file.name;
  fileSelected.style.display = "flex";
  dropzone.style.display = "none";
  uploadBtn.disabled = false;
}

function clearFile() {
  fileInput.value = "";
  fileSelected.style.display = "none";
  dropzone.style.display = "block";
  uploadBtn.disabled = true;
  resetProgress();
}

// ─────────────────────────────────────────
//  UPLOAD
// ─────────────────────────────────────────

uploadBtn.addEventListener("click", uploadFile);

function uploadFile() {
  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  uploadBtn.disabled = true;
  uploadBtnText.textContent = "Subiendo…";
  progressWrap.style.display = "block";
  setProgress(0);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload");

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) setProgress((e.loaded / e.total) * 100);
  };

  xhr.onload = () => {
    setProgress(100);
    barLabel.textContent = "Completado";
    showToast(`✅ "${file.name}" subido correctamente`);
    uploadBtnText.textContent = "Subir documento";
    setTimeout(() => {
      clearFile();
      loadDocs();
    }, 1200);
  };

  xhr.onerror = () => {
    barFill.style.background = "var(--danger)";
    barLabel.textContent = "Error al subir";
    showToast("Error al subir el archivo", "err");
    uploadBtn.disabled = false;
    uploadBtnText.textContent = "Subir documento";
  };

  xhr.send(formData);
}

function setProgress(pct) {
  barFill.style.width  = pct + "%";
  barLabel.textContent = Math.round(pct) + "%";
}

function resetProgress() {
  progressWrap.style.display = "none";
  barFill.style.width  = "0%";
  barFill.style.background = "";
  barLabel.textContent = "0%";
}

// ─────────────────────────────────────────
//  UTILS
// ─────────────────────────────────────────

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─────────────────────────────────────────
//  INIT
// ─────────────────────────────────────────

loadDocs();
addMsg("bot", "👋 Bienvenido al asistente de <strong>Mercado Central 24H</strong>.<br>Puedes hacerme preguntas sobre los documentos o subir nuevos archivos PDF.");
