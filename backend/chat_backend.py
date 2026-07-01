from flask import Flask, request, jsonify
from psycopg2 import pool
import ollama
import os
import threading
from functools import lru_cache
from dotenv import load_dotenv
from typing import TypedDict, List
from langgraph.graph import StateGraph, END

# ---------------------------------------------------------
# STATE
# ---------------------------------------------------------

class AgentState(TypedDict):
    query: str
    context: List[str]
    answer: str

load_dotenv()

# ---------------------------------------------------------
# SEMÁFORO LLM — solo 1 inferencia a la vez
# ---------------------------------------------------------

_llm_semaphore = threading.Semaphore(1)

# ---------------------------------------------------------
# POSTGRES POOL
# ---------------------------------------------------------

db_pool = pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=3,
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)

# ---------------------------------------------------------
# EMBEDDINGS CON CACHÉ
# ---------------------------------------------------------

MAX_EMBED_CHARS = 1500

@lru_cache(maxsize=256)
def embed_text(text: str):
    text = text[:MAX_EMBED_CHARS]
    return tuple(
        ollama.embeddings(model="bge-m3", prompt=text)["embedding"]
    )

# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

def search_similar(query: str, top_k: int = 5):
    emb = list(embed_text(query))

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc_name, page, content
                FROM documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (emb, top_k * 2)
            )
            rows = cur.fetchall()
    finally:
        db_pool.putconn(conn)

    context = []
    for doc_name, page, content in rows:
        if content and len(content.strip()) > 40:
            context.append(f"[{doc_name} - pág {page}] {content}")
        if len(context) >= top_k:
            break

    return context

# ---------------------------------------------------------
# RETRIEVAL NODE
# ---------------------------------------------------------

def retrieval_node(state: AgentState):
    query = state["query"].strip()
    query_lower = query.lower()

    if any(x in query_lower for x in ["donde", "ubicación", "direccion", "sucursal"]):
        context = search_similar(query, top_k=6)
    else:
        context = search_similar(query, top_k=5)

    return {"context": context}

# ---------------------------------------------------------
# GENERATION NODE
# ---------------------------------------------------------

def chat_node(state: AgentState):
    context_text = "\n".join(state["context"])

    system_prompt = """
Eres un asistente RAG especializado en documentos.

REGLAS OBLIGATORIAS:
- Usa SOLO el contexto entregado.
- NO inventes información.
- Si no está en el contexto, responde: "No se encontró información en los documentos".
- Si hay direcciones o ubicaciones, enuméralas claramente.
- Responde en formato claro y estructurado.
- Incluye referencias como [documento - página] cuando sea posible.
"""

    prompt = f"""
CONTEXTO:
{context_text}

PREGUNTA:
{state['query']}
"""

    with _llm_semaphore:
        response = ollama.chat(
            model="qwen2.5:3b",
            options={
                "num_predict": 180,
                "temperature": 0.1,
                "num_thread": 4,
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

    return {"answer": response["message"]["content"]}

# ---------------------------------------------------------
# LANGGRAPH
# ---------------------------------------------------------

workflow = StateGraph(AgentState)

workflow.add_node("retrieval", retrieval_node)
workflow.add_node("generator", chat_node)

workflow.set_entry_point("retrieval")
workflow.add_edge("retrieval", "generator")
workflow.add_edge("generator", END)

app_graph = workflow.compile()

# ---------------------------------------------------------
# FLASK API
# ---------------------------------------------------------

app = Flask(__name__)

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)

    if not data or "query" not in data:
        return jsonify({"error": "query requerida"}), 400

    query = data["query"]

    result = app_graph.invoke({"query": query})

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT doc_name
                FROM documents
                ORDER BY doc_name;
            """)
            docs = [r[0] for r in cur.fetchall()]
    finally:
        db_pool.putconn(conn)

    return jsonify({
        "documents": docs,
        "answer": result["answer"]
    })

# ---------------------------------------------------------
# RUN — usar solo para desarrollo local
# Para producción: gunicorn app:app --workers 1 --threads 4 --timeout 120 --bind 127.0.0.1:6000 --worker-class gthread
# ---------------------------------------------------------

if __name__ == "__main__":
    print("Chat RAG iniciado en puerto 6000")
    app.run(
        host="127.0.0.1",
        port=6000,
        debug=False,
        threaded=False   # False porque el semáforo maneja concurrencia
    )
