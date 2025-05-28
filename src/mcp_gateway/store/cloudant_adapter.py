# cloudant_adapter.py
from typing import List, Dict
from ibmcloudant import CloudantV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core.api_exception import ApiException
from ibmcloudant.cloudant_v1 import Document
from mcp_gateway.utils import LoggerFactory
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
    
    def load_all_servers(self) -> List[Dict]:
        try:
            result = self._client.post_all_docs(db=self._db_name, include_docs=True).get_result()
            return [row["doc"] for row in result.get("rows", []) if "doc" in row]
        except Exception as exc:
            logger.error("Cloudant read failed: %s", exc)
            return []
    
    def add_server(self, config: Dict) -> None:
        doc_id = config["id"]
        try:
            self._client.get_document(db=self._db_name, doc_id=doc_id).get_result()
            logger.info("Server '%s' already exists in Cloudant. Skipping add.", doc_id)
        except ApiException as e:
            if e.code == 404:
                try:
                    self._client.post_document(db=self._db_name, document=Document(**config)).get_result()
                    logger.info("Saved server '%s' to Cloudant", doc_id)
                except Exception as post_err:
                    logger.error("Failed to save server '%s': %s", doc_id, post_err)
            else:
                logger.error("Error checking server '%s': %s", doc_id, e)
    
    def remove_server(self, server_id: str) -> None:
        try:
            result = self._client.post_find(
                db=self._db_name,
                selector={"id": {"$eq": server_id}}
            ).get_result()

            for doc in result.get("docs", []):
                self._client.delete_document(db=self._db_name, doc_id=doc["_id"], rev=doc["_rev"])
                logger.info("Deleted server '%s' from Cloudant", server_id)
        except Exception as exc:
            logger.error("Cloudant operation failed: %s", exc)