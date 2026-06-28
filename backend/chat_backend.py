from flask import Flask, request, jsonify
import psycopg2, ollama, os
from dotenv import load_dotenv
from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    query: str
    context: List[str]
    answer: str

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)
cur = conn.cursor()

def embed_text(text):
    return ollama.embeddings(model="bge-m3", prompt=text)["embedding"]

def search_similar(query, top_k=3):
    emb = embed_text(query)
    cur.execute(
        "SELECT content FROM documents ORDER BY embedding <=> %s::vector LIMIT %s",
        (emb, top_k)
    )
    return [row[0] for row in cur.fetchall()]

def retrieval_node(state: AgentState):
    context = search_similar(state["query"])
    return {"context": context}

def chat_node(state: AgentState):
    context_text = "\n".join(state["context"])
    system_prompt = (
        "Eres un asistente experto. Usa el contexto proporcionado para responder. "
        "Si la respuesta no está en el contexto, dilo claramente."
    )
    prompt = f"Contexto:\n{context_text}\n\nPregunta:\n{state['query']}"

    response = ollama.chat(model="llama3.1", messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ])
    return {"answer": response["message"]["content"]}

workflow = StateGraph(AgentState)
workflow.add_node("retrieval", retrieval_node)
workflow.add_node("generator", chat_node)
workflow.set_entry_point("retrieval")
workflow.add_edge("retrieval", "generator")
workflow.add_edge("generator", END)
app_graph = workflow.compile()

app = Flask(__name__)

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    query = data.get("query", "")
    result = app_graph.invoke({"query": query})

    # documentos únicos
    cur.execute("SELECT DISTINCT doc_name FROM documents ORDER BY doc_name;")
    docs = [r[0] for r in cur.fetchall()]

    return jsonify({
        "documents": docs,
        "answer": result["answer"]  # ya en Markdown
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6000, debug=True)

