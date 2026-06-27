import psycopg2
import ollama
import os
from dotenv import load_dotenv
from typing import TypedDict, List
from langgraph.graph import StateGraph, END

# Definir la estructura del estado
class AgentState(TypedDict):
    query: str
    context: List[str]
    answer: str

load_dotenv()

# Conexión (Asegúrate de tener pgvector habilitado)
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
    # Usamos distancia coseno (coseno <=> ) que suele ser mejor para semántica
    cur.execute(
        "SELECT content FROM documents ORDER BY embedding <=> %s::vector LIMIT %s",
        (emb, top_k)
    )
    return [row[0] for row in cur.fetchall()]

# Nodos del Grafo
def retrieval_node(state: AgentState):
    context = search_similar(state["query"])
    return {"context": context}

def chat_node(state: AgentState):
    context_text = "\n".join(state["context"])
    
    # Sistema mejorado para dar más contexto y evitar alucinaciones
    system_prompt = (
        "Eres un asistente experto. Usa el contexto proporcionado para responder a la pregunta del usuario. "
        "Si la respuesta no se encuentra en el contexto, di claramente que no tienes esa información."
    )
    
    prompt = f"Contexto:\n{context_text}\n\nPregunta del usuario:\n{state['query']}"
    
    response = ollama.chat(model="llama3.1", messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ])
    
    return {"answer": response["message"]["content"]}

# Construcción del grafo
workflow = StateGraph(AgentState)

workflow.add_node("retrieval", retrieval_node)
workflow.add_node("generator", chat_node)

workflow.set_entry_point("retrieval")
workflow.add_edge("retrieval", "generator")
workflow.add_edge("generator", END)

app = workflow.compile()

if __name__ == "__main__":
    query_input = "Cuál es el organigrama general de la tienda dame los cargos dame los cargos  ?"
    result = app.invoke({"query": query_input})
    print("\nRespuesta del Asistente:\n", result["answer"])

