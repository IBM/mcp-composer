import os
import re
from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.types import ChatModelParameters
from beeai_framework.backend import UserMessage
from dotenv import load_dotenv, find_dotenv


# Load environment variables
load_dotenv(find_dotenv(".env"))
model_name = os.getenv("CHAT_MODEL_NAME", "watsonx").strip()

llm_default: ChatModel = ChatModel.from_name(
    model_name,
    ChatModelParameters(temperature=0.01, max_tokens=1000),
)


def parse_llm_name(llm_name: str) -> tuple[str, str]:
    """LLM name mapping to provider and chat model name"""
    if not llm_name:
        return "", ""

    pattern = r"(\w+)\(([^)]+)\)"
    matches = re.findall(pattern, llm_name)
    if len(matches) >= 1:
        provider, chat_model = matches[0]
        provider = provider.lower()
        match provider:
            case "openai":
                chat_model = "gpt-" + chat_model
                os.environ["OPENAI_CHAT_MODEL"] = chat_model
            case "watsonx":
                if "llama-4" in chat_model:
                    chat_model = "meta-llama/llama-4-maverick-17b-128e-instruct-fp8"
                elif "llama-3" in chat_model:
                    chat_model = "meta-llama/llama-3-3-70b-instruct"
                elif "granite-3" in chat_model:
                    chat_model = "ibm/granite-3-3-8b-instruct"
                elif "mistral-large" in chat_model:
                    chat_model = "mistralai/mistral-large"
                elif "mistral-medium-2505" in chat_model:
                    chat_model = "mistralai/mistral-medium-2505"

                if chat_model != "":
                    os.environ["WATSONX_CHAT_MODEL"] = chat_model
            case "ollama":
                os.environ["OLLAMA_CHAT_MODE"] = chat_model

        print("select model:", provider, chat_model)
        return provider, chat_model
    else:
        return llm_name, ""


def get_llm(llm_name: str | None = None) -> ChatModel:
    if llm_name:
        provider, chat_model = parse_llm_name(llm_name)
        if chat_model != "":
            return ChatModel.from_name(
                provider, ChatModelParameters(temperature=0.01, max_tokens=1000)
            )

    return llm_default


async def run_llm(user_input: str, llm_name: str | None = None) -> str:
    llm = get_llm(llm_name)
    response = await llm.create(messages=[UserMessage(content=user_input)])
    return response.get_text_content()
