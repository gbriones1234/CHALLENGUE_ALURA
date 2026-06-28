import psycopg2
import ollama
import os
from dotenv import load_dotenv
import PyPDF2

# Carga de variables
load_dotenv()

# Conexión optimizada
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)
cur = conn.cursor()

# Configuración de base de datos
cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        content TEXT,
        embedding VECTOR(1024)
    );
""")
# IMPORTANTE: Crear índice para búsquedas rápidas (HNSW)
cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_hnsw ON documents USING hnsw (embedding vector_cosine_ops);")
conn.commit()

def get_text_chunks(text, chunk_size=500, overlap=50):
    """Divide el texto en trozos con solapamiento para mantener contexto."""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

def embed_text(text):
    """Obtiene el embedding desde Ollama."""
    return ollama.embeddings(model="bge-m3", prompt=text)["embedding"]

def load_pdf(path):
    reader = PyPDF2.PdfReader(path)
    for page in reader.pages:
        text = page.extract_text()
        if text:
            chunks = get_text_chunks(text)
            for chunk in chunks:
                emb = embed_text(chunk)
                # Psycopg2 maneja la lista de floats como vector automáticamente si la extensión está activa
                cur.execute(
                    "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
                    (chunk, emb)
                )
    conn.commit()
    print("Documento procesado con éxito.")

if __name__ == "__main__":
    load_pdf("documentos/ed99ddc6-bead-47fd-886b-c007c7e36885.pdf")

