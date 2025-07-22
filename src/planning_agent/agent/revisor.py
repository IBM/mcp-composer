import json, asyncio
from typing import Callable


from beeai_framework.workflows import Workflow
from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.backend.message import UserMessage, SystemMessage

from planning_agent.core.state import State
def make_revision_step(llm: ChatModel, validate_step_id: str, cancel_step_id: str) -> Callable[[State], str]: 
    async def revise(state: State) -> str: 
        #-----USER HAS NOT PROVIDED FEEDBACK-----
        if state.user_feedback is None: 

            if state.validation_error: 
                print(" YOUR PLAN COULD NOT BE VALIDATED BECAUSE:\n" +
                    state.validation_error + "\n")
                state.validation_error = None


            print("\n CURRENT PLAN \n" + "-"*60)
            print(json.dumps(state.plan, indent = 2))
            print(
                "\nType one of: \n"
                " /run      - execute the plan exactly as shown \n"
                " /cancel   - abort the workflow\n"
                " <changes> - describe what to tweak\n"
            )
            loop = asyncio.get_event_loop()
            state.user_feedback = await loop.run_in_executor(None, input, ">>> ")
            #Jump back to revision 
            return "revision"
        
        fb = state.user_feedback.strip().lower()
        
        #-----USER HAS ASKED TO CANCEL OR RUN-----
        if fb.startswith("/cancel"): 
            return cancel_step_id
        if fb.startswith("/run"): 
            return validate_step_id
        
        #-----USER HAS GIVEN FEEDBACK-----
        sys_msg = SystemMessage(
            content=(
                "Rewrite the JSON plan to"
                "satisfy the user's feedback. Output ONLY the new plan as"
                "a JSON object with the SAME schema)\n\n"
            )
        )

        user_msg = UserMessage(
            f"Original plan: \n'''json\n{json.dumps(state.plan, indent =2)}\n'''\n"
            f"User feedback: \n{state.user_feedback}"
        )

        chat_in = ChatModelInput(
            messages = [state.plan_msg, sys_msg, user_msg],
            response_format = {"type": "json_object"},
            temperature = 0
        )

        response = await llm.create(messages=chat_in.messages, response_format=chat_in.response_format, temperature=chat_in.temperature)
        message = response.messages[0]
        plan_dict = json.loads(message.content[0].text)
        state.plan = plan_dict
        state.user_feedback = None
        return "revision"

    return revise 