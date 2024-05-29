import logging
from typing import List, Optional
from abc import ABC, abstractmethod
from ..loggers.conversation_logger import ConversationLogger
from ..helpers.config.config_helper import ConfigHelper
from ..parser.output_parser_tool import OutputParserTool
from ..tools.content_safety_checker import ContentSafetyChecker

logger = logging.getLogger(__name__)


class OrchestratorBase(ABC):
    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigHelper.get_active_config_or_default()
        # self.id = ""
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}
        # logger.debug(f"New message id: {self.id} with tokens {self.tokens}")
        self.conversation_logger: ConversationLogger = ConversationLogger()
        self.content_safety_checker = ContentSafetyChecker()
        self.output_parser = OutputParserTool()

    def log_tokens(self, prompt_tokens, completion_tokens):
        self.tokens["prompt"] += prompt_tokens
        self.tokens["completion"] += completion_tokens
        self.tokens["total"] += prompt_tokens + completion_tokens

    @abstractmethod
    async def orchestrate(
        self,
        id: str,
        user_id: str,
        user_message: str,
        chat_history: List[dict],
        conversation_id: str,
        # feedback: Optional[dict],
        **kwargs: dict,
    ) -> list[dict]:
        pass

    def call_content_safety_input(self, user_message: str):
        logger.debug("Calling content safety with question")
        filtered_user_message = (
            self.content_safety_checker.validate_input_and_replace_if_harmful(
                user_message
            )
        )
        if user_message != filtered_user_message:
            logger.warning("Content safety detected harmful content in question")
            messages = self.output_parser.parse(
                question=user_message, answer=filtered_user_message
            )
            return messages

        return None

    def call_content_safety_output(self, user_message: str, answer: str):
        logger.debug("Calling content safety with answer")
        filtered_answer = (
            self.content_safety_checker.validate_output_and_replace_if_harmful(answer)
        )
        if answer != filtered_answer:
            logger.warning("Content safety detected harmful content in answer")
            messages = self.output_parser.parse(
                question=user_message, answer=filtered_answer
            )
            return messages

        return None

    async def handle_message(
        self,
        id: str,
        user_id: str,
        user_message: str,
        chat_history: List[dict],
        conversation_id: str,
        # feedback: Optional[dict],
        **kwargs: Optional[dict],
    ) -> dict:
        # if feedback:
        #     cosmos_client = CosmosConversationClient()

        #     cosmos_client.update_message_feedback(
        #         user_id=user_id,
        #         message_id=id,
        #         feedback=feedback
        #     )
        #     return

        result = await self.orchestrate(
            id, user_id, user_message, chat_history, conversation_id, **kwargs
        )

        if self.config.logging.log_tokens:
            custom_dimensions = {
                "id": id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "prompt_tokens": self.tokens["prompt"],
                "completion_tokens": self.tokens["completion"],
                "total_tokens": self.tokens["total"],
            }
            logger.info("Token Consumption", extra=custom_dimensions)
        if self.config.logging.log_user_interactions:
            self.conversation_logger.log(
                messages=[
                    {
                        "id": id,
                        "user_id": user_id,
                        "role": "user",
                        "content": user_message,
                        "conversation_id": conversation_id,
                    }
                ]
                + result
            )
        return result
