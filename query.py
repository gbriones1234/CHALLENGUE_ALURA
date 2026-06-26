import psycopg2
import ollama
import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph

# Cargar variables del archivo .env
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
    emb = ollama.embeddings(model="bge-m3", prompt=text)["embedding"]
    return "[" + ",".join(str(x) for x in emb) + "]"

def search_similar(query, top_k=3):
    emb_str = embed_text(query)
    cur.execute(
        "SELECT content FROM documents ORDER BY embedding <-> %s::vector LIMIT %s",
        (emb_str, top_k)
    )
    return [row[0] for row in cur.fetchall()]

def chat_with_context(query):
    context = search_similar(query)
    prompt = f"Contexto:\n{context}\n\nPregunta:\n{query}"
    response = ollama.chat(model="phi3", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]

# Definir grafo de estados
graph = StateGraph(dict)

def input_node(state):
    return {"query": state["query"]}

def retrieval_node(state):
    results = search_similar(state["query"])
    return {"query": state["query"], "context": results}

def chat_node(state):
    prompt = f"Contexto:\n{state['context']}\n\nPregunta:\n{state['query']}"
    response = ollama.chat(model="gemma:2b", messages=[{"role": "user", "content": prompt}])
    return {"answer": response["message"]["content"]}

graph.add_node("input_node", input_node)
graph.add_node("retrieval_node", retrieval_node)
graph.add_node("chat_node", chat_node)

graph.add_edge("input_node", "retrieval_node")
graph.add_edge("retrieval_node", "chat_node")

graph.set_entry_point("input_node")
graph.set_finish_point("chat_node")

app = graph.compile()

if __name__ == "__main__":
    
    #query = "¿Cuál es el mensaje del director general?"
    query = "Cuál es el oranigrama general de la tienda?"
    result = app.invoke({"query": query})
    print("Respuesta:", result["answer"])

