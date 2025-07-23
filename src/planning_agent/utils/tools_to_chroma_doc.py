import json, textwrap
from planning_agent.core.state import parseDescriptions, clip
from planning_agent.ab_tests.constants import FilterApproaches

def tool_to_doc(t: object, approach: int = FilterApproaches.VECTOR_STORE_FULL_DESC): 
    "Flatten tool name + description + schema"
    
    if approach == FilterApproaches.VECTOR_STORE_FULL_TOOL: 
        return textwrap.dedent(f"""
            TOOL NAME: {t['name']}
            DESCRIPTION: {t['description']}
            SCHEMA: {t['args']}
        """).strip() 
    elif approach == FilterApproaches.VECTOR_STORE_FULL_DESC: 
        return textwrap.dedent(f"""
            TOOL NAME: {t['name']}
            DESCRIPTION: {t['description']}
        """).strip() 
    elif approach == FilterApproaches.VECTOR_STORE_PARSED_DESC:
        return textwrap.dedent(f"""
            TOOL NAME: {t['name']}
            DESCRIPTION: {parseDescriptions(t['description'])}
        """).strip() 
    else: 
        return textwrap.dedent(f"""
            TOOL NAME: {t['name']}
            DESCRIPTION: {clip(t['description'], 100)}
        """).strip() 