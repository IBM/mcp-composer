import os
import ast
import textwrap


from mcp_composer.exceptions import ToolGenerateError
from mcp_composer.settings.tool_setting import ToolSettings
from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.utils.utils import (
    ensure_dependencies_installed,
    extract_imported_modules,
)

logger = LoggerFactory.get_logger()


class DynamicToolGenerator:
    def __init__(self):
        self.output_dir = "custom_tool"
        self.file_name = "tools.py"

        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        self.folder_path = os.path.join(parent_dir, self.output_dir)
        self.filepath = os.path.join(self.folder_path, self.file_name)
        self._ensure_base_file()

    def _ensure_base_file(self):
        """Create folder and Create the file with shared imports if not exists"""
        os.makedirs(self.folder_path, exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                f.write("import httpx\n")
                f.write("from collections import OrderedDict\n\n")
                f.write("# --- Generated tool functions below ---\n\n")

    def _parse_script_to_ast(self, script: str):
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

    def create_from_script(self, script_model: ToolSettings):
        try:
            if script_model.script_config:
                script = script_model.script_config["value"]
                tree = self._parse_script_to_ast(script)

                # Step 1: Detect and install dependencies
                dependencies = extract_imported_modules(script)
                ensure_dependencies_installed(dependencies)

                # Prepare safe execution context
                safe_globals = {"__builtins__": __builtins__}
                local_namespace = {}

                # Compile and execute user script
                compiled_code = compile(tree, filename="<user_script>", mode="exec")
                exec(compiled_code, safe_globals, local_namespace)

                # find function defined in the script
                for fn in local_namespace.values():
                    if callable(fn):
                        self.write_function_to_file(fn.__name__, script)
                        return fn
                    else:
                        raise ToolGenerateError("Invalid script provided.")

        except SyntaxError as e:
            logger.exception("Syntax error in script: %s", e)
            raise

        except ValueError as e:
            logger.exception("Validation failed: %s", str(e))
            raise

        except ToolGenerateError as e:
            logger.exception("Script error: %s", str(e))
            raise

    def write_function_to_file(self, func_name: str, function_code: str):
        # Check for duplicate function if file exists
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    existing_code = f.read()

                tree = ast.parse(existing_code, mode="exec")
                defined_funcs = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if func_name in defined_funcs:
                    raise ValueError(f"Function '{func_name}' already exists in.")

            except ValueError as e:
                logger.exception("Python script eriting to file failed: %s", str(e))
                raise e

            except SyntaxError as e:
                logger.exception(f"Failed to parse the file: {e}")
                raise RuntimeError(f"Failed to parse the file: {e}")

        # Clean and append function code
        try:
            cleaned_code = textwrap.dedent(function_code).strip()

            with open(self.filepath, "a") as f:
                f.write(f"\n# --- MCP Tool function: {func_name} ---\n")
                f.write(cleaned_code + "\n")
        except Exception as e:
            raise RuntimeError(f"Failed to write function to file: {e}")
