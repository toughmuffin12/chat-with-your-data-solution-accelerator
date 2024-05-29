import os
import azure.functions as func
import logging
import json
import uuid

from utilities.helpers.env_helper import EnvHelper
from utilities.helpers.orchestrator_helper import Orchestrator
from utilities.helpers.config.config_helper import ConfigHelper
from utilities.helpers.azure_cosmos_helper import CosmosConversationClient


bp_get_conversation_response = func.Blueprint()
logger = logging.getLogger(__name__)
logger.setLevel(level=os.environ.get("LOGLEVEL", "INFO").upper())


@bp_get_conversation_response.route(route="GetConversationResponse")
async def get_conversation_response(req: func.HttpRequest) -> func.HttpResponse:
    return await do_get_conversation_response(req)


async def do_get_conversation_response(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Python HTTP trigger function processed a request.")

    message_orchestrator = Orchestrator()
    env_helper: EnvHelper = EnvHelper()

    try:
        req_body = req.get_json()
        user_message = req_body["messages"][-1]["content"]
        conversation_id = req_body["conversation_id"]
        if conversation_id == "" or not conversation_id:
            conversation_id = str(uuid.uuid4())
        user_id = req_body["user_id"]
        message_id = req_body["id"]
        feedback = req_body.get("feedback", None)
        user_assistant_messages = list(
            filter(
                lambda x: x["role"] in ("user", "assistant"), req_body["messages"][0:-1]
            )
        )

        # Message Feedback
        if feedback:
            cosmos_client = CosmosConversationClient()
            cosmos_client.update_message_feedback(
                user_id=user_id, message_id=message_id, feedback=feedback
            )
            print("Feedback updated")
            response_obj = {
                "id": message_id,
                "model": env_helper.AZURE_OPENAI_MODEL,
                "created": "response.created",
                "object": "response.object",
                "choices": [],
            }
            return func.HttpResponse(json.dumps(response_obj), status_code=200)

        chat_history = []
        for i, k in enumerate(user_assistant_messages):
            if i % 2 == 0:
                chat_history.append(
                    (
                        user_assistant_messages[i]["content"],
                        user_assistant_messages[i + 1]["content"],
                    )
                )

        messages = await message_orchestrator.handle_message(
            id=message_id,
            user_id=user_id,
            user_message=user_message,
            chat_history=chat_history,
            conversation_id=conversation_id,
            # feedback=feedback,
            orchestrator=ConfigHelper.get_active_config_or_default().orchestrator,
        )
        if messages is not None:
            response_id = messages[-1]["id"]
        else:
            response_id = None
        response_obj = {
            "id": response_id,
            "model": env_helper.AZURE_OPENAI_MODEL,
            "created": "response.created",
            "object": "response.object",
            "choices": [{"messages": messages}],
        }

        return func.HttpResponse(json.dumps(response_obj), status_code=200)

    except Exception as e:
        logger.exception("Exception in /api/GetConversationResponse")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)
