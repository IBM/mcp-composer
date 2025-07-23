import jsonschema
from core.state import State
from beeai_framework.workflows import Workflow

def make_validate_step(): 
    async def validate(state: State) -> str: 
        steps = state.plan.get("steps", [])
        bad_steps: list[str] = []
    
        for idx, step in enumerate(steps): 
            name = step.get("tool")
            
            schema = state.tool_schemas.get(name)["properties"]
            if schema is None: 
                raise ValueError(f"Unknown tool '{name}' at step {idx}")
            
            args = step.get("args", {})
            print(f"ARGS: {args}")
            print(f"SCHEMA: {schema}")
            try: 
                jsonschema.validate(instance = args, schema = schema)
            except jsonschema.ValidationError as e: 
                bad_steps.append(f"Step {idx}: {e.message}")

        if not bad_steps: 
            print("\nTHIS PLAN HAS BEEN VALIDATED AND WILL NOW RUN\n")
            return "execute"
        else: 
            print("\nTHIS PLAN COULD NOT BE VALIDATED BECAUSE:\n")
            state.validation_error = "\n".join(bad_steps)
            return "cleanup"

    return validate
