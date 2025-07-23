import json, re, asyncio
import textwrap
from typing import Any, Dict, Iterator, Optional, Callable
from core.state import State
from fastmcp import Client
from client import MCPClient
from fastmcp.client.transports import StreamableHttpTransport

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.types import ChatModelInput
from beeai_framework.backend.message import UserMessage, SystemMessage, ToolMessage, AssistantMessage
from beeai_framework.workflows import Workflow

import httpx, logging, sys


from collections import deque

'''
logging.basicConfig(
    stream = sys.stderr, 
    level = logging.DEBUG, 
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

for logger_name in ("httpx", "httpcore"): 
    logging.getLogger(logger_name).setLevel(logging.DEBUG)
'''

class RingBuffer: 
    '''Holds last N items from prompt context.'''
    def __init__(self, size: int = 3): 
        self._q = deque(maxlen=size)
    
    def push(self, ordinal: int, summary: str) -> None: 
        self._q.append((ordinal, summary))
    
    def render(self) -> str: 
        return "\n".join(f"[{i}] {txt}" for i, txt in self._q) or "[none]"

class Scratchpad: 

    def __init__(self) -> None: 
        self._data: Dict[int, Any] = {}

    def write(self, idx: int, value: Any) -> None: 
        self._data[idx] = value

    def read(self, idx: int, attr: Optional[str] = None) -> Any: 
        val = self._data.get(idx)
        if attr and isinstance(val, dict): 
            return val.get(attr)
        return val

    def __getitem__(self, idx: int) -> Any: 
        return self.read(idx)
    
    def __contains__(self, idx: int) -> bool: 
        return idx in self._data
    
    def keys(self) -> Iterator[int]: 
        return self._data.keys()
    
    def items(self) -> Iterator[tuple[int, Any]]: 
        return self._data.items()
    
    def summary(self, max_chars: int = 120) -> str: 
        lines = []
        for i, val in sorted(self._data.items()): 
            text = val if isinstance(val, str) else json.dumps(val) 
            short = textwrap.shorten(text, max_chars, placeholder="...")
            lines.append(f"[{i}] {short}")
        return "\n".join(lines) or "[empty]"

class PromptBuilder: 
    SYSTEM = (
        "You are the EXECUTOR. \n\n"
        "Input (from user role) - JSON containing:\n"
        '   "tool": "<exact_tool_name>"\n'
        '   "args": {...} <-- may include placeholders like $step3.body \n\n'
        "You may reason silently, then OUTPUT ONLY:\n\n"
        '   {"args": {...finalized...}}\n\n'
        '   where the "args" object is ready to be sent to that tool. \n\n'
        'RULES: \n'
        '1. Do NOT change or output the tool name'
        '2. Use placeholders ($stepN or $stepN.key) to fetch prior results'
        '3. If you need to compute a value, put it directly into the args'
        '4. No extra keys, no narration, no comments'
    )
     
    def __init__(self, tool_docs: str, last_n: int = 3): 
        self.tool_docs = tool_docs.strip()
        self.last_n = last_n
    
    def build(
        self, 
        step: Dict[Any, Any], 
        ordinal: int,
        scratch_sum: str, 
        recent_buffer: str,
        feedback: str | None = None
    ) -> list[dict]: 

        sys_blocks = [self.SYSTEM, f"TOOLS: \n {self.tool_docs}"]
        if feedback: 
            sys_blocks.append(f"FEEDBACK: \n {feedback}")
        
        return [
            SystemMessage(content = 
                "\n\n".join(sys_blocks)), 
            UserMessage( content = 
                (
                    f"RECENT RESULTS (most recent last): \n{recent_buffer} \n\n"
                    f"SCRATCHPAD SUMMARY:\n{scratch_sum}\n\n"
                    f"NEXT STEP {ordinal}:\n{json.dumps(step)}"
                )
            )
        ]
    
    def build_synthesizer(
        self, 
        user_query: str, 
        scratch_sum: str, 
        recent_buffer: str
    ): 

        print(
            f'''
                Query: {user_query}\n
                Memory Buffer : \n{recent_buffer}
                '''
        )
        return [SystemMessage( content = 
            (
                f'''
                You are an expert assistnat.\n 
                Using the memory buffer, answer the user query in plain text.
                DO NOT GIVE ANY REASONING OF HOW TO CREATE THE ANSWER, JUST ANSWER THE QUERY.
                '''
            )), 
            UserMessage(content = (
                f'''
                Query: {user_query}\n
                Memory Buffer : \n{recent_buffer}
                '''
            ))
        ]


