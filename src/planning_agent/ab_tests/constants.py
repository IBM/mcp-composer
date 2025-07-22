from enum import Enum
class FilterApproaches(int, Enum): 
    DESCRIPTIONS = 1
    FULL_DESCRIPTIONS = 2
    VECTOR_STORE_FULL_TOOL = 3
    VECTOR_STORE_FULL_DESC = 4
    VECTOR_STORE_PARSED_DESC = 5
    VECTOR_STORE_CLIPPED_DESC = 6
    VECTOR_STORE_AND_LLM = 7
    COARSE_AND_FINE_LLM = 8 
    FULL_INFO = 9
    PROMPTED_VECTOR_STORE = 10
    THREE_STEP = 11

class LLMModel(int, Enum):
    PLACEHOLDER = 1
    LLAMA = 2
    MISTRAL = 3

class EmbeddingModels(int, Enum): 
    MINIL6 = 1
    MPNET = 2
    QWEN = 3


class Constants: 
    OptionFilterMap = {
        1: FilterApproaches.DESCRIPTIONS, 
        2: FilterApproaches.DESCRIPTIONS, 
        3: FilterApproaches.DESCRIPTIONS, 
        4: FilterApproaches.FULL_DESCRIPTIONS, 
        5: FilterApproaches.FULL_DESCRIPTIONS, 
        6: FilterApproaches.FULL_DESCRIPTIONS, 
        7: FilterApproaches.VECTOR_STORE_FULL_TOOL, 
        8: FilterApproaches.VECTOR_STORE_FULL_TOOL, 
        9: FilterApproaches.VECTOR_STORE_FULL_TOOL, 
        10: FilterApproaches.VECTOR_STORE_FULL_DESC, 
        11: FilterApproaches.VECTOR_STORE_FULL_DESC, 
        12: FilterApproaches.VECTOR_STORE_FULL_DESC, 
        13: FilterApproaches.VECTOR_STORE_PARSED_DESC, 
        14: FilterApproaches.VECTOR_STORE_PARSED_DESC, 
        15: FilterApproaches.VECTOR_STORE_PARSED_DESC, 
        16: FilterApproaches.VECTOR_STORE_CLIPPED_DESC, 
        17: FilterApproaches.VECTOR_STORE_CLIPPED_DESC, 
        18: FilterApproaches.VECTOR_STORE_CLIPPED_DESC,
        19: FilterApproaches.VECTOR_STORE_AND_LLM,
        20: FilterApproaches.VECTOR_STORE_AND_LLM,
        21: FilterApproaches.VECTOR_STORE_AND_LLM, 
        22: FilterApproaches.VECTOR_STORE_AND_LLM, 
        23: FilterApproaches.VECTOR_STORE_AND_LLM,
        24: FilterApproaches.VECTOR_STORE_AND_LLM,
        25: FilterApproaches.VECTOR_STORE_AND_LLM, 
        26: FilterApproaches.VECTOR_STORE_AND_LLM, 
        27: FilterApproaches.VECTOR_STORE_AND_LLM, 
        28: FilterApproaches.COARSE_AND_FINE_LLM,
        29: FilterApproaches.COARSE_AND_FINE_LLM, 
        30: FilterApproaches.COARSE_AND_FINE_LLM, 
        31: FilterApproaches.FULL_INFO, 
        32: FilterApproaches.FULL_INFO, 
        33: FilterApproaches.FULL_INFO, 
        34: FilterApproaches.PROMPTED_VECTOR_STORE, 
        35: FilterApproaches.PROMPTED_VECTOR_STORE, 
        36: FilterApproaches.PROMPTED_VECTOR_STORE,
        37: FilterApproaches.THREE_STEP, 
        38: FilterApproaches.THREE_STEP,
        39: FilterApproaches.THREE_STEP,
    }

    LLM_OPTIONS = {
        #REGULAR PARSED DESCRIPTIONS
        1 : LLMModel.PLACEHOLDER, 
        2 : LLMModel.LLAMA, 
        3 : LLMModel.MISTRAL,
        #JUST TOOL NAMES AND FIRST SENTENCE OF DESCRIPTON
        4 : LLMModel.PLACEHOLDER,
        5 : LLMModel.LLAMA, 
        6 : LLMModel.MISTRAL, 
        #VECTOR STORE COARSE FILTERING + LLM FINE FILTERING  
        19 : LLMModel.PLACEHOLDER, 
        20: LLMModel.PLACEHOLDER, 
        21 : LLMModel.PLACEHOLDER, 
        22: LLMModel.LLAMA, 
        23: LLMModel.LLAMA, 
        24: LLMModel.LLAMA, 
        25: LLMModel.MISTRAL, 
        26: LLMModel.MISTRAL,
        27: LLMModel.MISTRAL, 
        #LLM COARSE FILTERING + LLM FINE FILTERING
        28: LLMModel.PLACEHOLDER, 
        29: LLMModel.LLAMA, 
        30: LLMModel.MISTRAL, 
        31: LLMModel.PLACEHOLDER, 
        32: LLMModel.LLAMA, 
        33: LLMModel.MISTRAL, 
        34: LLMModel.PLACEHOLDER, 
        35: LLMModel.LLAMA, 
        36: LLMModel.MISTRAL,
        37: LLMModel.PLACEHOLDER, 
        38: LLMModel.LLAMA, 
        39: LLMModel.MISTRAL,


    }

    EMBEDDING_OPTIONS = {
        7: EmbeddingModels.MINIL6, 
        8: EmbeddingModels.MPNET, 
        9: EmbeddingModels.QWEN, 
        10: EmbeddingModels.MINIL6, 
        11: EmbeddingModels.MPNET, 
        12: EmbeddingModels.QWEN, 
        13: EmbeddingModels.MINIL6, 
        14: EmbeddingModels.MPNET, 
        15: EmbeddingModels.QWEN , 
        16: EmbeddingModels.MINIL6, 
        17: EmbeddingModels.MPNET,
        18: EmbeddingModels.QWEN,
        19: EmbeddingModels.MINIL6, 
        20: EmbeddingModels.MPNET, 
        21: EmbeddingModels.QWEN, 
        22: EmbeddingModels.MINIL6, 
        23: EmbeddingModels.MPNET, 
        24: EmbeddingModels.QWEN , 
        25: EmbeddingModels.MINIL6, 
        26: EmbeddingModels.MPNET,
        27: EmbeddingModels.QWEN,  
        35: EmbeddingModels.MPNET,
        36: EmbeddingModels.MPNET,
        37: EmbeddingModels.QWEN , 
        38: EmbeddingModels.MINIL6, 
        39: EmbeddingModels.MPNET,
    }

