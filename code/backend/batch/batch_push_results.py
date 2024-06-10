import os
import logging
import json
from urllib.parse import urlparse
import azure.functions as func
import requests

from utilities.helpers.azure_blob_storage_client import AzureBlobStorageClient
from utilities.helpers.env_helper import EnvHelper
from utilities.helpers.embedders.embedder_factory import EmbedderFactory
from utilities.search.search import Search

bp_batch_push_results = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


def _get_file_name_from_message(message_body) -> str:
    return message_body.get(
        "filename",
        "/".join(
            urlparse(message_body.get("data", {}).get("url", "")).path.split("/")[2:]
        ),
    )


@bp_batch_push_results.queue_trigger(
    arg_name="msg", queue_name="doc-processing", connection="AzureWebJobsStorage"
)
def batch_push_results(msg: func.QueueMessage) -> None:
    message_body = json.loads(msg.get_body().decode("utf-8"))
    logger.debug("Process Document Event queue function triggered: %s", message_body)

    event_type = message_body.get("eventType", "")
    # We handle "" in this scenario for backwards compatibility
    # This function is primarily triggered by an Event Grid queue message from the blob storage
    # However, it can also be triggered using a legacy schema from BatchStartProcessing
    if event_type in ("", "Microsoft.Storage.BlobCreated"):
        _process_document_created_event(message_body)

    elif event_type == "Microsoft.Storage.BlobDeleted":
        _process_document_deleted_event(message_body)

    else:
        raise NotImplementedError(f"Unknown event type received: {event_type}")


def _process_document_created_event(message_body) -> None:
    env_helper: EnvHelper = EnvHelper()
    supported_file_types = ["pdf", "txt", "jpeg", "jpg", "png", "docx", "md", "html"]
    blob_client = AzureBlobStorageClient()
    file_name = _get_file_name_from_message(message_body)
    file_extension = file_name.split(".")[-1]
    if file_extension not in supported_file_types:
        description_string = f"{file_name} was not processed as it is not a supported file type. \n Supported file types are: {supported_file_types}"
        jira_url = "https://automation.atlassian.com/pro/hooks/80b5ac1b40e7e9fb1656bb536aefadd80c1f178d"
        headers = {"Content-Type": "application/json"}
        body = {
            "data": {
                "project": "KX",
                "summary": "Unsupported File Type Uploaded",
                "description": description_string,
                "issuetype": "Task",
            }
        }
        requests.post(jira_url, headers=headers, json=body)
        print(
            "{file_name} was not processed as {file_extension} is not a supported file exstenstion - A JIRA ticket has been created."
        )
        return

    file_sas = blob_client.get_blob_sas(file_name)

    embedder = EmbedderFactory.create(env_helper)
    embedder.embed_file(file_sas, file_name)


def _process_document_deleted_event(message_body) -> None:
    env_helper: EnvHelper = EnvHelper()
    search_handler = Search.get_search_handler(env_helper)

    blob_url = message_body.get("data", {}).get("url", "")
    search_handler.delete_by_source(f"{blob_url}_SAS_TOKEN_PLACEHOLDER_")
