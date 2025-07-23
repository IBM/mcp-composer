from beeai_framework.backend.chat import ChatModel, ChatModelInput
import os, dotenv; dotenv.load_dotenv()
from planning_agent.ab_tests.constants import LLMModel
from enum import Enum

def build_llm(llm_model: int = 2) -> ChatModel: 

    llm = None

    if llm_model == LLMModel.PLACEHOLDER:
        llm = ChatModel.from_name(
            "watsonx:ibm/granite-3-3-8b-instruct", 
            provider_args = {
                "api_key": os.getenv("WX_API_KEY"), 
                "project_id": os.getenv("WATSONX_PROJECT_ID"), 
                "base_url": os.getenv("WATSONX_URL")
                },
            params = {"temperature": 0.3, "structured_output": True, "max_tokens": 1000}
        )
    
    elif llm_model == LLMModel.LLAMA: 
        llm = ChatModel.from_name(
            "watsonx:meta-llama/llama-4-maverick-17b-128e-instruct-fp8", 
            provider_args = {
                "api_key": os.getenv("WX_API_KEY"), 
                "project_id": os.getenv("WATSONX_PROJECT_ID"), 
                "base_url": os.getenv("WATSONX_URL")
                },
            params = {"temperature": 0.3, "structured_output": True, "max_tokens": 1000}
        )
    
    elif llm_model == LLMModel.MISTRAL:
        llm = ChatModel.from_name(
            "watsonx:mistralai/mistral-medium-2505", 
            provider_args = {
                "api_key": os.getenv("WX_API_KEY"), 
                "project_id": os.getenv("WATSONX_PROJECT_ID"), 
                "base_url": os.getenv("WATSONX_URL")
                },
            params = {"temperature": 0.3, "structured_output": True, "max_tokens": 1000}
        )

    return llm 

#watsonx:meta-llama/llama-3-3-70b-instruct
#watsonx:meta-llama/llama-4-maverick-17b-128e-instruct-fp8
#watsonx:ibm/granite-13b-instruct-v2
#watsonx:ibm/granite-3-3-8b-instruct