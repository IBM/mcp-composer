"""Custom tool utility functions"""

import ast
import json
import os
import textwrap
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import httpx

from mcp_composer.core.models.tool import ToolBuilderConfig
from mcp_composer.core.utils.auth_strategy import get_client
from mcp_composer.core.utils.exceptions import ToolGenerateError
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.utils import (
    ensure_dependencies_installed,
    extract_imported_modules,
)

logger = LoggerFactory.get_logger()


class ToolPaths:
    """Custom tool paths"""

    OUTPUT_DIR_NAME = "custom_tool"
    TOOLS_FILE_NAME = "tools.py"
    CURL_TOOLS_FILE_NAME = "tools.json"
    CURL_DIR_NAME = "curl"


class DynamicToolGenerator:
    """Custom Tool generator class"""

    def __init__(self) -> None:
        self.output_dir = ToolPaths.OUTPUT_DIR_NAME
        self.file_name = ToolPaths.TOOLS_FILE_NAME

        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        self.folder_path = os.path.join(parent_dir, self.output_dir)
        self.filepath = os.path.join(self.folder_path, self.file_name)
        self._ensure_base_file()

    @staticmethod
    def _get_curl_folder_and_file_path() -> Tuple[str, str]:
        """return folder and filepath for writing tools"""
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        folder_path = os.path.join(
            parent_dir, f"{ToolPaths.OUTPUT_DIR_NAME}/{ToolPaths.CURL_DIR_NAME}"
        )
        filepath = os.path.join(folder_path, ToolPaths.CURL_TOOLS_FILE_NAME)
        return folder_path, filepath

    @staticmethod
    def create_api_request(tool: Dict[str, Any]) -> Callable[[], Any]:
        """Create API tool"""
        logger.info("Generate tool from API request on the fly:%s", tool)

        async def api_tool() -> Dict[str, Any]:
            data = tool.get("data")
            headers = tool["headers"]
            method = tool["method"]
            body = data if data else None
            url = tool["url"]

            async with httpx.AsyncClient() as client:
                req = client.build_request(
                    method.upper(), url, headers=headers, json=body
                )
                res = await client.send(req)
                return {"status_code": res.status_code, "body": res.text}

        api_tool.__name__ = tool["id"]
        api_tool.__doc__ = tool["description"]
        return api_tool

    @staticmethod
    def write_curl_to_file(tool_data: dict) -> None:
        """Write the converted cURL command as a Python function into a file."""
        try:
            folder_path, filepath = (
                DynamicToolGenerator._get_curl_folder_and_file_path()
            )
            os.makedirs(folder_path, exist_ok=True)

            if os.path.exists(filepath):
                existing = json.loads(Path(filepath).read_text(encoding="utf-8"))
                if existing:
                    # Deep copy to avoid modifying originals
                    result = deepcopy(existing)
                    tool_id = tool_data.get("id")
                    updated = False
                    for i, tool in enumerate(result):
                        if tool.get("id") == tool_id:
                            result[i] = tool_data  # Overwrite with new config
                            updated = True
                            logger.info("Updated tool '%s' in local file", tool_id)
                            break
                    if not updated:
                        result.append(tool_data)
                    Path(filepath).write_text(
                        json.dumps(result, indent=2), encoding="utf-8"
                    )
            else:
                Path(filepath).write_text(
                    json.dumps([tool_data], indent=2), encoding="utf-8"
                )

        except Exception as e:
            logger.exception("Failed to write curl config to file: %s", e)
            raise

    @staticmethod
    def read_curl_from_file() -> List[Callable[[], Any]]:
        """Read curl command python function from file"""
        try:
            _, filepath = DynamicToolGenerator._get_curl_folder_and_file_path()
            tools_list: List[Callable[[], Any]] = []
            if os.path.exists(filepath):
                tools = json.loads(Path(filepath).read_text(encoding="utf-8"))
                for tool in tools:
                    tools_list.append(DynamicToolGenerator.create_api_request(tool))
            return tools_list
        except Exception as e:
            logger.exception("Failed to read  curl config from file: %s", e)
            raise

    def _ensure_base_file(self) -> None:
        """Create folder and Create the file with shared imports if not exists"""
        os.makedirs(self.folder_path, exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write("import httpx\n")
                f.write("from collections import OrderedDict\n\n")
                f.write("# --- Generated tool functions below ---\n\n")

    def _parse_script_to_ast(self, script: str) -> ast.Module:
        """validate python script"""
        try:
            tree = ast.parse(script, mode="exec")
            func_defs = [
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if len(func_defs) != 1:
                raise ValueError("Script must contain exactly one function.")
            return tree
        except SyntaxError as e:
            raise e

    def _write_function_to_file(self, func_name: str, function_code: str) -> None:
        """Write parsed python script to file"""
        # Check for duplicate function if file exists
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    existing_code = f.read()

                tree = ast.parse(existing_code, mode="exec")
                defined_funcs = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if func_name in defined_funcs:
                    raise ValueError(f"Function {func_name} already exists in.")

            except ValueError as e:
                logger.exception("Python script writing to file failed: %s", str(e))
                raise e

            except SyntaxError as e:
                logger.exception("Failed to parse the file: %s", e)
                raise RuntimeError(f"Failed to parse the file: {e}") from e

        # Clean and append function code
        try:
            cleaned_code = textwrap.dedent(function_code).strip()

            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(f"\n# --- MCP Tool function: {func_name} ---\n")
                f.write(cleaned_code + "\n")
        except Exception as e:
            raise RuntimeError(f"Failed to write function to file:{e}") from e

    def create_from_script(self, script_model: ToolBuilderConfig) -> Callable[[], Any]:
        """Create a Python function from a Python script string"""
        try:
            if script_model.script_config:
                script = script_model.script_config["value"]
                tree = self._parse_script_to_ast(script)

                # Step 1: Detect and install dependencies
                dependencies = extract_imported_modules(script)
                ensure_dependencies_installed(dependencies)

                # Prepare safe execution context
                safe_globals = {"__builtins__": __builtins__}
                local_namespace: Dict[str, Any] = {}

                # Compile and execute user script
                compiled_code = compile(tree, filename="<user_script>", mode="exec")
                exec(compiled_code, safe_globals, local_namespace)

                # find function defined in the script
                for fn in local_namespace.values():
                    if callable(fn):
                        self._write_function_to_file(fn.__name__, script)
                        return fn

                # If no callable function was found
                raise ValueError("No callable function found in the script")

        except SyntaxError as e:
            logger.exception("Syntax error in script: %s", e)
            raise

        except ValueError as e:
            logger.exception("Validation failed: %s", str(e))
            raise

        except ToolGenerateError as e:
            logger.exception("Script error: %s", str(e))
            raise

        # If script_model.script_config doesn't exist
        raise ValueError("No script configuration provided")


class OpenApiTool:
    """Custom tool generator for OpenAPI specification"""

    def __init__(
        self, file_name: str, open_api: Dict, auth_config: Dict | None = None
    ) -> None:
        self.output_dir = "custom_tool"
        self.file_name = f"{file_name}.json"
        self.auth_file_name = f"{file_name}_auth.json"
        self.open_api = open_api
        self.auth_config = auth_config

        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        self.folder_path = os.path.join(parent_dir, self.output_dir)
        self.filepath = os.path.join(self.folder_path, self.file_name)
        self.auth_filepath = os.path.join(self.folder_path, self.auth_file_name)
        self._ensure_base_file()

    @staticmethod
    async def read_openapi_from_file() -> Dict[str, Tuple[Dict[str, Any], Any]]:
        """Read openapi specification"""
        try:
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            folder_path = os.path.join(parent_dir, ToolPaths.OUTPUT_DIR_NAME)
            file_pairs: Dict[str, Dict[str, Path]] = {}
            server_data: Dict[str, Tuple[Dict[str, Any], Any]] = {}
            if os.path.exists(folder_path):
                for file in Path(folder_path).glob("*.json"):
                    name = file.stem
                    if name.endswith("_auth"):
                        base = name.replace("_auth", "")
                        file_pairs.setdefault(base, {})["auth"] = file
                    else:
                        file_pairs.setdefault(name, {})["open_api"] = file
                # Read both files together
                for _, files in file_pairs.items():
                    open_api = {}
                    auth_config = {}

                    if "open_api" in files:
                        with files["open_api"].open() as f:
                            open_api = json.load(f)
                    if "auth" in files:
                        with files["auth"].open() as f:
                            auth_config = json.load(f)
                    server_url = open_api["servers"][0]["url"]
                    server_name = open_api["info"]["title"].replace(" ", "_")

                    server_data[server_name] = (
                        open_api,
                        await get_client(server_url, auth_config),
                    )
            return server_data
        except Exception as e:
            logger.exception("Failed to read  curl config from file:%s", e)
            raise

    def _ensure_base_file(self) -> None:
        """Create folder and Create the file"""
        os.makedirs(self.folder_path, exist_ok=True)
        for path in [self.filepath, self.auth_filepath]:
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({}, f)

    def write_openapi(self) -> None:
        """write OpenAPI specification to file"""
        try:
            existing = json.loads(Path(self.filepath).read_text(encoding="utf-8"))
            if existing:
                # Deep copy to avoid modifying originals
                result = deepcopy(existing)

                # Merge paths
                for path, methods in self.open_api.get("paths", {}).items():
                    if path not in result["paths"]:
                        result["paths"][path] = methods
                    else:
                        # Merge methods under the same path (e.g., get/post)
                        result["paths"][path].update(methods)

                # Merge components
                new_components = self.open_api.get("components", {})
                result_components = result.setdefault("components", {})
                for section, items in new_components.items():
                    section_dict = result_components.setdefault(section, {})
                    for k, v in items.items():
                        if k in section_dict:
                            logger.info("Skipping duplicate component:%s", section)
                        else:
                            section_dict[k] = v

                # Merge tags (avoid duplicates by name)
                existing_tags = {tag["name"] for tag in result.get("tags", [])}
                new_tags = self.open_api.get("tags", [])
                for tag in new_tags:
                    if tag["name"] not in existing_tags:
                        result.setdefault("tags", []).append(tag)

                Path(self.filepath).write_text(
                    json.dumps(result, indent=2), encoding="utf-8"
                )
            else:
                Path(self.filepath).write_text(
                    json.dumps(self.open_api, indent=2), encoding="utf-8"
                )

            if self.auth_config:
                Path(self.auth_filepath).write_text(
                    json.dumps(self.auth_config, indent=2), encoding="utf-8"
                )

        except Exception as e:
            logger.exception("Failed to write OpenAPI spec to file: %s", e)
            raise
