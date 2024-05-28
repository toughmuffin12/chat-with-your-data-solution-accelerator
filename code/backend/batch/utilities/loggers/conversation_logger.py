from ..helpers.azure_cosmos_helper import CosmosConversationClient

from datetime import datetime
import json


class ConversationLogger:
    def __init__(self):
        # self.logger = AzureSearchHelper().get_conversation_logger()
        # self.logger = CosmosConversationClient(
        #     cosmosdb_endpoint=EnvHelper().AZURE_COSMOS_DB_ENDPOINT,
        #     credential=EnvHelper().AZURE_COSMOS_DB_KEY,
        #     database_name=EnvHelper().AZURE_COSMOS_DB_NAME,
        #     container_name=EnvHelper().AZURE_COSMOS_DB_CONTAINER_NAME,
        #     enable_message_feedback=True
        # )
        self.logger = CosmosConversationClient()

    def log(self, messages: list):
        self.log_user_message(messages)
        self.log_assistant_message(messages)

    def log_user_message(self, messages: dict):
        text = ""
        metadata = {}
        for message in messages:
            if message["role"] == "user":
                metadata["id"] = message["id"]
                metadata["type"] = message["role"]
                metadata["user_id"] = message["user_id"]
                metadata["conversation_id"] = message.get("conversation_id")
                metadata["created_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                metadata["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                text = message["content"]
        # self.logger.add_texts(texts=[text], metadatas=[metadata])

        self.logger.create_message(
            uuid=metadata["id"],
            conversation_id=metadata["conversation_id"],
            user_id=metadata["user_id"],
            input_message={"role": "user", "content": text},
            metadata=metadata,
        )

    def log_assistant_message(self, messages: dict):
        text = ""
        metadata = {}
        try:
            metadata["conversation_id"] = set(
                filter(None, [message.get("conversation_id") for message in messages])
            ).pop()
            metadata["user_id"] = set(
                filter(None, [message.get("user_id") for message in messages])
            ).pop()
        except KeyError:
            metadata["conversation_id"] = None
            metadata["user_id"] = None
        for message in messages:
            if message["role"] == "assistant":
                metadata["id"] = message["id"]
                metadata["type"] = message["role"]
                metadata["created_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                metadata["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                text = message["content"]
                self.logger.create_message(
                    uuid=metadata["id"],
                    conversation_id=metadata["conversation_id"],
                    user_id=metadata["user_id"],
                    input_message={"role": "assistant", "content": text},
                    metadata=metadata,
                )
            elif message["role"] == "tool":
                metadata["sources"] = [
                    source["id"]
                    for source in json.loads(message["content"]).get("citations", [])
                ]
                # print("TOOL conv_ID", conversation_id)
                self.logger.create_message(
                    uuid=message["id"],
                    conversation_id=metadata["conversation_id"],
                    user_id=metadata["user_id"],
                    input_message={"role": "tool", "content": text},
                    metadata=metadata,
                )
        # self.logger.add_texts(texts=[text], metadatas=[metadata])
