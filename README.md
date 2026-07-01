# 🚀 Chat Backend sobre OCI Oracle Linux 9 ARM

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

```
Este proyecto implementa un **backend de chat inteligente** que combina recuperación de información desde documentos almacenados en **PostgreSQL** con generación de respuestas mediante **modelos de lenguaje (LLMs)**.  
La arquitectura está desplegada en **Oracle Cloud Infrastructure (OCI)** sobre **Oracle Linux 9 ARM64**, optimizada para entornos empresariales y de alta disponibilidad.

---

## 🧩 Tecnologías utilizadas

- **[Flask](ca://s?q=Flask_framework)** → Framework ligero en Python para construir APIs REST.
- **[PostgreSQL + pgvector](ca://s?q=Postgres_pgvector)** → Base de datos relacional con soporte para búsquedas semánticas mediante embeddings.
- **[Oracle Linux 9 ARM64](ca://s?q=Oracle_Linux_9_ARM64)** → Sistema operativo robusto y optimizado para OCI.
- **[OCI (Oracle Cloud Infrastructure)](ca://s?q=Oracle_Cloud_Infrastructure)** → Plataforma cloud donde corre el backend.
- **[LangGraph](ca://s?q=LangGraph)** → Orquestación de flujos conversacionales con nodos de recuperación y generación.
- **[Ollama](ca://s?q=Ollama_embeddings_y_chat)** → Motor de embeddings (`bge-m3`) y chat (`llama3.1`) para procesamiento de lenguaje natural.
- **[dotenv](ca://s?q=python_dotenv)** → Manejo seguro de variables de entorno y credenciales.
- **[psycopg2](ca://s?q=psycopg2_postgres_python)** → Conector de Python para PostgreSQL.

---

## 📐 Arquitectura del flujo

1. **Usuario envía consulta** vía endpoint `/api/chat`.
2. **Embeddings** de la consulta se generan con `bge-m3`.
3. **Recuperación semántica** en PostgreSQL usando `pgvector`.
4. **LangGraph** dirige el flujo:
   - Nodo de recuperación → obtiene contexto relevante.
   - Nodo de generación → construye respuesta con `llama3.1`.
5. **Respuesta final** se devuelve en formato JSON, junto con la lista de documentos consultados.

---

## ⚙️ Instalación y ejecución en OCI Oracle Linux 9 ARM

```bash
# Clonar el repositorio
git clone https://github.com/gbriones1234/CHALLENGUE_ALURA.git

cd chat-backend-oracle

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno en .env
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=5432

# Ejecutar servidor Flask
python chat_backend.py



