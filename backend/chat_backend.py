from flask import Flask, request, jsonify
from psycopg2 import pool
import ollama
import os
import re
import io
import base64
import threading
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from functools import lru_cache
from dotenv import load_dotenv
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END

load_dotenv()

# ---------------------------------------------------------
# STATE
# ---------------------------------------------------------

class AgentState(TypedDict):
    query: str
    intent: str
    context: List[str]
    answer: str
    chart: Optional[str]
    suggestions: List[str]

# ---------------------------------------------------------
# SEMÁFORO LLM — solo 1 inferencia a la vez
# ---------------------------------------------------------

_llm_semaphore = threading.Semaphore(1)

# ---------------------------------------------------------
# POSTGRES POOL (RAG de documentos)
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
# EMBEDDINGS CON CACHÉ (RAG de documentos)
# ---------------------------------------------------------

MAX_EMBED_CHARS = 1500

@lru_cache(maxsize=256)
def embed_text(text: str):
    text = text[:MAX_EMBED_CHARS]
    return tuple(
        ollama.embeddings(model="bge-m3", prompt=text)["embedding"]
    )

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
# INVENTARIO — carga en pandas (no pgvector)
# ---------------------------------------------------------

INVENTORY_PATH = os.getenv("INVENTORY_XLSX_PATH", "./Inventario_supermercado.xlsx")
_inventory_lock = threading.Lock()
_INVENTORY_DF: Optional[pd.DataFrame] = None