class TestOptions(): 
    test_options = { 
        1: "<Placeholder model>",
        2: "llama 4 parsed descriptions", 
        3: "mistral medium parsed descriptions", 
        4: "<Placeholder model> full descriptions",
        5: "llama 4 full descriptions", 
        6: "mistral medium full descriptions", 
        7: "vectore store MiniL6 full tool info", 
        8: "vectore store mpnet full tool info",
        9: "vectore store Qwen3-0.6B full tool info",
        10: "vectore store MiniL6 full descriptions (no schema)", 
        11: "vectore store mpnet full descriptions (no schema)",
        12: "vectore store Qwen3-0.6B full descriptions (no schema)",
        13: "vectore store MiniL6 (parsed descriptions)", 
        14: "vectore store mpnet (parse descriptions)",
        15: "vectore store Qwen3-0.6B (parse descriptions)",
        16: "vectore store MiniL6 (clipped descriptions)", 
        17: "vectore store mpnet (clipped descriptions)",
        18: "vectore store Qwen3-0.6B (clipped descriptions)",
        19: "MiniL6 -> <Placeholder model>", 
        20: "mpnet -> <Placeholder model>", 
        21: "Qwen3-0.6B -> <Placeholder model>", 
        22: "MiniL6 -> llama4", 
        23: "mpnet -> llama4", 
        24: "Qwen3-0.6B -> llama4",
        25: "MiniL6 -> mistral medium", 
        26: "mpnet -> mistral medium", 
        27: "Qwen3-0.6B -> mistral medium", 
        28: "<Placeholder model> clipped descriptions (name + 100 chars) --> full descriptions on subset", 
        29: "llama 4 clipped descriptions (name + 100 chars) --> full descriptions info on subset", 
        30: "mistral medium clipped descriptions (name + 100 chars) --> full descriptions info on subset", 
        31: "<Placeholder model>",
        32: "llama 4 full tool info", 
        33: "mistral medium full tool info", 
        34: "<placeholder> prompt to vector store", 
        35: "llama4 prompt to vector store (mpnet)", 
        36: "mistral medium prompt to vector store (mpnet)",
        37: "<placeholder + qwen > three step prompt --> vec --> llm", 
        38: "llama4 + qwen three step prompt --> vec --> llm", 
        39: "mistral + qwen three step prompt --> vec --> llm", 
    }
    tests_in_commission = [35]


