# 🏪 Mercado Central 24H – Asistente Inteligente de Documentos (RAG + AI)

Sistema de recuperación aumentada por IA (RAG) que permite consultar documentos internos en lenguaje natural usando embeddings, PostgreSQL + pgvector y modelos LLM locales con Ollama.

---

## 🚀 Demo del Proyecto

El sistema permite:

- 📄 Subir documentos PDF
- 🧠 Convertirlos en embeddings semánticos
- 🔎 Buscar información relevante con similitud vectorial
- 💬 Consultar los documentos en lenguaje natural
- ⚡ Generar respuestas con IA local (Llama 3.1)

---

## 🏗️ Arquitectura del Sistema

```text
Frontend (HTML + JS)
        │
        ▼
Node.js (Express + Multer)
        │
        ├── Guarda archivos PDF
        └── Llama backend Python (Flask Embeddings)
                │
                ▼
        PostgreSQL + pgvector
                │
                ▼
        Ollama (bge-m3 + llama3.1)

