const chatBox = document.getElementById("chatBox");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");

const docList = document.getElementById("docList");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const progress = document.getElementById("progress");

// ---------------- CHAT ----------------

sendBtn.onclick = sendMessage;

async function sendMessage() {

    const text = userInput.value.trim();
    if (!text) return;

    addMsg("user", text);
    userInput.value = "";

    try {

        const res = await fetch("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({query: text})
        });

        const data = await res.json();

        renderDocs(data.documents);

        addMsg("bot", marked.parse(data.answer));

    } catch (e) {
        addMsg("bot", "❌ Error conectando con el servidor");
        console.error(e);
    }
}

// ---------------- UI CHAT ----------------

function addMsg(type, text) {

    const div = document.createElement("div");
    div.className = "msg " + type;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = text;

    div.appendChild(bubble);
    chatBox.appendChild(div);

    chatBox.scrollTop = chatBox.scrollHeight;
}

// ---------------- DOCUMENTOS ----------------

async function loadDocs() {

    try {

        const res = await fetch("/api/embed/documents");
        const data = await res.json();

        renderDocs(data);

    } catch (e) {
        console.error("Error docs:", e);
    }
}

function renderDocs(docs) {

    docList.innerHTML = "";

    docs.forEach(d => {

        const span = document.createElement("span");
        span.className = "badge bg-secondary badge-doc";
        span.innerText = d.doc_name;

        docList.appendChild(span);
    });
}

// ---------------- UPLOAD ----------------

uploadBtn.onclick = uploadFile;

function uploadFile() {

    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload");

    xhr.upload.onprogress = (e) => {

        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            progress.style.width = percent + "%";
            progress.innerText = Math.round(percent) + "%";
        }
    };

    xhr.onload = () => {

        progress.style.width = "100%";
        progress.innerText = "OK";

        loadDocs();
    };

    xhr.onerror = () => {
        progress.style.width = "100%";
        progress.innerText = "ERROR";
        progress.classList.add("bg-danger");
    };

    xhr.send(formData);
}

// ---------------- INIT ----------------

loadDocs();
addMsg("bot", "👋 Bienvenido a Mercado Central 24H. Puedes consultar documentos o subir nuevos archivos.");
