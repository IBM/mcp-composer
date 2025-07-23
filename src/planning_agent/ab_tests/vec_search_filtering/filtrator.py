from core.state import State
from ab_tests.vec_search_filtering.tool_to_doc import tool_to_doc
from typing import Dict

import chromadb, os 
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chromadb.config import Settings

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage, SystemMessage
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.workflows import Workflow

from utils.planmsg import build_plan_msg

import json

def make_filter_step(llm: ChatModel): 

    def create_chroma(state: State): 
        client = chromadb.PersistentClient(
            path = "./src/planning_agent/chroma"
        )


        col = client.get_or_create_collection(
            name = "tool_vectors", 
            embedding_function= OpenAIEmbeddingFunction(model_name="text-embedding-3-small"),
        )

        docs = [tool_to_doc(t) for t in state.tools]
        ids = [t["name"] for t in state.tools]

        col.upsert(documents= docs, ids = ids)

        return client, col
    
    def suggest_tools(user_query: str, col: object, state: State, n_results: int = 10): 
        res = col.query(query_texts= [user_query], n_results= n_results)
        hits = list(zip(res["ids"][0], res["distances"][0], res["metadatas"][0]))
        return sorted(hits, key = lambda x: x[1])



    async def filter(state: State) -> str: 


        client, col = create_chroma(state)

        filtered_tools = suggest_tools(state.task, col, state)
        print(filtered_tools)

        
        '''
        filtered_tools = set(obj["tools"])
        state.filter_tools(filtered_tools)
        build_plan_msg(state)
        '''

        return Workflow.END
        #return Workflow.NEXT
        

    return filter 