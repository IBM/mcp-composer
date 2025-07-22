import os 
from dotenv import load_dotenv

from planning_agent.core.state import State
from beeai_framework.workflows import Workflow

load_dotenv()
TEST_RESULTS_PATH = os.getenv("TEST_RESULTS_PATH")

def make_write_step(option: int): 

    async def write(state: State) -> str: 

        filtered_tools_str = "Error in Completion"
        if state.filtered_tools: 
            filtered_tools_str = ", ".join(sorted(list(map(lambda tool: tool["name"], state.filtered_tools))))

        with open(TEST_RESULTS_PATH, "a") as f:
            f.write(f"{filtered_tools_str}\n")           
            return Workflow.END

    return write 
