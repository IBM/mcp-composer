from planning_agent.core.state import State
import chromadb, os 
import ollama
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from chromadb.utils.embedding_functions.ollama_embedding_function import OllamaEmbeddingFunction
from sentence_transformers import SentenceTransformer 

from chromadb.config import Settings
from planning_agent.utils.tools_to_chroma_doc import tool_to_doc
from planning_agent.ab_tests.constants import EmbeddingModels

from enum import Enum

def create_chroma(state: State, embedding_model: int, approach: int = 2): 
        
        client = chromadb.PersistentClient(
            path = "./src/planning_agent/chroma"
        )
        if embedding_model == 1: 
            col = client.get_or_create_collection(
                name = f"tool_vectors_miniL6{approach}"
            )
        elif embedding_model == 2: 
            col = client.get_or_create_collection(
                name = f"tool_vectors_mpnet{approach}", 
                embedding_function= SentenceTransformerEmbeddingFunction(
                    model_name="all-mpnet-base-v2" 
                )
            ) 
        else: 
            col = client.get_or_create_collection(
                name = f"tool_vectors_qwen{approach}", 
                embedding_function= SentenceTransformerEmbeddingFunction(
                    model_name="Qwen/Qwen3-Embedding-0.6B" 
                )
            )
        docs = [tool_to_doc(t, approach) for t in state.tools]
        ids = [t["name"] for t in state.tools]

        col.upsert(documents= docs, ids = ids)

        return client, col
    
def suggest_tools(user_query: str, col: object, n_results: int = 10): 
    res = col.query(query_texts= [user_query], n_results= n_results)
    hits = list(zip(res["ids"][0], res["distances"][0], res["metadatas"][0]))
    return sorted(hits, key = lambda x: x[1])



'''
if embedding_model == 1: 
            col = client.get_or_create_collection(
                name = "tool_vectors_qwen", 
                embedding_function= SentenceTransformerEmbeddingFunction(
                    model_name="Qwen/Qwen3-Embedding-0.6B" 
                )
            )
        elif embedding_model == 2: 
            col = client.get_or_create_collection(
                name = "tool_vectors_bge", 
                embedding_function= SentenceTransformerEmbeddingFunction(
                    model_name="BAAI/bge-m3" 
                )
            ) 
        else: 
             col = client.get_or_create_collection(
                name = "tool_vectors_intfloat", 
                embedding_function= SentenceTransformerEmbeddingFunction(
                    model_name="intfloat/multilingual-e5-large-instruct" 
                )
            )
'''