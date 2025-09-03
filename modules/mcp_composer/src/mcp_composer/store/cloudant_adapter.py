"""cloudant_adapter.py"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List

from ibm_cloud_sdk_core import ApiException
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibmcloudant import CloudantV1
from ibmcloudant.cloudant_v1 import Document

from mcp_composer.core.utils.exceptions import ToolDuplicateError
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.core.utils.tools import check_duplicate_tool

from .database import DatabaseInterface

logger = LoggerFactory.get_logger()
if TYPE_CHECKING:
    from mcp_composer.core.composer import MCPComposer


class CloudantAdapter(DatabaseInterface):
    def __init__(self, api_key: str, service_url: str, db_name: str = "mcp_servers"):
        self._db_name = db_name
        self._api_key = api_key
        self._service_url = service_url
        self._client = self._initialize_client()

    def _initialize_client(self) -> CloudantV1:
        if not self._api_key or not self._service_url:
            raise ValueError("Both api_key and service_url must be provided")

        authenticator = IAMAuthenticator(self._api_key)
        client = CloudantV1(authenticator=authenticator)
        client.set_service_url(self._service_url)

        if self._db_name not in client.get_all_dbs().get_result():
            client.put_database(self._db_name)

        return client

    def _save_disabled_tools_to_db(
        self, server_id: str, tools: list[str], enable: bool
    ) -> None:
        tools = list(set(tools))  # Remove duplicates
        try:
            # Try to fetch the existing document
            existing_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()

            if enable:
                # Simply overwrite disabled tools
                existing_doc["disabled_tools"] = tools
            else:
                if len(tools) == 1 and tools[0].lower() == "all":
                    existing_tools = []
                else:
                    existing_tools = existing_doc.get("disabled_tools", [])

                if existing_tools:
                    logger.info(
                        "Remove tool list is already %s present in cloudant for server_id %s. Updating list. Response: %s",
                        existing_tools,
                        server_id,
                        existing_doc,
                    )

                    duplicate_tool = check_duplicate_tool(existing_tools, tools)
                    if duplicate_tool:
                        raise ToolDuplicateError(
                            f"Tool {duplicate_tool} is already removed"
                        )

                    existing_doc["disabled_tools"].extend(tools)
                else:
                    existing_doc["disabled_tools"] = tools

            # Save updated document
            response = self._client.post_document(
                db=self._db_name,
                document=existing_doc,
            ).get_result()

            logger.info(
                "Saved disabled tool list '%s' for server '%s'. Response: '%s'",
                existing_doc["disabled_tools"],
                server_id,
                response,
            )

        except ApiException as e:
            if e.code == 404 and not enable:
                # Create a new document if server not found and we're disabling tools
                logger.info(
                    "Server %s does not exist in database. Adding with disabled tools list.",
                    server_id,
                )
                tool_doc = Document(
                    _id=server_id, id=server_id, disabled_tools=tools, type="composer"
                )
                response = self._client.post_document(
                    db=self._db_name,
                    document=tool_doc,
                ).get_result()

                logger.info(
                    "Saved disabled tool list '%s' for server '%s'. Response: '%s'",
                    tools,
                    server_id,
                    response,
                )
            else:
                logger.error("Failed to save disabled tool list: %s", str(e))

    def load_all_servers(self) -> List[Dict]:
        try:
            result = self._client.post_all_docs(
                db=self._db_name, include_docs=True
            ).get_result()
            return [row["doc"] for row in result.get("rows", []) if "doc" in row]
        except Exception as exc:
            logger.error("Cloudant read failed: %s", exc)
            return []

    def add_server(self, config: Dict) -> None:
        doc_id = config["id"]
        try:
            existing = self._client.get_document(
                db=self._db_name, doc_id=doc_id
            ).get_result()
            config["_rev"] = existing["_rev"]  # Set revision ID for update

            # Update existing document
            self._client.post_document(
                db=self._db_name, document=Document(**config)
            ).get_result()
            logger.info("Updated server '%s' in Cloudant", doc_id)
        except ApiException as e:
            if e.code == 404:
                try:
                    self._client.post_document(
                        db=self._db_name, document=Document(**config)
                    ).get_result()
                    logger.info("Saved server '%s' to Cloudant", doc_id)
                except Exception as post_err:
                    logger.error("Failed to save server '%s': %s", doc_id, post_err)
            else:
                logger.error("Error checking server '%s': %s", doc_id, e)

    def remove_server(self, server_id: str) -> None:
        try:
            result = self._client.post_find(
                db=self._db_name, selector={"id": {"$eq": server_id}}
            ).get_result()

            for doc in result.get("docs", []):
                self._client.delete_document(
                    db=self._db_name, doc_id=doc["_id"], rev=doc["_rev"]
                )
                logger.info("Deleted server '%s' from Cloudant", server_id)
        except Exception as exc:
            logger.error("Cloudant operation failed: %s", exc)

    def disable_tools(self, tools: list[str], server_id: str) -> None:
        """Disable tools for a member server."""
        self._save_disabled_tools_to_db(server_id, tools, enable=False)

    def enable_tools(self, tools: list[str], server_id: str) -> None:
        """Enable tools for a member server."""
        self._save_disabled_tools_to_db(server_id, tools, enable=True)

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        try:
            # Try to retrieve the existing server document
            existing_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()

            # Update or initialize tools_description
            tools_description = existing_doc.get("tools_description", {})
            tools_description[tool] = description
            existing_doc["tools_description"] = tools_description

            # Save the updated document
            response = self._client.post_document(
                db=self._db_name,
                document=existing_doc,
            ).get_result()

            logger.info(
                "Updated tool description '%s' for server '%s'. Response: %s",
                description,
                server_id,
                response,
            )

        except ApiException as e:
            if e.code == 404:
                # Document does not exist, create a new one
                logger.info(
                    "Server '%s' not found in database. Adding it with tool description.",
                    server_id,
                )
                tool_doc = Document(
                    _id=server_id,
                    id=server_id,
                    tools_description={tool: description},
                )
                response = self._client.post_document(
                    db=self._db_name,
                    document=tool_doc,
                ).get_result()

                logger.info(
                    "Saved tool description '%s' for server '%s'. Response: %s",
                    description,
                    server_id,
                    response,
                )
            else:
                logger.error("Failed to save tool description: %s", str(e))

    def disable_prompts(self, prompts: list[str], server_id: str) -> None:
        try:
            # check if server config already present in db
            existing_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            prompts = list(set(prompts))
            existing_prompts = existing_doc.get("disabled_prompts", [])
            prompts_description = existing_doc.get("prompts_description", {})

            # check the prompt already present in disabled prompts list
            # if yes raise error, else update the disabled prompts list
            if existing_prompts:
                logger.info(
                    """Disabled prompt list is already
                        %s present in cloudant for server_id %s.
                        So, update the disabled prompt list.
                        Response: %s""",
                    existing_prompts,
                    server_id,
                    existing_doc,
                )

                duplicate_prompt = check_duplicate_tool(existing_prompts, prompts)
                if duplicate_prompt:
                    raise ToolDuplicateError(
                        f"Prompt {duplicate_prompt} is already disabled"
                    )
                existing_doc["disabled_prompts"].extend(prompts)
            else:
                # if no disabled prompts list present add it
                existing_doc["disabled_prompts"] = prompts

            # Remove prompt descriptions if they exist
            if existing_doc["disabled_prompts"] and prompts_description:
                for prompt in existing_doc["disabled_prompts"]:
                    prompts_description.pop(prompt, None)

            response = self._client.post_document(
                db=self._db_name,
                document=existing_doc,
            ).get_result()

            logger.info(
                """Saved disabled prompt list '%s'
                    for server '%s'.
                    Response: '%s'""",
                existing_doc["disabled_prompts"],
                server_id,
                response,
            )

        except ApiException as e:
            # Add server config to db with disabled prompts list, since it not exist
            if e.code == 404:
                logger.info(
                    "Server %s is not exist in database. Adding the server with disabled prompt list",
                    server_id,
                )
                prompt_doc = Document(
                    _id=server_id, id=server_id, disabled_prompts=prompts
                )
                response = self._client.post_document(
                    db=self._db_name,
                    document=prompt_doc,
                ).get_result()
                logger.info(
                    """Saved disabled prompt list '%s'
                        for server '%s'.
                        Response: '%s'""",
                    prompts,
                    server_id,
                    response,
                )
            else:
                logger.error("Failed to save disabled prompt list:%s", str(e))

    def enable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Enable prompts which already disabled"""
        try:
            # check if server config already present in db
            existing_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            existing_doc["disabled_prompts"] = prompts

            response = self._client.post_document(
                db=self._db_name,
                document=existing_doc,
            ).get_result()

            logger.info(
                """Saved disabled prompt list '%s'
                    for server '%s'.
                    Response: '%s'""",
                existing_doc["disabled_prompts"],
                server_id,
                response,
            )
        except Exception as e:
            logger.error("Failed to save disabled prompt list:%s", str(e))

    def disable_resources(self, resources: list[str], server_id: str) -> None:
        try:
            # check if server config already present in db
            existing_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            resources = list(set(resources))
            existing_resources = existing_doc.get("disabled_resources", [])
            resources_description = existing_doc.get("resources_description", {})

            # check the resource already present in disabled resources list
            # if yes raise error, else update the disabled resources list
            if existing_resources:
                logger.info(
                    """Disabled resource list is already
                        %s present in cloudant for server_id %s.
                        So, update the disabled resource list.
                        Response: %s""",
                    existing_resources,
                    server_id,
                    existing_doc,
                )

                duplicate_resource = check_duplicate_tool(existing_resources, resources)
                if duplicate_resource:
                    raise ToolDuplicateError(
                        f"Resource {duplicate_resource} is already disabled"
                    )
                existing_doc["disabled_resources"].extend(resources)
            else:
                # if no disabled resources list present add it
                existing_doc["disabled_resources"] = resources

            # Remove resource descriptions if they exist
            if existing_doc["disabled_resources"] and resources_description:
                for resource in existing_doc["disabled_resources"]:
                    resources_description.pop(resource, None)

            response = self._client.post_document(
                db=self._db_name,
                document=existing_doc,
            ).get_result()

            logger.info(
                """Saved disabled resource list '%s'
                    for server '%s'.
                    Response: '%s'""",
                existing_doc["disabled_resources"],
                server_id,
                response,
            )

        except ApiException as e:
            # Add server config to db with disabled resources list, since it not exist
            if e.code == 404:
                logger.info(
                    "Server %s is not exist in database. Adding the server with disabled resource list",
                    server_id,
                )
                resource_doc = Document(
                    _id=server_id, id=server_id, disabled_resources=resources
                )
                response = self._client.post_document(
                    db=self._db_name,
                    document=resource_doc,
                ).get_result()
                logger.info(
                    """Saved disabled resource list '%s'
                        for server '%s'.
                        Response: '%s'""",
                    resources,
                    server_id,
                    response,
                )
            else:
                logger.error("Failed to save disabled resource list:%s", str(e))

    def enable_resources(self, resources: list[str], server_id: str) -> None:
        """Enable resources which already disabled"""
        try:
            # check if server config already present in db
            existing_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            existing_doc["disabled_resources"] = resources

            response = self._client.post_document(
                db=self._db_name,
                document=existing_doc,
            ).get_result()

            logger.info(
                """Saved disabled resource list '%s'
                    for server '%s'.
                    Response: '%s'""",
                existing_doc["disabled_resources"],
                server_id,
                response,
            )
        except Exception as e:
            logger.error("Failed to save disabled resource list:%s", str(e))

    def get_document(self, server_id: str) -> Dict:
        # get the server config details of a single server
        server_doc = {}
        try:
            server_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()

            logger.info(
                "Retrieve server '%s' config details from Cloudant. Response: %s",
                server_id,
                server_doc,
            )

        except ApiException as e:
            logger.error("No server details found in  DB: %s", e)
        return server_doc

    def mark_deactivated(self, server_id: str) -> None:
        try:
            # Get the document first
            doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            doc["status"] = "deactivated"

            # Update the document with new status
            response = self._client.post_document(
                db=self._db_name,
                document=doc,
            ).get_result()
            logger.info(
                "Marked server '%s' as deactivated. Response: %s", server_id, response
            )
        except ApiException as e:
            if e.code == 404:
                logger.error("Server '%s' not found. Cannot deactivate.", server_id)
            else:
                logger.error("Error deactivating server '%s': %s", server_id, e)

        except Exception as e:
            logger.error(
                "Unexpected error while deactivating server '%s': %s", server_id, e
            )

    def get_server_status(self, server_id: str) -> str:
        try:
            doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            status = doc.get("status", "active")  # default to 'active' if not set
            logger.info("Server '%s' has status: %s", server_id, status)
            return status
        except ApiException as e:
            if e.code == 404:
                logger.warning("Server '%s' not found when fetching status.", server_id)
            else:
                logger.error(
                    "Error retrieving server status for '%s': %s", server_id, e
                )

        except Exception as e:
            logger.error(
                "Unexpected error retrieving status for '%s': %s", server_id, e
            )

        return "unknown"

    def update_server_config(self, config: dict) -> None:
        """
        Update the configuration of an existing server.
        If the document does not exist, raise an error.
        """
        server_id = config.get("id")
        if not server_id:
            raise ValueError("Config must include 'id' to update.")

        try:
            existing = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()

            config["_rev"] = existing["_rev"]

            self._client.post_document(
                db=self._db_name, document=Document(**config)
            ).get_result()

            logger.info("Updated configuration for server '%s'", server_id)

        except ApiException as e:
            if e.code == 404:
                logger.error("Server '%s' not found in Cloudant.", server_id)
                raise ValueError(f"Server '{server_id}' not found in Cloudant.") from e
            else:
                logger.error("Failed to update server '%s': %s", server_id, e)
                raise
