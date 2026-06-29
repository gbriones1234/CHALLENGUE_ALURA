const express = require("express");
const multer = require("multer");
const path = require("path");
const axios = require("axios");

const app = express();
const PORT = 3000;

// Configuración de Multer: guarda con nombre original y extensión
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, path.join(__dirname, "uploads")); // asegura ruta correcta
  },
  filename: function (req, file, cb) {
    cb(null, file.originalname); // conserva nombre y extensión
  }
});

const upload = multer({ storage: storage });

// Servir archivos estáticos (frontend)
app.use(express.static(path.join(__dirname, "public")));

// Endpoint para subir archivos
app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    // Ruta absoluta del archivo subido
    const filePath = path.resolve(__dirname, "uploads", req.file.originalname);

    // Enviar al backend Flask
    const response = await axios.post("http://127.0.0.1:5000/api/embed/upload", {
      path: filePath
    });

    res.json({ status: "ok", backend: response.data });
  } catch (err) {
    console.error("Error al subir archivo:", err.message);
    res.status(500).json({ status: "error", message: err.message });
  }
});

// Endpoint para listar documentos desde backend
app.get("/documents", async (req, res) => {
  try {
    const response = await axios.get("http://127.0.0.1:5000/api/embed/documents");
    res.json(response.data);
  } catch (err) {
    console.error("Error al listar documentos:", err.message);
    res.status(500).json({ status: "error", message: err.message });
  }
});

// Iniciar servidor
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Frontend en http://0.0.0.0:${PORT}`);
});

