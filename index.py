import psycopg2
import ollama
import os
from dotenv import load_dotenv
import PyPDF2

# Cargar variables del archivo .env
load_dotenv()

# Conexión a Postgres con pgvector usando variables de entorno
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)
cur = conn.cursor()

# Crear extensión y tabla si no existen
cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        content TEXT,
        embedding VECTOR(1024)
    );
""")
conn.commit()

def embed_text(text):
    emb = ollama.embeddings(model="bge-m3", prompt=text)["embedding"]
    # Convertir lista a string compatible con pgvector
    return "[" + ",".join(str(x) for x in emb) + "]"

def load_pdf(path):
    reader = PyPDF2.PdfReader(path)
    for page in reader.pages:
        text = page.extract_text()
        if text:
            emb_str = embed_text(text)
            cur.execute(
                "INSERT INTO documents (content, embedding) VALUES (%s, %s::vector)",
                (text, emb_str)
            )
    conn.commit()

if __name__ == "__main__":
    load_pdf("documentos/ed99ddc6-bead-47fd-886b-c007c7e36885.pdf")
    print("PDF cargado en la base de datos con embeddings.")

