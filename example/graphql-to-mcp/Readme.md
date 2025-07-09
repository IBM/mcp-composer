# Configuration 

```
[
  {
    "id": "mcp-countries",
    "type": "graphql",
    "graphql": {
      "endpoint": "https://countries.trevorblades.com/",
      "schema_filepath": "schemas/countries.graphql"
    },
    "auth_strategy": "none",
    "auth": {}
  },
  {
    "id": "mcp-pokemon",
    "type": "graphql",
    "graphql": {
      "endpoint": "https://graphqlpokemon.favware.tech/v8",
      "schema_filepath": "schemas/pokemon.graphql"
    },
    "auth_strategy": "none",
    "auth": {}
  }
]
```
# GraphQLTool  Class

GraphQLTool (graphql_tool.py)

- A Pydantic-compatible Tool subclass that:

- Accepts query and optional variables

- Sends payloads to the GraphQL API

- Returns results as TextContent

- Uses PrivateAttr() to store endpoint and headers



# Input 

```
{
  "query": "{ country(code: \"BR\") { name capital emoji } }"
}
```

# Output

```
[
  {
    "type": "text",
    "text": "{\"data\":{\"country\":{\"name\":\"Brazil\",...}}"
  }
]

```