def load_inventory() -> pd.DataFrame:
    df = pd.read_excel(INVENTORY_PATH)
    df = df.dropna(subset=["SKU"]).copy()

    for col in ["Categoría", "Subcategoría", "Ubicación", "Marca", "Descripción", "Proveedor Principal"]:
        df[col] = df[col].astype(str).str.strip()

    df["Fecha de Vencimiento"] = pd.to_datetime(df["Fecha de Vencimiento"], errors="coerce")
    df["Fecha de Fabricación"] = pd.to_datetime(df["Fecha de Fabricación"], errors="coerce")

    for col in ["Stock Actual", "Stock Mínimo", "Stock Máximo"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df


def get_inventory() -> pd.DataFrame:
    """Devuelve el DataFrame en memoria, recargándolo si el archivo cambió."""
    global _INVENTORY_DF
    with _inventory_lock:
        if _INVENTORY_DF is None:
            _INVENTORY_DF = load_inventory()
        return _INVENTORY_DF


def reload_inventory() -> int:
    global _INVENTORY_DF
    with _inventory_lock:
        _INVENTORY_DF = load_inventory()
        return len(_INVENTORY_DF)


# ---------------------------------------------------------
# DETECCIÓN DE INTENCIÓN (inventario vs documentos)
# ---------------------------------------------------------

INVENTORY_KEYWORDS = [
    "stock", "inventario", "abarrote", "abarrotes", "quedan", "queda",
    "cuantos", "cuántos", "cuanto", "cuánto", "existencia", "existencias",
    "disponible", "disponibles", "ubicacion", "ubicación", "donde esta",
    "donde están", "dónde está", "dónde están", "vencer", "vence",
    "vencimiento", "caduc", "reponer", "reposicion", "reposición",
    "grafica", "gráfica", "grafico", "gráfico", "compara", "comparar",
    "sku", "precio", "costo", "proveedor", "lote", "pasillo",
    "refrigerador", "congelador", "vitrina", "exhibidor", "producto",
    "productos", "marca", "categoria", "categoría"
]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def detect_intent(query: str) -> str:
    df = get_inventory()
    q = _norm(query)

    if any(k in q for k in INVENTORY_KEYWORDS):
        return "inventario"

    for val in list(df["Categoría"].unique()) + list(df["Subcategoría"].unique()) + list(df["Ubicación"].unique()):
        if val and _norm(val) in q:
            return "inventario"

    return "documentos"


# ---------------------------------------------------------
# EXTRACCIÓN DE FILTROS DESDE LA PREGUNTA
# ---------------------------------------------------------

def extract_filters(query: str, df: pd.DataFrame) -> dict:
    q = _norm(query)
    filters = {
        "categoria": None,
        "subcategoria": None,
        "ubicacion": None,
        "producto": None,
        "bajo_stock": False,
        "vencimiento_dias": None,
        "grafica": False,
    }

    for cat in df["Categoría"].unique():
        if cat and _norm(cat) in q:
            filters["categoria"] = cat
            break

    for sub in df["Subcategoría"].unique():
        if sub and _norm(sub) in q:
            filters["subcategoria"] = sub
            break

    for ubi in df["Ubicación"].unique():
        if ubi and _norm(ubi) in q:
            filters["ubicacion"] = ubi
            break

    m = re.search(r"pasillo\s*(\d+)", q)
    if m and not filters["ubicacion"]:
        candidate = f"Pasillo {m.group(1)}"
        if candidate in df["Ubicación"].values:
            filters["ubicacion"] = candidate

    for desc in df["Descripción"].unique():
        if desc and len(desc) > 4 and _norm(desc) in q:
            filters["producto"] = desc
            break

    if not filters["producto"]:
        for marca in df["Marca"].unique():
            if marca and len(marca) > 3 and re.search(rf"\b{re.escape(_norm(marca))}\b", q):
                filters["producto"] = None
                filters["marca"] = marca
                break

    if any(k in q for k in ["bajo stock", "poco stock", "stock bajo", "por reponer", "hay que reponer", "stock minimo", "stock mínimo", "agotand"]):
        filters["bajo_stock"] = True

    m = re.search(r"(?:pr[oó]ximos?\s+)?(\d+)\s*d[ií]as", q)
    if any(k in q for k in ["vencer", "vence", "vencimiento", "caduc"]):
        filters["vencimiento_dias"] = int(m.group(1)) if m else 30

    if any(k in q for k in ["grafica", "gráfica", "grafico", "gráfico", "visualiza", "compara", "comparar", "muestra un gráfico", "chart"]):
        filters["grafica"] = True

    return filters


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df.copy()

    if filters.get("categoria"):
        out = out[out["Categoría"] == filters["categoria"]]
    if filters.get("subcategoria"):
        out = out[out["Subcategoría"] == filters["subcategoria"]]
    if filters.get("ubicacion"):
        out = out[out["Ubicación"] == filters["ubicacion"]]
    if filters.get("producto"):
        out = out[out["Descripción"] == filters["producto"]]
    if filters.get("marca"):
        out = out[out["Marca"] == filters["marca"]]
    if filters.get("bajo_stock"):
        out = out[out["Stock Actual"] <= out["Stock Mínimo"]]
    if filters.get("vencimiento_dias") is not None:
        hoy = pd.Timestamp.now()
        dias = (out["Fecha de Vencimiento"] - hoy).dt.days
        out = out[dias.between(0, filters["vencimiento_dias"])]

    return out


# ---------------------------------------------------------
# RESUMEN TEXTUAL PARA EL LLM (el LLM solo redacta, no calcula)
# ---------------------------------------------------------

def build_summary(df_filtered: pd.DataFrame, filters: dict) -> str:
    if df_filtered.empty:
        return "No se encontraron productos que coincidan con los filtros aplicados."

    total_items = len(df_filtered)
    total_stock = int(df_filtered["Stock Actual"].sum())

    lines = [
        f"Total de productos encontrados: {total_items}",
        f"Suma de stock actual: {total_stock} unidades",
        "",
        "Detalle (máx. 20 productos):",
    ]

    detalle = df_filtered.sort_values("Stock Actual").head(20)
    for _, r in detalle.iterrows():
        lines.append(
            f"- {r['Descripción']} ({r['Marca']}) | SKU {r['SKU']} | "
            f"Categoría: {r['Categoría']} / {r['Subcategoría']} | "
            f"Ubicación: {r['Ubicación']} | "
            f"Stock: {r['Stock Actual']} (mín {r['Stock Mínimo']}, máx {r['Stock Máximo']})"
        )

    return "\n".join(lines)


# ---------------------------------------------------------
# GRÁFICAS (matplotlib -> PNG base64)
# ---------------------------------------------------------

def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("utf-8")


def _style_axes(ax):
    ax.set_facecolor("#161b22")
    ax.figure.set_facecolor("#0d1117")
    ax.tick_params(colors="#e6edf3", labelsize=9)
    ax.xaxis.label.set_color("#e6edf3")
    ax.yaxis.label.set_color("#e6edf3")
    ax.title.set_color("#e6edf3")
    for spine in ax.spines.values():
        spine.set_color("#30363d")
    ax.grid(axis="x", color="#30363d", linewidth=0.5, alpha=0.6)


def make_chart(df_filtered: pd.DataFrame, filters: dict) -> Optional[str]:
    if df_filtered.empty:
        return None

    if filters.get("bajo_stock"):
        data = df_filtered.sort_values("Stock Actual").head(15)
        fig, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * len(data))))
        ax.barh(data["Descripción"], data["Stock Actual"], color="#f85149", label="Stock actual")
        ax.barh(data["Descripción"], data["Stock Mínimo"], color="#3fb950", alpha=0.35, label="Stock mínimo")
        ax.set_title("Productos con stock bajo mínimo")
        ax.legend(facecolor="#161b22", labelcolor="#e6edf3", fontsize=8)
        _style_axes(ax)
        return _fig_to_base64(fig)

    if filters.get("subcategoria") or (filters.get("categoria") and len(df_filtered) <= 25):
        data = df_filtered.groupby("Descripción")["Stock Actual"].sum().sort_values(ascending=False).head(15)
        fig, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * len(data))))
        ax.barh(data.index[::-1], data.values[::-1], color="#2f81f7")
        ax.set_title(f"Stock por producto — {filters.get('categoria') or ''} {filters.get('subcategoria') or ''}".strip())
        _style_axes(ax)
        return _fig_to_base64(fig)

    if filters.get("ubicacion"):
        data = df_filtered.groupby("Descripción")["Stock Actual"].sum().sort_values(ascending=False).head(15)
        fig, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * len(data))))
        ax.barh(data.index[::-1], data.values[::-1], color="#2f81f7")
        ax.set_title(f"Stock en {filters['ubicacion']}")
        _style_axes(ax)
        return _fig_to_base64(fig)

    # Default: stock total por categoría (sobre el universo filtrado)
    data = df_filtered.groupby("Categoría")["Stock Actual"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(data.index, data.values, color="#2f81f7")
    ax.set_title("Stock total por categoría")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    _style_axes(ax)
    return _fig_to_base64(fig)


# ---------------------------------------------------------
# SUGERENCIAS DE CONSULTAS
# ---------------------------------------------------------

def build_suggestions(filters: dict, df_filtered: pd.DataFrame) -> List[str]:
    sug = []

    if filters.get("categoria"):
        cat = filters["categoria"]
        sug.append(f"¿Qué productos de {cat} tienen stock bajo?")
        sug.append(f"Gráfica de stock por producto en {cat}")
    elif filters.get("ubicacion"):
        ubi = filters["ubicacion"]
        sug.append(f"¿Qué productos hay en {ubi} con stock bajo?")
    elif filters.get("bajo_stock"):
        sug.append("¿Qué proveedores surten los productos con stock bajo?")
        sug.append("¿Cuáles de estos vencen en los próximos 30 días?")
    else:
        sug.append("¿Qué productos tienen stock por debajo del mínimo?")
        sug.append("Gráfica de stock total por categoría")
        sug.append("¿Qué productos vencen en los próximos 30 días?")

    return sug[:3]


# ---------------------------------------------------------
# NODOS DEL GRAFO
# ---------------------------------------------------------

def intent_node(state: AgentState):
    return {"intent": detect_intent(state["query"])}


def route_intent(state: AgentState):
    return state["intent"]


def retrieval_node(state: AgentState):
    query = state["query"].strip()
    query_lower = query.lower()

    if any(x in query_lower for x in ["donde", "ubicación", "direccion", "sucursal"]):
        context = search_similar(query, top_k=6)
    else:
        context = search_similar(query, top_k=5)

    return {"context": context}


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
            options={"num_predict": 400, "num_ctx": 4096, "temperature": 0.1, "num_thread": 4},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

    return {"answer": response["message"]["content"], "chart": None, "suggestions": []}


def inventory_data_node(state: AgentState):
    df = get_inventory()
    filters = extract_filters(state["query"], df)
    filtered = apply_filters(df, filters)

    summary = build_summary(filtered, filters)
    chart = make_chart(filtered, filters) if (filters.get("grafica") or filters.get("bajo_stock")) else None
    suggestions = build_suggestions(filters, filtered)

    return {"context": [summary], "chart": chart, "suggestions": suggestions}


def inventory_narrate_node(state: AgentState):
    context_text = "\n".join(state["context"])

    system_prompt = """
Eres el asistente de inventario de Mercado Central 24H.

REGLAS OBLIGATORIAS:
- Los números y datos ya fueron calculados. NO recalcules ni inventes cifras.
- Usa EXACTAMENTE los datos entregados en el resumen.
- Responde de forma breve, clara y en español.
- Si el resumen indica que no hay resultados, dilo claramente.
- Si hay una lista de productos, preséntala en formato de lista.
"""

    prompt = f"""
RESUMEN DE INVENTARIO:
{context_text}

PREGUNTA DEL USUARIO:
{state['query']}
"""

    with _llm_semaphore:
        response = ollama.chat(
            model="qwen2.5:3b",
            options={"num_predict": 350, "num_ctx": 4096, "temperature": 0.1, "num_thread": 4},
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

workflow.add_node("classify_intent", intent_node)
workflow.add_node("retrieval", retrieval_node)
workflow.add_node("generator", chat_node)
workflow.add_node("inventory_data", inventory_data_node)
workflow.add_node("inventory_narrate", inventory_narrate_node)

workflow.set_entry_point("classify_intent")

workflow.add_conditional_edges(
    "classify_intent",
    route_intent,
    {"inventario": "inventory_data", "documentos": "retrieval"}
)

workflow.add_edge("retrieval", "generator")
workflow.add_edge("generator", END)

workflow.add_edge("inventory_data", "inventory_narrate")
workflow.add_edge("inventory_narrate", END)

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

    result = app_graph.invoke({
        "query": query,
        "intent": "",
        "context": [],
        "answer": "",
        "chart": None,
        "suggestions": [],
    })

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT doc_name FROM documents ORDER BY doc_name;")
            docs = [r[0] for r in cur.fetchall()]
    finally:
        db_pool.putconn(conn)

    return jsonify({
        "documents": docs,
        "answer": result["answer"],
        "intent": result["intent"],
        "chart": result.get("chart"),
        "suggestions": result.get("suggestions", []),
    })


@app.route("/api/inventory/reload", methods=["POST"])
def inventory_reload():
    try:
        n = reload_inventory()
        return jsonify({"status": "ok", "rows": n})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------
# RUN — usar solo para desarrollo local
# Para producción: gunicorn app:app --workers 1 --threads 4 --timeout 120 --bind 127.0.0.1:6000 --worker-class gthread
# ---------------------------------------------------------

if __name__ == "__main__":
    get_inventory()  # precarga al arrancar
    print("Chat RAG + Inventario iniciado en puerto 6000")
    app.run(
        host="127.0.0.1",
        port=6000,
        debug=False,
        threaded=False   # False porque el semáforo maneja concurrencia
    )