_P = re.compile(r"\$step(\d+)(?:\.(\w+))?")

def _sub(value: Any, ctx: Dict[int, Any]) -> Any: 
    if isinstance(value, str): 
        m = _P.fullmatch(value.strip())
        if m: 
            idx, attr = m.groups()
            data = ctx.get(int(idx))
            return data.get(attr) if (attr and isinstance(data, dict)) else data
    return value 

def resolve_local(v: str, scratch: Scratchpad): 
    m = _P.fullmatch(v)
    return scratch.read(int(m.group(1)), m.group(2)) if m else v

def resolve_placeholders(obj: Dict[str, Any], scratch: Scratchpad): 
    return {k: resolve_local(v, scratch) if isinstance (v, str) else v for k, v in obj.items()}

def _shorten(res: Any, max_len = 120): 
    txt = res if isinstance(res, str) else json.dumps(res)
    return txt if len(txt) <= max_len else txt[:max_len] + "..."


def make_execute_step(llm: ChatModel, call_tool: Callable[[str, Dict[str, Any]], Any], n_back: int = 3, max_retries: int = 1): 
    async def execute(state: State): 
    
        prompt_builder = PromptBuilder(state.tool_list_as_str())
        
        try: 
            plan = state.plan
            steps = plan["steps"]
            scratch = Scratchpad()
            recent = RingBuffer(n_back)

        except Exception as e: 
            raise ValueError(f"Bad plan format: {e}")
        

        for ordinal, step in enumerate(steps, start = 1): 
            tool = step["tool"]
            args = step.get("args", {})
            feedback = None
            for attempt in range(max_retries + 1): 
                prompt_messages = prompt_builder.build(
                    ordinal = ordinal, 
                    step = step, 
                    scratch_sum = scratch.summary(), 
                    recent_buffer = recent.render(), 
                    feedback = feedback
                )
                print(prompt_messages)
                reply = await llm.create(messages = prompt_messages, response_format = {"type": "json_object"})
                reply = reply.messages[0].content[0].text
                try: 
                    refined = json.loads(reply)["args"]
                    break 
                except Exception as e: 
                    feeback = f"Output invalid: {e}"
                    if attempt == max_retries: 
                        log.error("LLM failed on step %d, using raw args", ordinal)
                        refined = args
            
            final_args = resolve_placeholders(refined, scratch) 

            '''
            try: 
                result = await run_tool(client, tool, **args)
                print("result:", result)
            except asyncio.TimeoutError: 
                print("likely missing DONE")
            except Exception as e: 
                print("fast MCP error")

            '''
            try: 
                result = await call_tool(tool, final_args)
                print(result)
                result = result.content[0].text
            except Exception as e: 
                result = {"error": str(e)}
                #log.exception("Tool %s failed: %s", tool, e)
        
            scratch.write(ordinal, result)
            recent.push(ordinal, result)
    
        synthesize_prompt = prompt_builder.build_synthesizer(user_query = state.task, scratch_sum = scratch.summary(), recent_buffer = recent.render())
        final_answer = await llm.create(messages = synthesize_prompt, temperature = 0.2, max_new_tokens = 256)
        final_answer = final_answer.messages[0].content
        print(f"HERE IS THE ANSWER TO YOUR QUERY: \n\n {final_answer[0].text}")


        return Workflow.END  

    return execute
