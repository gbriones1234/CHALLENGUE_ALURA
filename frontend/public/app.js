const chatWindow = document.getElementById("chatWindow");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const docList = document.getElementById("docList");

// Enviar mensaje al backend de chat
sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  userInput.value = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text })
    });

    const data = await response.json();

    // Actualizar documentos cargados
    renderDocuments(data.documents);

    // Mostrar respuesta del bot en Markdown
    appendMessage("bot", marked.parse(data.answer));
  } catch (err) {
    appendMessage("bot", "<span class='text-danger'>Error al conectar con el backend</span>");
    console.error(err);
  }
}

// Subida de documentos
const dropzone = document.getElementById("dropzone");
const progressBar = document.getElementById("progress");

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

document.getElementById("uploadBtn").addEventListener("click", () => {
  const file = document.getElementById("fileInput").files[0];
  if (file) uploadFile(file);
});

function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  progressBar.style.width = "0%";
  progressBar.innerText = "0%";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/embed/upload", true);

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const percent = Math.round((e.loaded / e.total) * 100);
      progressBar.style.width = percent + "%";
      progressBar.innerText = percent + "%";
    }
  };

  xhr.onloadstart = () => {
    progressBar.classList.add("progress-bar-animated");
  };

  xhr.onload = () => {
    progressBar.classList.remove("progress-bar-animated");
    progressBar.style.width = "100%";
    progressBar.innerText = "Completado";
    loadDocuments();
  };

  xhr.onerror = () => {
    progressBar.classList.remove("progress-bar-animated");
    progressBar.classList.add("bg-danger");
    progressBar.innerText = "Error";
  };

  xhr.send(formData);
}

// Listar documentos cargados
async function loadDocuments() {
  try {
    const response = await fetch("/api/embed/documents");
    const docs = await response.json();
    renderDocuments(docs);
  } catch (err) {
    console.error("Error al listar documentos:", err);
  }
}

function appendMessage(sender, text) {
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message", sender === "user" ? "user-msg" : "bot-msg");

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.innerHTML = text;

  msgDiv.appendChild(bubble);
  chatWindow.appendChild(msgDiv);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function renderDocuments(docs) {
  docList.innerHTML = "";
  docs.forEach(doc => {
    const badge = document.createElement("span");
    badge.classList.add("badge", "bg-secondary", "me-1", "mb-1");
    badge.innerText = doc;
    docList.appendChild(badge);
  });
}

// Cargar documentos al inicio
loadDocuments();

