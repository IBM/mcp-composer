"""countries_graphql_mcp.py"""

import inspect
import json

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
                    # Create function signature dynamically based on arguments
                    if arg_defs:
                        param_names = [arg["name"] for arg in arg_defs if arg.get("name")]

                        async def dynamic_arg_tool(**kwargs):
                            missing = [p for p in param_names if p not in kwargs]
                            if missing:
                                raise ValueError(
                                    f"Missing required arguments: {', '.join(missing)}"
                                )

                            arg_assignments = []
                            for name in param_names:
                                value = kwargs[name]
                                if isinstance(value, bool):
                                    formatted_value = "true" if value else "false"
                                elif value is None:
                                    formatted_value = "null"
                                else:
                                    formatted_value = json.dumps(value)
                                arg_assignments.append(f"{name}: {formatted_value}")

                            args_string = ", ".join(arg_assignments)
                            query_body = (
                                f"""
                        query {{
                          {tool_name}({args_string}) {{
                            __typename
                          }}
                        }}"""
                            )

                            response = await http_client.post(
                                "", json={"query": query_body}
                            )
                            response.raise_for_status()
                            return response.json()

                        dynamic_arg_tool.__name__ = f"{tool_name}_tool"
                        dynamic_arg_tool.__signature__ = inspect.Signature(
                            [
                                inspect.Parameter(
                                    name,
                                    inspect.Parameter.KEYWORD_ONLY,
                                    default=inspect._empty,
                                )
                                for name in param_names
                            ]
                        )

                        return Tool.from_function(
                            dynamic_arg_tool,
                            name=tool_name,
                            description=f"Query {tool_name} with parameters: {', '.join(param_names)}",
                        )
                    # Create a function without parameters
                    async def tool_func_without_args():
                        query_body = f"query {{ {tool_name} {{ __typename }} }}"
                        response = await http_client.post(
                            "", json={"query": query_body}
                        )
                        response.raise_for_status()
                        return response.json()

                    # Create the tool with the function that has no parameters
                    return Tool.from_function(
                        tool_func_without_args,
                        name=tool_name,
                        description=f"Query {tool_name}",
                    )

                tools.append(make_tool(tool_name, arg_defs))
    return tools
