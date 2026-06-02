"""
Configurazioni comuni per l'indicizzazione e l'estrazione di testo.

"""
from langchain_huggingface import HuggingFaceEmbeddings
from neo4j import GraphDatabase

NEO4J_URI  = "bolt://localhost:7687"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

NEO4J_VECTOR_KWARGS = dict(
    url=NEO4J_URI,
    username="neo4j",
    password="password",
    index_name="documenti_turistici",
    node_label="Documento",
    text_node_property="testo",
    embedding_node_property="embedding",
)

driver = GraphDatabase.driver(NEO4J_URI, auth=None)


def carica_embeddings() -> HuggingFaceEmbeddings:
    print(f"Inizializzazione modello ({MODEL_NAME})...")
    return HuggingFaceEmbeddings(model_name=MODEL_NAME, encode_kwargs={"normalize_embeddings": True})