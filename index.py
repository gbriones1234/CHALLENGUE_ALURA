import psycopg2
import ollama
import csv
from PyPDF2 import PdfReader

# Conexión a Postgres con pgvector
conn = psycopg2.connect("dbname=vector_db user=postgres password=postgres host=localhost")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding VECTOR(1024)
);
""")
conn.commit()

def embed_text(text):
    response = ollama.embeddings(model="qwen3-embedding", prompt=text)
    return response["embedding"]

def load_csv(file_path):
    with open(file_path, newline='', encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            text = " ".join(row)
            emb = embed_text(text)
            cur.execute("INSERT INTO documents (content, embedding) VALUES (%s, %s)", (text, emb))
    conn.commit()

def load_pdf(file_path):
    reader = PdfReader(file_path)
    for page in reader.pages:
        text = page.extract_text()
        if text:
            emb = embed_text(text)
            cur.execute("INSERT INTO documents (content, embedding) VALUES (%s, %s)", (text, emb))
    conn.commit()

if __name__ == "__main__":
    # Cambia aquí según el tipo de archivo
    load_csv("data.csv")
    # load_pdf("documento.pdf")
    print("Archivo cargado y vectorizado en Postgres.")

