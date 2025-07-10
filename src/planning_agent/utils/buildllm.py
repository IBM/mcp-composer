from beeai_framework.backend.chat import ChatModel, ChatModelInput
import os, dotenv; dotenv.load_dotenv()

def build_llm() -> ChatModel: 

    
    '''
    llm = ChatModel.from_name(
        "openai:gpt-4o-mini"
    )
    '''
    
    llm = ChatModel.from_name(
        "watsonx:meta-llama/llama-4-maverick-17b-128e-instruct-fp8", 
        provider_args = {
            "api_key": os.getenv("WX_API_KEY"), 
            "project_id": os.getenv("WATSONX_PROJECT_ID"), 
            "base_url": os.getenv("WATSONX_URL")
            },
        params = {"temperature": 0.01, "structured_output": True, "max_tokens": 1000}
    )
    
    

    return llm 

#watsonx:meta-llama/llama-3-3-70b-instruct
#watsonx:meta-llama/llama-4-maverick-17b-128e-instruct-fp8
#watsonx:ibm/granite-13b-instruct-v2
#watsonx:ibm/granite-3-3-8b-instruct