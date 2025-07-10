from core.state import State
from typing import Dict

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage, SystemMessage
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.workflows import Workflow

import json

def validate_plan(state: State, plan: Dict[str, list]): 
    steps = plan['steps']
    wrong_tools = []
    for step in steps: 
        if step['tool'] not in state.tool_names: 
            wrong_tools.append(f"The following tool does not exist: {step['tool']}")
    return wrong_tools

def generate_prompt_input(state: State, user_feedback: str = "") -> ChatModelInput: 
        messages = []

        if user_feedback: 
            messages = [
                state.plan_msg, 
                UserMessage(content=(
                    f"Task: {state.task}\n"
                )),
                SystemMessage(content=(
                    f"In the past you tried using the following tools that do not exist: \n {user_feedback}"
                    "\n Make sure you don't make the same mistake"
                ))
            ]
        else: 
            messages = [
                    state.plan_msg, 
                    UserMessage(content=(
                        f"User Query: {state.task}\n"
                    )), 
                ]

        chat_input = ChatModelInput(
                messages = messages, 
                temperature = 0,
                response_format = {"type": "json_object"}
            )

        return chat_input


def make_plan_step(llm: ChatModel): 

    async def plan(state: State) -> str: 

        user_feedback = ""

        for attempt in range(2):  #1 retry
            chat_input = generate_prompt_input(state, user_feedback)
            response = await llm.create(messages = chat_input.messages, response_format = chat_input.response_format)
            message = response.messages[0]

            plan_dict = json.loads(message.content[0].text)
            user_feedback = validate_plan(state, plan_dict)

            if user_feedback: 
                user_feedback = "\n".join(user_feedback)
                continue

            state.plan = plan_dict
        
        if not state.plan: 
            raise ValueError(f"Inadequate tools for the following query: {state.task}")

        return Workflow.NEXT

    return plan 