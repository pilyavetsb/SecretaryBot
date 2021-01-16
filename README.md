# Finance and Analytics Department Helper Bot
This is a Microsoft Teams bot aiming to automate some of my tedious tasks while improving internal customers' experience at the same time.
Also a nice exercise in async python and Microsoft Graph API. My Magnum Opus atm😁

## What it does
- constructs an autoreply message, sets it active and marks the calendar as "out of office" according to user inputs. Autoreply message can be both in English and Russian (at the same time!)
- provides download links for the market size/share reports accroding to queries specified by users
- guides users through a decision tree to help them identify the right person to contact with their issue. Returns not just a name, but an Adaptive card with a manager, current status and a photo.
- provides users with links to the instructions related to the most popular tasks, such as travel requisitons etc
- sends a nicely formatted card with Tikkurila's stock price


## Testing the bot using Bot Framework Emulator
[Microsoft Bot Framework Emulator](https://github.com/microsoft/botframework-emulator) is a desktop application that allows bot developers to test and debug their bots on localhost or running remotely through a tunnel.

- Install the Bot Framework emulator from [here](https://github.com/Microsoft/BotFramework-Emulator/releases)

### Connect to bot using Bot Framework Emulator
- Launch Bot Framework Emulator
- File -> Open Bot
- Paste this URL in the emulator window - http://localhost:3978/api/messages

# Further reading

- [Microsoft Graph Documentation](https://docs.microsoft.com/en-us/graph/overview)
- [Bot Framework Documentation](https://docs.botframework.com)
- [Bot Basics](https://docs.microsoft.com/azure/bot-service/bot-builder-basics?view=azure-bot-service-4.0)
- [Dialogs](https://docs.microsoft.com/azure/bot-service/bot-builder-concept-dialog?view=azure-bot-service-4.0)
- [Azure Bot Service Introduction](https://docs.microsoft.com/azure/bot-service/bot-service-overview-introduction?view=azure-bot-service-4.0)
- [Azure Bot Service Documentation](https://docs.microsoft.com/azure/bot-service/?view=azure-bot-service-4.0)
- [Azure CLI](https://docs.microsoft.com/cli/azure/?view=azure-cli-latest)
- [Azure Portal](https://portal.azure.com)
