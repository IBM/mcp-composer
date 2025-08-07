"""countries_graphql_mcp.py"""

import httpx
from fastmcp.tools import Tool

# from dotenv import load_dotenv

# load_dotenv()

GRAPHQL_INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      name
      kind
      fields {
        name
        args {
          name
          type { name kind }
        }
        type { name kind }
      }
    }
  }
}
"""

# Configuration (can be placed in a YAML or .env if needed)
config = {
    "id": "mcp-countries",
    "type": "graphql",
    "graphql": {"endpoint": "https://countries.trevorblades.com/"},
    "auth_strategy": "none",  # can be bearer or header if needed
    "auth": {"auth_prefix": "", "token": ""},
}


# Set up the HTTP client
GRAPHQL_ENDPOINT = config["graphql"]["endpoint"]
headers = {}

# If auth is required
if config["auth_strategy"] == "bearer":
    headers["Authorization"] = (
        f"{config['auth']['auth_prefix']} {config['auth']['token']}"
    )

http_client = httpx.AsyncClient(base_url=GRAPHQL_ENDPOINT, headers=headers)


async def fetch_graphql_schema():
    """Fetch GraphQL Schema via Introspection"""
    resp = await http_client.post("", json={"query": GRAPHQL_INTROSPECTION_QUERY})
    resp.raise_for_status()
    return resp.json()["data"]["__schema"]


async def create_tools(schema):
    """Dynamically Create Tools from Queries"""
    tools = []
    for gql_type in schema["types"]:
        if (
            gql_type["kind"] == "OBJECT"
            and gql_type["name"] == schema["queryType"]["name"]
        ):
            for field in gql_type["fields"]:
                tool_name = field["name"]
                arg_defs = field.get("args", [])

                def make_tool(tool_name, arg_defs):
                    async def tool_func(**kwargs):
                        arg_str = ", ".join(
                            f'{arg["name"]}: "{kwargs.get(arg["name"], "")}"'
                            for arg in arg_defs
                        )
                        query_body = (
                            f"""
                        query {{
                          {tool_name}({arg_str}) {{
                            __typename
                          }}
                        }}"""
                            if arg_str
                            else f"query {{ {tool_name} {{ __typename }} }}"
                        )
                        response = await http_client.post(
                            "", json={"query": query_body}
                        )
                        response.raise_for_status()
                        return response.json()

                    return Tool.from_function(
                        tool_func, name=tool_name, description=f"Query {tool_name}"
                    )

                tools.append(make_tool(tool_name, arg_defs))
    return tools
