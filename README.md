# Demo 

1. cd to test folder

2. run the following command 

```
uv run test_gw.py
```

3. Run the MCP Inspector

```

npx @modelcontextprotocol/inspector
```


4.  Open the MCP Inspector in a browser and run

<img width="388" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/4931cf7c-5a0b-4c18-b405-42df30bcac27">

5.  Go to Tools in the MCP Inspector and List Tools
   <img width="999" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/ce5eb760-d02c-42e5-9589-f807ce15ff15">

7.  We will first use the `register_mcp_server` tool  and register stock_info mcp server using the bellow config
   ```
{
  "id": "mcp-stock-info",
  "type": "http",
  "endpoint": "https://mcp-stock-info.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/mcp"
}
```

<img width="1684" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/af0157ab-c4e5-4a25-a2be-ccabd800ada7">


Once the tool is run , it will be successfully registered

<img width="1684" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/67f628fc-7773-496d-b9da-c44341f6d2d9">

9.  Clear Tool and List Tool again - This is where it might take long time or throw time out error based on the configuration of the MCP Inspector . In case you have time out error disconnect the server and connect again and run the List Tool , it will show 2 tools from gateway and all tools from mcp-stockinfo
<img width="1661" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/caefc2d8-7528-4231-a81f-5885cc0deab8">

10.  Run any tools

<img width="1670" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/f6678d13-99d3-4367-93ad-ab58d6431532">

