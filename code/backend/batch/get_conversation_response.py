import os
import azure.functions as func
import requests
import logging
import json
import datetime

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
        print("REQ BODY", req_body)
        user_message = req_body["messages"][-1]["content"]
        conversation_id = req_body["conversation_id"]
        if conversation_id == "" or not conversation_id:
            conversation_id = str(uuid.uuid4())
        user_id = req_body["user_id"]
        message_id = req_body["id"]
        feedback = req_body.get("feedback", None)
        chat_history = req_body.get("chatHistory", [])
        if len(chat_history) == 10:
            chat_history.pop(0)
        print("chat_history", chat_history)
        print("REQ BODY[messages]", req_body)
        # user_assistant_messages = list(
        #     filter(lambda x: x["role"] in ("user", "assistant"), req_body["messages"])
        # )
        # Message Feedback
        if feedback:
            cosmos_client = CosmosConversationClient()
            cosmos_client.update_message_feedback(
                user_id=user_id, message_id=message_id, feedback=feedback
            )
            try:
                if feedback["positive/negative"] == "NegativeFeedback":
                    if feedback["catagory"] == "Other":
                        description_string = f"{feedback['catagory']} - {feedback['text_input']}\nUser Message Content: {req_body['messages'][0]['content']}\nAssistant Message Content: {req_body['messages'][-1]['content']}\nConversation ID: {conversation_id}\nTimestamp: {datetime.datetime.now()}"
                    else:
                        description_string = f"{feedback['catagory']}\nUser Message Content: {req_body['messages'][0]['content']}\nAssistant Message Content: {req_body['messages'][-1]['content']}\nConversation ID: {conversation_id}\nTimestamp: {datetime.datetime.now()}"
                    jira_url = "https://automation.atlassian.com/pro/hooks/80b5ac1b40e7e9fb1656bb536aefadd80c1f178d"
                    headers = {"Content-Type": "application/json"}
                    body = {
                        "data": {
                            "project": "KX",
                            "summary": "Negative Feedback Recieved",
                            "description": description_string,
                            "issuetype": "Task",
                        }
                    }
                    requests.post(jira_url, headers=headers, json=body)
                print("Feedback updated")
            except requests.exceptions.HTTPError as err:
                print(
                    f"HTTP request failed with status {err.response.status_code}, reason: {err.response.text}"
                )
            response_obj = {
                "id": message_id,
                "model": env_helper.AZURE_OPENAI_MODEL,
                "created": "response.created",
                "object": "response.object",
                "choices": [],
            }
            return func.HttpResponse(json.dumps(response_obj), status_code=200)

        # if len(user_assistant_messages) == 1:
        #     # Add the single message as a dictionary to chat_history
        #     chat_history.append(
        #         {"content": user_assistant_messages[0]["content"], "role": "user"}
        #     )  # Adjust "role" as necessary
        # else:
        #     # For more than one message, attempt to pair them and add as dictionaries
        #     for i in range(len(user_assistant_messages) - 1):
        #         if i % 2 == 0:
        #             chat_history.append(
        #                 {
        #                     "content": user_assistant_messages[i]["content"],
        #                     "role": "user",
        #                 }
        #             )  # Example role
        #             chat_history.append(
        #                 {
        #                     "content": user_assistant_messages[i + 1]["content"],
        #                     "role": "assistant",
        #                 }
        #             )  # Adjust roles as necessary

        messages = await message_orchestrator.handle_message(
            id=message_id,
            user_id=user_id,
            user_message=user_message,
            chat_history=chat_history,
            conversation_id=conversation_id,
            # feedback=feedback,
            orchestrator=ConfigHelper.get_active_config_or_default().orchestrator,
        )
        # chat_history.append(
        #     {"role": "assistant", "content": messages[-1]["content"]}
        # )
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
            "chat_history": chat_history,
        }

        return func.HttpResponse(json.dumps(response_obj), status_code=200)

    except Exception as e:
        logger.exception("Exception in /api/GetConversationResponse")
        jira_url = "https://automation.atlassian.com/pro/hooks/80b5ac1b40e7e9fb1656bb536aefadd80c1f178d"
        headers = {"Content-Type": "application/json"}
        body = {
            "data": {
                "project": "KX",
                "summary": "Error in Chatbot API",
                "description": f"Error: {str(e)}\nMessage Content: {req_body['messages'][-1]['content']}\nConversation ID: {conversation_id}\nTimestamp: {datetime.datetime.now()}",
                "issuetype": "Task",
            }
        }
        requests.post(jira_url, headers=headers, json=body)
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500)
