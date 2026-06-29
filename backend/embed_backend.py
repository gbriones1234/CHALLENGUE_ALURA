from flask import Flask, request, jsonify
import psycopg2
import ollama
import os
import re
import hashlib
import PyPDF2
from psycopg2.extras import execute_values
import traceback
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# CONEXION POSTGRES
# ---------------------------------------------------------

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)

cur = conn.cursor()

# ---------------------------------------------------------
# TABLA
# ---------------------------------------------------------

cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

cur.execute("""
CREATE TABLE IF NOT EXISTS documents (

    id SERIAL PRIMARY KEY,

    doc_name TEXT NOT NULL,

    page INTEGER,

    chunk_id INTEGER,

    content TEXT NOT NULL,

    embedding VECTOR(1024)

);
""")

cur.execute("""

CREATE INDEX IF NOT EXISTS idx_documents_hnsw

ON documents

USING hnsw (embedding vector_cosine_ops);

""")

conn.commit()

# ---------------------------------------------------------
# LIMPIEZA DEL TEXTO
# ---------------------------------------------------------

def clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.replace("\n", " ")
    text = text.replace("\t", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()

# ---------------------------------------------------------
# CHUNKING
# ---------------------------------------------------------

def get_text_chunks(text, chunk_size=700, overlap=120):

    text = clean_text(text)

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if len(chunk) >= 120:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks

# ---------------------------------------------------------
# HASH DEL CHUNK
# (nos servirá para detectar duplicados)
# ---------------------------------------------------------

def chunk_hash(chunk: str):

    return hashlib.sha256(
        chunk.encode("utf-8")
    ).hexdigest()

# ---------------------------------------------------------
# EMBEDDING
# ---------------------------------------------------------

def embed_text(text):

    response = ollama.embeddings(
        model="bge-m3",
        prompt=text
    )

    embedding = response["embedding"]

    if len(embedding) != 1024:
        raise Exception(
            "Embedding inválido generado por Ollama"
        )

    return embedding


# ---------------------------------------------------------
# CARGA DEL PDF
# ---------------------------------------------------------
def load_pdf(path):

    if not os.path.exists(path):
        raise FileNotFoundError(path)

    doc_name = os.path.basename(path)

    print("=" * 70)
    print(f"Indexando: {doc_name}")

    try:

        cur.execute(
            "DELETE FROM documents WHERE doc_name=%s",
            (doc_name,)
        )

        conn.commit()

        reader = PyPDF2.PdfReader(path)

        total_pages = len(reader.pages)

        rows = []

        total_chunks = 0

        for page_number, page in enumerate(reader.pages, start=1):

            print(f"Procesando página {page_number}/{total_pages}")

            text = page.extract_text()

            if not text:
                continue

            text = clean_text(text)

            chunks = get_text_chunks(text)

            for chunk_number, chunk in enumerate(chunks, start=1):

                try:

                    embedding = embed_text(chunk)

                    rows.append(

                        (
                            doc_name,
                            page_number,
                            chunk_number,
                            chunk,
                            embedding
                        )

                    )

                    total_chunks += 1

                except Exception as e:

                    print(e)

        if rows:

            execute_values(

                cur,

                """
                INSERT INTO documents
                (
                    doc_name,
                    page,
                    chunk_id,
                    content,
                    embedding
                )
                VALUES %s
                """,

                rows,

                page_size=100

            )

        conn.commit()

        print("-" * 70)
        print(f"Documento : {doc_name}")
        print(f"Páginas   : {total_pages}")
        print(f"Chunks    : {total_chunks}")
        print("Carga completada")
        print("=" * 70)

    except Exception as e:

        conn.rollback()

        raise e

# Flask app
app = Flask(__name__)


@app.route("/api/embed/upload", methods=["POST"])
def upload():

    try:


        data = request.get_json(silent=True)

        if data is None:
            return jsonify({
                "status": "error",
                "message": "Debe enviar Content-Type: application/json"
            }), 400

        path = data.get("path")

        if not path:
            return jsonify({
                "status": "error",
                "message": "Debe indicar path"
            }), 400

        load_pdf(path)

        return jsonify({
            "status": "ok",
            "file": os.path.basename(path)
        })

    except Exception as e:
        traceback.print_exc()

        return jsonify({
            "status": "error",
            "type": type(e).__name__,
            "message": str(e)
        }), 500


@app.route("/api/embed/documents", methods=["GET"])
def list_docs():

    cur.execute("""

        SELECT DISTINCT doc_name

        FROM documents

        ORDER BY doc_name

    """)

    rows = cur.fetchall()

    return jsonify(

        [

            {

                "doc_name": r[0]

            }

            for r in rows

        ]

    )



if __name__ == "__main__":

    print("=" * 70)
    print("Servicio de Embeddings iniciado")
    print("Puerto : 5000")
    print("=" * 70)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
