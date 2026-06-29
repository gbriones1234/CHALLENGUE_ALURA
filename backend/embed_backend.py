from flask import Flask, request, jsonify
import psycopg2, ollama, os, PyPDF2
from dotenv import load_dotenv

load_dotenv()

# Conexión a Postgres
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)
cur = conn.cursor()

# Extensión vector y tabla
cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        doc_name TEXT,
        content TEXT,
        embedding VECTOR(1024)
    );
""")
cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_hnsw ON documents USING hnsw (embedding vector_cosine_ops);")
conn.commit()

# Funciones auxiliares
def get_text_chunks(text, chunk_size=500, overlap=50):
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

def embed_text(text):
    return ollama.embeddings(model="bge-m3", prompt=text)["embedding"]

def load_pdf(path):
    doc_name = os.path.basename(path)  # nombre del archivo
    reader = PyPDF2.PdfReader(path)
    for page in reader.pages:
        text = page.extract_text()
        if text:
            chunks = get_text_chunks(text)
            for chunk in chunks:
                emb = embed_text(chunk)
                cur.execute(
                    "INSERT INTO documents (doc_name, content, embedding) VALUES (%s, %s, %s)",
                    (doc_name, chunk, emb)
                )
    conn.commit()

# Flask app
app = Flask(__name__)

@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json()
    path = data["path"]
    load_pdf(path)
    return jsonify({"status": "ok", "file": path})

@app.route("/documents", methods=["GET"])
def list_docs():
    cur.execute("SELECT DISTINCT doc_name FROM documents ORDER BY doc_name;")
    rows = cur.fetchall()
    return jsonify([{"doc_name": r[0]} for r in rows])

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)

