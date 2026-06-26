import psycopg2
import ollama
from langgraph.graph import Graph

conn = psycopg2.connect("dbname=vector_db user=postgres password=postgres host=localhost")
cur = conn.cursor()

def search_similar(query, top_k=3):
    emb = ollama.embeddings(model="qwen3-embedding", prompt=query)["embedding"]
    cur.execute("SELECT content FROM documents ORDER BY embedding <-> %s LIMIT %s", (emb, top_k))
    return [row[0] for row in cur.fetchall()]

def chat_with_context(query):
    context = search_similar(query)
    prompt = f"Contexto:\n{context}\n\nPregunta:\n{query}"
    response = ollama.chat(model="phi3", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]

graph = Graph()

@graph.node
def input_node(state):
    return {"query": state["query"]}

@graph.node
def retrieval_node(state):
    results = search_similar(state["query"])
    return {"query": state["query"], "context": results}

@graph.node
def chat_node(state):
    prompt = f"Contexto:\n{state['context']}\n\nPregunta:\n{state['query']}"
    response = ollama.chat(model="phi3", messages=[{"role": "user", "content": prompt}])
    return {"answer": response["message"]["content"]}

graph.add_edge("input_node", "retrieval_node")
graph.add_edge("retrieval_node", "chat_node")

if __name__ == "__main__":
    query = "¿Qué información contiene el documento sobre clientes?"
    result = graph.run({"query": query})
    print("Respuesta:", result["answer"])

