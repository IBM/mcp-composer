import json, textwrap

def tool_to_doc(t): 
    "Flatten tool name + description + schema"
    return textwrap.dedent(f"""
        TOOL NAME: {t['name']}
        DESCRIPTION: {t['description']}
        SCHEMA: {t['args']}
    """).strip() 