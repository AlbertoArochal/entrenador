import os
import json
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "fitness_exercises"
EMBED_MODEL = "all-MiniLM-L6-v2"


def get_embedding_function():
    return SentenceTransformer(EMBED_MODEL)


def _build_from_dataset(ds, embedder, collection):
    texts = []
    metadata_list = []
    ids = []
    for i, row in enumerate(ds):
        question = row.get("Question") or row.get("question", "")
        answer = row.get("Answer") or row.get("answer", "")
        if not question or not answer:
            continue
        text = f"Pregunta: {question}\nRespuesta: {answer}"
        texts.append(text)
        metadata_list.append({"question": question, "source": "huggingface"})
        ids.append(f"ex_{i}")

    batch_size = 64
    for start in range(0, len(texts), batch_size):
        end = min(start + batch_size, len(texts))
        batch_texts = texts[start:end]
        batch_embeddings = embedder.encode(batch_texts, show_progress_bar=False).tolist()
        collection.add(
            embeddings=batch_embeddings,
            documents=batch_texts,
            metadatas=metadata_list[start:end],
            ids=ids[start:end],
        )
    return len(texts)


def build_knowledge_base():
    print("Cargando dataset de ejercicios...")
    from datasets import load_dataset

    ds = load_dataset("its-myrto/fitness-question-answers", split="train")
    print(f"  Dataset: {len(ds)} registros")

    print("Inicializando ChromaDB...")
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
    try:
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()
        print(f"  Coleccion existente: {count} documentos")
        return count
    except Exception:
        collection = client.create_collection(COLLECTION_NAME)

    print("Generando embeddings...")
    embedder = get_embedding_function()
    total = _build_from_dataset(ds, embedder, collection)
    print(f"  {total} documentos indexados en ChromaDB")
    return total


def query_fitness_knowledge(query, k=3):
    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        build_knowledge_base()
        collection = client.get_collection(COLLECTION_NAME)

    embedder = get_embedding_function()
    query_emb = embedder.encode([query], show_progress_bar=False).tolist()
    results = collection.query(query_embeddings=query_emb, n_results=k)

    contextos = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        contextos.append(doc)

    return "\n\n---\n\n".join(contextos)


def rebuild():
    import shutil
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
    return build_knowledge_base()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--rebuild":
        total = rebuild()
    else:
        total = build_knowledge_base()
    print(f"Listo. {total} documentos en la base de conocimiento.")
