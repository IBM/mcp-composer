"""Custom tool utility functions"""

import ast
import json
import os
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple
from deepdiff import DeepDiff

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

    rollback_versions: Dict[str, str] = {}
    rollback_file = "curl_rollback_versions.json"

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
    def _validate_curl_exists(api_name: str) -> bool:
        """
        Validate if the given API exists under custom_tool/openapi/
        Example: OpenApiTool.validate_api_exists("instana") - True / False
        """
        try:
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            api_path = os.path.join(parent_dir, "custom_tool", "curl", api_name)

            return os.path.isdir(api_path)
        except Exception as e:
            logger.exception("Failed to validate curl function tool existence: %s", e)
            return False

    @staticmethod
    def _load_rollback_versions() -> None:
        """Load rollback versions from curl_rollback_versions.json"""
        try:
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            rollback_path = os.path.join(parent_dir, ToolPaths.OUTPUT_DIR_NAME, DynamicToolGenerator.rollback_file)

            if os.path.exists(rollback_path):
                with open(rollback_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, meta in data.items():
                    DynamicToolGenerator.rollback_versions[name] = meta.get("rollback_version")
        except Exception as e:
            logger.warning("Failed to load rollback versions for DynamicToolGenerator: %s", e)

    @staticmethod
    def _get_curl_folder_and_file_path() -> Tuple[str, str]:
        """return folder and filepath for writing tools"""
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        folder_path = os.path.join(parent_dir, f"{ToolPaths.OUTPUT_DIR_NAME}/{ToolPaths.CURL_DIR_NAME}")
        filepath = os.path.join(folder_path, ToolPaths.CURL_TOOLS_FILE_NAME)
        return folder_path, filepath

    @staticmethod
    def _version_to_tuple(version: str) -> Tuple[int, int, int]:
        parts = version.lstrip("v").split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version}")
        major, minor, patch = map(int, parts)
        return major, minor, patch

    @staticmethod
    def _increment_version(version: str) -> str:
        major, minor, patch = DynamicToolGenerator._version_to_tuple(version)
        return f"v{major}.{minor}.{patch + 1}"

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
                req = client.build_request(method.upper(), url, headers=headers, json=body)
                res = await client.send(req)
                return {"status_code": res.status_code, "body": res.text}

        api_tool.__name__ = tool["id"]
        api_tool.__doc__ = tool["description"]
        return api_tool

    @staticmethod
    def set_rollback_version(api_name: str, version: str) -> None:
        """Set the rollback version for a given cURL-based API tool"""
        try:
            if DynamicToolGenerator._validate_curl_exists(api_name):
                normalized_version = version if version.startswith("v") else f"v{version}"
                parts = normalized_version.lstrip("v").split(".")
                if len(parts) != 3 or not all(p.isdigit() for p in parts):
                    raise ValueError(f"Invalid version format: {version}. Expected: vX.Y.Z or X.Y.Z")

                current_file = os.path.abspath(__file__)
                current_dir = os.path.dirname(current_file)
                parent_dir = os.path.dirname(current_dir)
                rollback_path = os.path.join(parent_dir, ToolPaths.OUTPUT_DIR_NAME, DynamicToolGenerator.rollback_file)

                if os.path.exists(rollback_path):
                    with open(rollback_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = {}

                data[api_name] = {"rollback_version": normalized_version}

                with open(rollback_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                DynamicToolGenerator.rollback_versions[api_name] = normalized_version
                logger.info("Rollback version set for %s: %s", api_name, version)
            else:
                raise ValueError("No tool found")
        except Exception as e:
            logger.exception("Failed to set rollback version: %s", e)
            raise

    @staticmethod
    def write_curl_to_file(tool_data: dict) -> None:
        """
        Write the curl-based tool to a versioned folder (custom_tool/curl/<tool_id>/vX.Y.Z/tools.json)
        Only write if content has changed. Version is incremented based on patch version.
        """
        try:
            tool_id = tool_data.get("id")
            if not tool_id:
                raise ValueError("Tool data must include an 'id' field")

            # Base path: custom_tool/curl/<tool_id>
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            base_path = Path(parent_dir) / ToolPaths.OUTPUT_DIR_NAME / ToolPaths.CURL_DIR_NAME / tool_id
            os.makedirs(base_path, exist_ok=True)

            # Get all versioned subdirectories starting with 'v'
            version_dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith("v")]
            latest_version_path = None
            latest_tool_data = None

            if version_dirs:
                latest_version_path = max(version_dirs, key=lambda d: DynamicToolGenerator._version_to_tuple(d.name))
                tools_file = latest_version_path / ToolPaths.CURL_TOOLS_FILE_NAME
                if tools_file.exists():
                    with open(tools_file, "r", encoding="utf-8") as f:
                        latest_tool_data = json.load(f)

            # If content unchanged, skip
            if latest_tool_data == tool_data:
                logger.info("No changes in tool data for %s. Skipping version increment.", tool_id)
                return

            # Compute next version
            if latest_version_path:
                next_version = DynamicToolGenerator._increment_version(latest_version_path.name)
            else:
                next_version = "v1.0.0"

            # Write tool data to next version
            version_path = base_path / next_version
            version_path.mkdir(parents=True, exist_ok=True)
            tools_file_path = version_path / ToolPaths.CURL_TOOLS_FILE_NAME

            with open(tools_file_path, "w", encoding="utf-8") as f:
                json.dump(tool_data, f, indent=2)

            logger.info("Tool data for '%s' written to: %s", tool_id, tools_file_path)

        except Exception as e:
            logger.exception("Failed to write cURL tool data to versioned file: %s", e)
            raise

    @staticmethod
    def read_curl_from_file() -> List[Callable[[], Any]]:
        """
        Read cURL tools for all APIs from rollback version if present, else latest version.
        Directory structure: custom_tool/curl/<api_name>/vX.Y.Z/tools.json
        """
        tools_list: List[Callable[[], Any]] = []

        try:
            # Load rollback versions first
            DynamicToolGenerator._load_rollback_versions()

            # Build base curl directory path
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            curl_base_path = Path(parent_dir) / ToolPaths.OUTPUT_DIR_NAME / ToolPaths.CURL_DIR_NAME

            if not curl_base_path.exists():
                logger.warning("No curl base directory found at %s", curl_base_path)
                return tools_list

            # Iterate over each API directory
            for api_dir in curl_base_path.iterdir():
                if not api_dir.is_dir():
                    continue

                api_name = api_dir.name
                rollback_version = DynamicToolGenerator.rollback_versions.get(api_name)
                version_path = None

                if rollback_version:
                    candidate = api_dir / rollback_version
                    if candidate.exists():
                        version_path = candidate
                        logger.info("Using rollback version %s for %s", rollback_version, api_name)
                    else:
                        logger.warning(
                            "Rollback version %s not found for %s. Falling back to latest.", rollback_version, api_name
                        )

                # Fallback to latest version if no rollback or rollback missing
                if not version_path:
                    version_dirs = [d for d in api_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
                    if not version_dirs:
                        logger.warning("No versioned folders found for tool %s", api_name)
                        continue
                    version_path = max(version_dirs, key=lambda d: DynamicToolGenerator._version_to_tuple(d.name))

                tools_json_path = version_path / ToolPaths.CURL_TOOLS_FILE_NAME
                if not tools_json_path.exists():
                    logger.warning("tools.json not found for %s at %s", api_name, tools_json_path)
                    continue

                with open(tools_json_path, "r", encoding="utf-8") as f:
                    tool_data = json.load(f)

                if isinstance(tool_data, dict):
                    tools_list.append(DynamicToolGenerator.create_api_request(tool_data))
                elif isinstance(tool_data, list):
                    for tool in tool_data:
                        tools_list.append(DynamicToolGenerator.create_api_request(tool))

        except Exception as e:
            logger.exception("Failed to read curl config for tools: %s", e)
            raise

        return tools_list

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
            func_defs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
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
                    node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
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

    rollback_versions: Dict[str, str] = {}
    rollback_file = "rollback_versions.json"

    def __init__(self, file_name: str, open_api: Dict, auth_config: Dict | None = None) -> None:
        self.output_dir = "custom_tool"
        self.file_name = f"{file_name}.json"
        self.auth_file_name = f"{file_name}_auth.json"
        self.open_api = open_api
        self.auth_config = auth_config
        self.api_name = file_name

        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        self.folder_path = os.path.join(parent_dir, self.output_dir)
        self.filepath = os.path.join(self.folder_path, self.file_name)
        self.auth_filepath = os.path.join(self.folder_path, self.auth_file_name)

    @staticmethod
    def _validate_api_exists(api_name: str) -> bool:
        """
        Validate if the given API exists under custom_tool/openapi/
        Example: OpenApiTool.validate_api_exists("instana") - True / False
        """
        try:
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            api_path = os.path.join(parent_dir, "custom_tool", "openapi", api_name)

            return os.path.isdir(api_path)
        except Exception as e:
            logger.exception("Failed to validate API existence: %s", e)
            return False

    @staticmethod
    def _load_rollback_versions() -> None:
        """Load rollback versions from rollback_versions.json into memory"""
        try:
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            rollback_path = os.path.join(parent_dir, "custom_tool", OpenApiTool.rollback_file)

            if os.path.exists(rollback_path):
                with open(rollback_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for api_name, meta in data.items():
                    OpenApiTool.rollback_versions[api_name] = meta.get("rollback_version")
        except Exception as e:
            logger.warning("Failed to load rollback versions: %s", e)

    @staticmethod
    def set_rollback_version(api_name: str, version: str) -> None:
        """
        Set the rollback version for a given API and persist to rollback_versions.json
        Example: OpenApiTool.set_rollback_version("google_openapi", "v1.0.0")
        """
        try:
            if OpenApiTool._validate_api_exists(api_name):
                # Normalize version to start with 'v'
                normalized_version = version if version.startswith("v") else f"v{version}"

                # Optional: Validate version format (basic)
                parts = normalized_version.lstrip("v").split(".")
                if len(parts) != 3 or not all(p.isdigit() for p in parts):
                    raise ValueError(f"Invalid version format: {version}. Expected format: vX.Y.Z or X.Y.Z")

                current_file = os.path.abspath(__file__)
                current_dir = os.path.dirname(current_file)
                parent_dir = os.path.dirname(current_dir)
                rollback_path = os.path.join(parent_dir, "custom_tool", OpenApiTool.rollback_file)

                # Load existing rollback versions if file exists
                if os.path.exists(rollback_path):
                    with open(rollback_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = {}

                # Set or update rollback version
                data[api_name] = {"rollback_version": normalized_version}

                # Save to file
                os.makedirs(os.path.dirname(rollback_path), exist_ok=True)
                with open(rollback_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                # Update in-memory
                OpenApiTool.rollback_versions[api_name] = normalized_version
                logger.info("Rollback version set for %s: %s", api_name, version)
            else:
                raise ValueError("No OpenAPI specification found")

        except Exception as e:
            logger.exception("Failed to set rollback version: %s", e)
            raise

    @staticmethod
    async def read_openapi_from_file() -> Dict[str, Tuple[Dict[str, Any], Any]]:
        """Read the latest or rollback-specified OpenAPI spec from custom_tool/openapi"""
        try:
            OpenApiTool._load_rollback_versions()

            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            base_path = Path(parent_dir) / "custom_tool" / "openapi"

            server_data: Dict[str, Tuple[Dict[str, Any], Any]] = {}

            if not base_path.exists():
                return server_data

            # Iterate through each API (e.g., google_openapi)
            for api_dir in base_path.iterdir():
                if not api_dir.is_dir():
                    continue

                api_name = api_dir.name

                # Get all version folders
                versions = [v for v in api_dir.iterdir() if v.is_dir() and v.name.startswith("v")]
                if not versions:
                    continue
                rollback_version = OpenApiTool.rollback_versions.get(api_name)
                selected_version_path = None
                # If rollback version is set and exists
                if rollback_version:
                    candidate_path = api_dir / rollback_version
                    if candidate_path.exists():
                        selected_version_path = candidate_path
                        logger.info("Rollback version %s used for %s", rollback_version, api_name)
                    else:
                        logger.warning(
                            "Rollback version %s not found for %s. Using latest.", rollback_version, api_name
                        )

                # If no rollback or invalid rollback, use latest
                if not selected_version_path:
                    selected_version_path = max(versions, key=lambda v: tuple(map(int, v.name.lstrip("v").split("."))))

                # Load spec files
                openapi_file = selected_version_path / f"{api_name}.json"
                auth_file = selected_version_path / f"{api_name}_auth.json"

                if openapi_file.exists():
                    with open(openapi_file, "r", encoding="utf-8") as f:
                        open_api = json.load(f)
                else:
                    continue  # skip if OpenAPI file not found

                auth_config = {}
                if auth_file.exists():
                    with open(auth_file, "r", encoding="utf-8") as f:
                        auth_config = json.load(f)

                server_url = open_api["servers"][0]["url"]
                server_name = open_api["info"]["title"].replace(" ", "_")

                server_data[server_name] = (
                    open_api,
                    await get_client(server_url, auth_config),
                )

            return server_data

        except Exception as e:
            logger.exception("Failed to read OpenAPI config from versioned folder: %s", e)
            raise

    def write_versioned_openapi(self) -> None:
        """Write OpenAPI spec to a versioned folder structure if the content has changed"""
        try:
            base_path = Path(self.folder_path) / "openapi" / self.api_name
            latest_version_path = self._get_latest_version_path(base_path)
            current_openapi = self.open_api

            if latest_version_path:
                with open(latest_version_path / f"{self.api_name}.json", "r", encoding="utf-8") as f:
                    existing_openapi = json.load(f)
                diff = DeepDiff(existing_openapi, current_openapi, ignore_order=True)

                if not diff:
                    logger.info("No changes detected in OpenAPI spec. Skipping version increment.")
                    return
                new_version = self._increment_version(latest_version_path.name)
            else:
                new_version = "v1.0.0"

            version_folder = base_path / new_version
            version_folder.mkdir(parents=True, exist_ok=True)

            # Write openapi spec
            with open(version_folder / f"{self.api_name}.json", "w", encoding="utf-8") as f:
                json.dump(current_openapi, f, indent=2)

            # Write auth config
            if self.auth_config:
                with open(version_folder / f"{self.api_name}_auth.json", "w", encoding="utf-8") as f:
                    json.dump(self.auth_config, f, indent=2)

            logger.info("Written OpenAPI spec to versioned folder: %s", version_folder)

        except Exception as e:
            logger.exception("Failed to write versioned OpenAPI spec: %s", e)
            raise

    def _get_latest_version_path(self, base_path: Path) -> Path | None:
        """Get the latest version folder path"""
        if not base_path.exists():
            return None
        versions = [p for p in base_path.iterdir() if p.is_dir() and p.name.startswith("v")]
        if not versions:
            return None
        return max(versions, key=lambda p: self._version_to_tuple(p.name))

    def _increment_version(self, version_str: str) -> str:
        """Increment patch version (v1.2.3 -> v1.2.4)"""
        major, minor, patch = self._version_to_tuple(version_str)
        return f"v{major}.{minor}.{patch + 1}"

    def _version_to_tuple(self, version_str: str) -> Tuple[int, int, int]:
        """Convert version string to tuple: v1.2.3 -> (1, 2, 3)"""
        parts = version_str.lstrip("v").split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version string: {version_str}. Expected format: vX.Y.Z")
        major, minor, patch = map(int, parts)
        return major, minor, patch
