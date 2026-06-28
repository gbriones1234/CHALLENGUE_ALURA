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
  xhr.open("POST", "/upload", true);

  // Feedback inicial: subida del archivo
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const percent = Math.round((e.loaded / e.total) * 100);
      progressBar.style.width = percent + "%";
      progressBar.innerText = percent + "%";
    }
  };

  // Cuando termina la subida, el backend empieza embeddings
  xhr.onloadstart = () => {
    progressBar.classList.add("progress-bar-animated");
  };

  xhr.onload = () => {
    // El backend responde solo cuando embeddings terminan
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

async function loadDocuments() {
  try {
    const response = await fetch("/documents");
    const docs = await response.json();
    const container = document.getElementById("documents");
    container.innerHTML = "<h2>Documentos cargados</h2><ul class='list-group'>" +
      docs.map(d => `<li class='list-group-item'>${d.doc_name}</li>`).join("") +
      "</ul>";
  } catch (err) {
    console.error("Error al listar documentos:", err);
  }
}

// cargar al inicio
loadDocuments();

