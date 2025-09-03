"""XML to JSON conversion middleware"""

import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, Union, List
from typing_extensions import override
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
import mcp.types as mt
from fastmcp.tools import Tool

from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class FormatXml2Json(Middleware):
    """Convert XML responses to JSON format in tool calls"""

    def __init__(self, mcp_composer):
        self.mcp_composer = mcp_composer

    def _xml_to_dict(self, element: ET.Element) -> Union[Dict[str, Any], str]:
        """Convert XML element to dictionary"""
        result = {}

        # Handle attributes
        if element.attrib:
            result["@attributes"] = dict(element.attrib)

        # Handle text content
        if element.text and element.text.strip():
            if not element.attrib and not list(element):
                # If no attributes and no children, return text directly
                return element.text.strip()
            result["#text"] = element.text.strip()

        # Handle child elements
        for child in element:
            child_data = self._xml_to_dict(child)
            # Strip namespace prefix from tag name
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if child_tag in result:
                # If tag already exists, convert to list
                if not isinstance(result[child_tag], list):
                    result[child_tag] = [result[child_tag]]
                result[child_tag].append(child_data)
            else:
                result[child_tag] = child_data

        return result

    def _parse_xml_string(self, xml_string: str) -> Dict[str, Any]:
        """Parse XML string and convert to dictionary"""
        try:
            # Remove any leading/trailing whitespace
            xml_string = xml_string.strip()

            # Parse XML
            root = ET.fromstring(xml_string)

            # Convert to dictionary, stripping namespace prefix from root tag
            root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            result = {root_tag: self._xml_to_dict(root)}

            return result
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise ToolFilterError(f"Invalid XML format: {e}")
        except Exception as e:
            logger.error(f"Error converting XML to JSON: {e}")
            raise ToolFilterError(f"XML to JSON conversion failed: {e}")

    def _is_xml_content(self, content: Any) -> bool:
        """Check if content appears to be XML"""
        if not isinstance(content, str):
            return False

        content = content.strip()
        return (
            content.startswith("<")
            and content.endswith(">")
            and ("<" in content[1:] and ">" in content[:-1])
        )

    def _convert_content_blocks(
        self, content_blocks: List[mt.ContentBlock]
    ) -> List[mt.ContentBlock]:
        """Convert XML content in content blocks to JSON"""
        converted_blocks = []

        for block in content_blocks:
            # Only process TextContent blocks
            if isinstance(block, mt.TextContent) and self._is_xml_content(block.text):
                try:
                    # Convert XML to JSON
                    json_data = self._parse_xml_string(block.text)
                    # Create a new TextContent block with JSON string
                    from dataclasses import replace, is_dataclass

                    if is_dataclass(block):
                        block = replace(block, text=json.dumps(json_data, indent=2))
                    else:
                        # Fallback for non-dataclass objects (like mocks)
                        block.text = json.dumps(json_data, indent=2)

                    logger.info("Converted XML content to JSON")
                except Exception as e:
                    logger.warning(f"Failed to convert XML content: {e}")
                    # Keep original content if conversion fails

            converted_blocks.append(block)

        return converted_blocks

    def _convert_structured_content(
        self, structured_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert XML in structured content to JSON"""
        if not structured_content:
            return structured_content

        def _convert_value(value: Any) -> Any:
            if isinstance(value, str) and self._is_xml_content(value):
                try:
                    return self._parse_xml_string(value)
                except Exception as e:
                    logger.warning(f"Failed to convert XML in structured content: {e}")
                    return value
            elif isinstance(value, dict):
                return {k: _convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_convert_value(item) for item in value]
            else:
                return value

        return _convert_value(structured_content)

    @override
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, Any],
    ) -> Any:
        """Convert XML responses to JSON format"""
        logger.debug("XML to JSON middleware processing tool call >>>>>>")

        try:
            # Call the next middleware/handler
            response = await call_next(context)

            # Check if it's a ToolResult or CallToolResult
            if hasattr(response, "structured_content"):
                # ToolResult type

                structured_attr = "structured_content"
            elif hasattr(response, "structuredContent"):
                # CallToolResult type

                structured_attr = "structuredContent"
            else:
                logger.debug("No structured content attribute found")
                structured_attr = None

            # Only process if content blocks contain XML
            if hasattr(response, "content") and response.content:
                xml_found = False
                converted_json_data = None

                # Check if any content block contains XML
                for block in response.content:
                    if isinstance(block, mt.TextContent) and self._is_xml_content(
                        block.text
                    ):
                        xml_found = True
                        # Convert XML to JSON
                        converted_json_data = self._parse_xml_string(block.text)
                        break

                # If XML found, convert content blocks and create structured content
                if xml_found and converted_json_data:
                    response.content = self._convert_content_blocks(response.content)

                    # Set structured content based on the response type
                    if structured_attr == "structured_content":
                        response.structured_content = converted_json_data

                    elif structured_attr == "structuredContent":
                        response.structuredContent = converted_json_data

            logger.debug("XML to JSON conversion completed")

            return response

        except Exception as e:
            logger.exception("Unexpected error in XML to JSON middleware: %s", e)
            # Return an error result instead of throwing, matching client behavior
            from mcp.types import TextContent, CallToolResult

            error_content = TextContent(
                type="text", text=f"XML to JSON conversion failed: {str(e)}"
            )
            return CallToolResult(
                content=[error_content], structuredContent=None, isError=True
            )
