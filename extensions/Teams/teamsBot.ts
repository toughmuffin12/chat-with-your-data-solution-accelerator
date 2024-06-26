import {
  ConversationState,
  MemoryStorage,
  TeamsActivityHandler,
  TurnContext,
  ActivityTypes,
  MessageFactory
} from "botbuilder";
import { CardFactory } from 'botbuilder';
import config from "./config";
import {
  ChatMessage,
  ChatResponse,
  ToolMessageContent,
  Citation,
} from "./model";

import { cwydResponseBuilder, negativeFeedback, positiveFeedback } from "./cards/cardBuilder";
import {v4 as uuidv4} from 'uuid';

const EMPTY_RESPONSE = "Sorry, I do not have an answer. Please try again.";
const SAMPLE_USER_ID = "00000000-0000-0000-0000-000000000000"

export class TeamsBot extends TeamsActivityHandler {
  constructor() {
    super();
    let newActivity;
    let assistantAnswer = "";
    let activityUpdated = true;
    var txt;
    var feedbackCategory;
    var feedbackType;
    let assistantMessageId = "";

    const memoryStorage = new MemoryStorage();
    const conversationState = new ConversationState(memoryStorage);
    const conversationData = conversationState.createProperty('ConversationData');



    this.onMessage(async (context, next) => {
      console.log("Running with Message Activity.");

      const removedMentionText = TurnContext.removeRecipientMention(
        context.activity
      );

      const data = await conversationData.get(context, {});

      if (!data.conversationId || data.conversationId === "personal-chat-id") {
        data.conversationId = uuidv4();

        conversationState.saveChanges(context);
      }
      let actionData = context.activity.value;
      
      if (actionData && actionData.type === "PositiveFeedback") {
        // Handle positive feedback here
        await context.sendActivity(`I am glad I could be of assistance. In a few words what was good about the response?`);
        feedbackType = actionData.type;
        newActivity = MessageFactory.attachment(positiveFeedback());
        await context.sendActivity(newActivity);
        return;
      }

      if (actionData && actionData.type === "NegativeFeedback") {
        // Handle negative feedback here
        await context.sendActivity(`I am sorry I could not help you, could be improved about this response?`);
        feedbackType = actionData.type;
        newActivity = MessageFactory.attachment(negativeFeedback());
        await context.sendActivity(newActivity);
        return;
      }

      if(!context.activity.value) {
        txt = removedMentionText.toLowerCase().replace(/\n|\r/g, "").trim();
      }
      
      try {
        // const reply = await context.sendActivity("Searching...");

        // console.log("context.activity.from.id", context.activity.from.id);
        const typingReply = await context.sendActivities([
          { type: ActivityTypes.Typing },
        ]);

        // Create a new activity with the user's message as a reply.
        const answers: ChatMessage[] = [];
        const userMessage: ChatMessage = {
          role: "user",
          content: txt,
        };
      
        // Call the Azure Function to get the response from Azure OpenAI on your Data
        let result = {} as ChatResponse;
        // Feedback handler
        if (context.activity.value) {
          let user_id = context.activity.from.id;
          feedbackCategory = context.activity.value.type;
          if (context.activity.value && context.activity.value.userInput) {
            // Handle the user's inputed feedback
            var feedbackText = context.activity.value.userInput;
            console.log("feedbackText", feedbackText)
            console.log("feedbackCategory", feedbackCategory)
            const assistantMessage: ChatMessage = {
              role: "assistant",
              content: assistantAnswer,
            };
            await fetch(config.azureFunctionUrl, {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({
                id: assistantMessageId,
                user_id: user_id,
                messages: [assistantMessage],
                feedback: {
                  "positive/negative": feedbackType,
                  "catagory": 'Other',
                  "text_input": feedbackText,
                },
                conversation_id: data.conversationId
              })
            });
            await context.sendActivity(`Thank you for your feedback. A human will review it shortly.`);
            return;
          } 
          if (context.activity.value.type === 'Other') {
            const card = {
              type: 'AdaptiveCard',
              body: [
                {
                  type: 'TextBlock',
                  text: 'Please provide your feedback.',
                  wrap: true,
                },
                {
                  type: 'Input.Text',
                  id: 'userInput',
                  placeholder: 'Type your message here',
                },
                {
                  type: 'ActionSet',
                  actions: [
                    {
                      type: 'Action.Submit',
                      title: 'Submit',
                    },
                  ],
                },
              ],
              $schema: 'http://adaptivecards.io/schemas/adaptive-card.json',
              version: '1.2',
            };
            
            await context.sendActivity({ attachments: [CardFactory.adaptiveCard(card)] });
          } else {
            const assistantMessage: ChatMessage = {
              role: "assistant",
              content: assistantAnswer,
            };

            await fetch(config.azureFunctionUrl, {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({
                id: assistantMessageId,
                user_id: user_id,
                messages: [assistantMessage],
                feedback: {
                  "positive/negative": feedbackType,
                  "catagory": feedbackCategory,
                  "text_input": "",
                },
                conversation_id: data.conversationId
              })
            });
            await context.sendActivity(`Thank you for your feedback. A human will review it shortly.`);
            return;
          }
        }

        try {
          let message_id = uuidv4().toString();
          const response = await fetch(config.azureFunctionUrl, {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              id: message_id,
              user_id: context.activity.from.id,
              messages: [userMessage],
              conversation_id: data.conversationId
            })
          });

          // Parse the response
          if (response?.body) {
            const reader = response.body.getReader();
            let runningText = "";

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              var text = new TextDecoder("utf-8").decode(value);

              const objects = text.split("\n");
              objects.forEach((obj) => {
                try {
                  runningText += obj;
                  result = JSON.parse(runningText);
                  assistantMessageId = result.id;
                  if (result.error) {
                    answers.push(userMessage, {
                      role: "error",
                      content:
                        "ERROR: " + result.error + " | " + EMPTY_RESPONSE,
                    });
                  } else {
                    answers.push(userMessage, ...result.choices[0].messages);

                  }
                  runningText = "";
                } catch (e) {
                  const errorMessage: ChatMessage = {
                    role: "error",
                    content: e.message,
                  };
                  answers.push(errorMessage);
                }
              });
            }
          }
        } catch (e) {
          console.error(e);
          const errorMessage: ChatMessage = {
            role: "error",
            content: e.message,
          };
          answers.push(errorMessage);
        }

        

        // Parse the citations from the tool message
        const parseCitationFromMessage = (message: ChatMessage) => {
          if (message.role === "tool") {
            try {
              const toolMessage = JSON.parse(
                message.content
              ) as ToolMessageContent;
              return toolMessage.citations;
            } catch {
              return [];
            }
          }
          return [];
        };

        // Generate the response for the user
        answers.map((answer, index) => {
          if (answer.role === "assistant") {
            assistantAnswer = answer.content;
            if (assistantAnswer.startsWith("[doc")) {
              assistantAnswer = EMPTY_RESPONSE;
              newActivity = MessageFactory.text(assistantAnswer);
            } else {
              const citations = parseCitationFromMessage(answers[index - 1]) as Citation[];
              if (citations.length === 0) {
                newActivity = MessageFactory.attachment(cwydResponseBuilder(citations, assistantAnswer));
                // newActivity.id = Math.floor(100000000 + Math.random() * 900000000);;
              } if (context.activity.text == "imageClicked") {
                newActivity = MessageFactory.attachment(negativeFeedback());

              } else {
                // console.log("context.activity.text", context.activity.text)
                newActivity = MessageFactory.attachment(cwydResponseBuilder(citations, assistantAnswer));
                activityUpdated = false;
              }
            }
          } else if (answer.role === "error") {
            newActivity = MessageFactory.text(
              "Sorry, an error occurred. Try waiting a few minutes. If the issue persists, contact your system administrator. Error: " +
              answer.content
            );
            // newActivity.id = Math.floor(100000000 + Math.random() * 900000000);;
          }

        });
        newActivity.typing = false; // Stop the ellipses visual indicator

        if (activityUpdated) {
          // newActivity.attachments = MessageFactory.attachment(CardFactory.adaptiveCard(feedbackCard));
          // console.log("newActivity.attachments", newActivity.attachments)
          if(context.activity.value == undefined) {
            await context.sendActivity(newActivity);
          }
          // const newActivityWithCard = MessageFactory.attachment(CardFactory.adaptiveCard(feedbackCard));
          // await context.sendActivity(newActivityWithCard);
        } else {
            // if (reply && reply.id) {
            //   try {
            //     await context.deleteActivity(reply.id);
            //   } catch (error) {
            //     console.log('Error in deleting message', error);
            //   }
            // }
            // newActivity.attachment = MessageFactory.attachment(CardFactory.adaptiveCard(feedbackCard));
            // console.log("newActivity.attachments", newActivity.attachments)
            if(context.activity.value == undefined) {
              await context.sendActivity(newActivity);
            }

            // const newActivityWithCard = MessageFactory.attachment(CardFactory.adaptiveCard(feedbackCard));
            // await context.sendActivity(newActivityWithCard);
        }

      } catch (error) {

        console.log('Error in onMessage:', error);
      } finally {
      }

      // By calling next() you ensure that the next BotHandler is run.
      await next();
    });

    this.onMembersAdded(async (context, next) => {
      const membersAdded = context.activity.membersAdded;
      for (let cnt = 0; cnt < membersAdded.length; cnt++) {
        if (membersAdded[cnt].id) {
          await context.sendActivity(
            `Greetings! I am the Chat with your data bot. How can I help you today?`
          );
          break;
        }
      }
      await next();
    });
  }
}
