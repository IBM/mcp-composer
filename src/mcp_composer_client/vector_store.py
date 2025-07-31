from sentence_transformers import SentenceTransformer 
import hnswlib, numpy as np, pickle, json, os
from dotenv import load_dotenv; load_dotenv()

# Model 
MODEL_NAME = "all-mpnet-base-v2"
encoder = SentenceTransformer(MODEL_NAME)
INDEX_PATH = os.getenv("VECTOR_STORE_DATABASE")

# Build/Rebuild the index 
def build_index(tool_docs: list[dict], index_path=INDEX_PATH):
    texts = [f"{d.name}: {d.description}" for d in tool_docs]
    vectors = encoder.encode(texts, convert_to_numpy=True).astype(np.float32)

    dim = vectors.shape[1]
    hnsw = hnswlib.Index(space='cosine', dim=dim)
    hnsw.init_index(max_elements=len(texts), ef_construction=200, M=16)
    hnsw.add_items(vectors, ids = np.arange(len(texts)))
    hnsw.set_ef(64)
    hnsw.save_index(index_path)

    #Persist the name metadata so we can map intID to name 
    meta = {i: tool.name for i, tool in enumerate(tool_docs)}
    with open(index_path + ".meta", "w") as f:
        json.dump(meta, f)
    

#Query
def query_tools(paragraph: str, k = 10, index_path=INDEX_PATH):
    dim = encoder.get_sentence_embedding_dimension()
    hnsw = hnswlib.Index(space='cosine', dim=dim)
    hnsw.load_index(index_path, max_elements = 10000)

    with open(index_path + ".meta") as f: 
        meta = json.load(f)
    
    q_vec = encoder.encode(paragraph, convert_to_numpy=True).astype(np.float32)
    labels, distances = hnsw.knn_query(q_vec, k=k)

    hits = []
    for idx, dist in zip(labels[0], distances[0]):
        tool_name = meta[str(idx)]
        score = 1 - dist / 2
        hits.append({"name": tool_name, "score": score})
    
    return hits

    