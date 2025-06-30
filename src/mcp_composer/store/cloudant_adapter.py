# cloudant_adapter.py
from typing import List, Dict
from ibmcloudant import CloudantV1
from ibm_cloud_sdk_core import ApiException
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibmcloudant.cloudant_v1 import Document
from mcp_composer.utils import LoggerFactory, check_duplicate_tool
from mcp_composer.exceptions import ToolDuplicateError
from .database import DatabaseInterface


logger = LoggerFactory.get_logger()


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

    def _add_record(self, record: dict):
        doc_id = record["id"]
        try:
            existing = self._client.get_document(
                db=self._db_name, doc_id=doc_id
            ).get_result()
            record["_rev"] = existing["_rev"]  # Set revision ID for update

            # Update existing document
            self._client.post_document(
                db=self._db_name, document=Document(**record)
            ).get_result()
            logger.info("Updated record '%s' in Cloudant", doc_id)
        except ApiException as e:
            if e.code == 404:
                try:
                    self._client.post_document(
                        db=self._db_name, document=Document(**record)
                    ).get_result()
                    logger.info("Saved record '%s' to Cloudant", doc_id)
                except Exception as post_err:
                    logger.error("Failed to save record '%s': %s", doc_id, post_err)
            else:
                logger.error("Error checking record '%s': %s", doc_id, e)

    def _get_record_qurey(self, qurey_selector):
        try:
            result = self._client.post_find(
                db=self._db_name,
                selector=qurey_selector,
            ).get_result()
            return result.get("docs", [])  # type: ignore
        except Exception as exc:
            logger.error("Cloudant read failed: %s", exc)
            return []

    def load_all_servers(self) -> List[Dict]:
        query = {"selector": {"type": {"$nin": ["tool"]}}}
        return self._get_record_qurey(query["selector"])

    def load_tools(self) -> List[Dict]:
        query = {"selector": {"type": "tool"}}
        return self._get_record_qurey(query["selector"])

    def add_server(self, config: Dict) -> None:
        self._add_record(config)

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

    def add_remove_tools(self, tools: list[str], server_id: str) -> None:
        try:
            # check if server config already present in db
            existing_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            tools = list(set(tools))
            existing_tools = existing_doc.get("remove_tools", [])
            tools_description = existing_doc.get("tools_description", {})

            # check the tool already present in remove tools list
            # if yes raise error, else update the remove tools list
            if existing_tools:
                logger.info(
                    f"""Remove tool list is already  
                        {existing_tools} present in cloudant for server_id {server_id}. 
                        So, update the remove tool list.
                        Response: {existing_doc}"""
                )

                duplicate_tool = check_duplicate_tool(existing_tools, tools)
                if duplicate_tool:
                    raise ToolDuplicateError(
                        f"Tool {duplicate_tool} is already removed"
                    )
                else:
                    existing_doc["remove_tools"].extend(tools)
            else:
                # if no remove tools list present add it
                existing_doc["remove_tools"] = tools

            # Remove tool descriptions if they exist
            if existing_doc["remove_tools"] and tools_description:
                for tool in existing_doc["remove_tools"]:
                    tools_description.pop(tool, None)

            response = self._client.post_document(
                db=self._db_name,
                document=existing_doc,
            ).get_result()

            logger.info(
                f"Saved remove tool list {existing_doc['remove_tools']} for server {server_id}. Response: {response}"
            )

        except ApiException as e:
            # Add server config to db with remove tools list, since it not exist
            if e.code == 404:
                logger.info(
                    f"Server {server_id} is not exist in database. Adding the server with remove tool list"
                )
                tool_doc = Document(_id=server_id, id=server_id, remove_tools=tools)
                response = self._client.post_document(
                    db=self._db_name,
                    document=tool_doc,
                ).get_result()
                logger.info(
                    f"Saved remove tool list {tools} for server {server_id}. Response: {response}"
                )
            else:
                logger.error(f"Failed to save remove tool list: {str(e)}")

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
                f"Updated tool description '{description}' for server '{server_id}'. Response: {response}"
            )

        except ApiException as e:
            if e.code == 404:
                # Document does not exist, create a new one
                logger.info(
                    f"Server '{server_id}' not found in database. Adding it with tool description."
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
                    f"Saved tool description '{description}' for server '{server_id}'. Response: {response}"
                )
            else:
                logger.error(f"Failed to save tool description: {e}")

    def get_document(self, server_id: str) -> Dict:
        # get the server config details of a single server
        server_doc = {}
        try:
            server_doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()

            logger.info(
                f"Retrive server '{server_id}' config details from cloudant. Response: {server_doc}"
            )
        except ApiException as e:
            logger.error(f"No server details found in  DB: {e}")
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
                f"Marked server '{server_id}' as deactivated. Response: {response}"
            )
        except ApiException as e:
            if e.code == 404:
                logger.error(f"Server '{server_id}' not found. Cannot deactivate.")
            else:
                logger.error(f"Error deactivating server '{server_id}': {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error while deactivating server '{server_id}': {e}"
            )

    def get_server_status(self, server_id: str) -> str:
        try:
            doc = self._client.get_document(
                db=self._db_name, doc_id=server_id
            ).get_result()
            status = doc.get("status", "active")  # default to 'active' if not set
            logger.info(f"Server '{server_id}' has status: {status}")
            return status
        except ApiException as e:
            if e.code == 404:
                logger.warning(f"Server '{server_id}' not found when fetching status.")
            else:
                logger.error(f"Error retrieving server status for '{server_id}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving status for '{server_id}': {e}")
        return "unknown"

    def add_tool(self, tool_config: Dict) -> None:
        tool_config["type"] = "tool"
        logger.info(f"Adding tool to database: {tool_config}")
        self._add_record(tool_config)
