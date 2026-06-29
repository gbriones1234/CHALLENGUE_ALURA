from flask import Flask, request, jsonify
import psycopg2
import ollama
import os
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
# POSTGRES
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
# EMBEDDINGS
# ---------------------------------------------------------

def embed_text(text: str):
    return ollama.embeddings(
        model="bge-m3",
        prompt=text
    )["embedding"]

# ---------------------------------------------------------
# SEARCH MEJORADO
# ---------------------------------------------------------

def search_similar(query: str, top_k: int = 5):

    emb = embed_text(query)

    cur.execute(
        """
        SELECT doc_name, page, content
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (emb, top_k * 3)
    )

    rows = cur.fetchall()

    context = []

    for doc_name, page, content in rows:

        # filtro básico de calidad
        if content and len(content.strip()) > 40:

            context.append(
                f"[{doc_name} - pág {page}] {content}"
            )

        if len(context) >= top_k:
            break

    return context

# ---------------------------------------------------------
# RETRIEVAL NODE
# ---------------------------------------------------------

def retrieval_node(state: AgentState):

    query = state["query"].strip()

    query_lower = query.lower()

    # fallback inteligente
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

    response = ollama.chat(
        model="llama3.1",
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

    # devolver docs únicos usados en contexto
    cur.execute("""
        SELECT DISTINCT doc_name
        FROM documents
        ORDER BY doc_name;
    """)

    docs = [r[0] for r in cur.fetchall()]

    return jsonify({
        "documents": docs,
        "answer": result["answer"]
    })


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == "__main__":

    print("Chat RAG iniciado en puerto 6000")

    app.run(
        host="127.0.0.1",
        port=6000,
        debug=False,
        threaded=True
    )
