from botbuilder.core import ActivityHandler, ConversationState, UserState, TurnContext, MessageFactory
from botbuilder.dialogs import Dialog
from helpers.dialog_helper import DialogHelper
from typing import List
from botbuilder.schema import ChannelAccount, ActivityTypes
import json


class DialogBot(ActivityHandler):
    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        dialog: Dialog,
    ):
        if conversation_state is None:
            raise Exception(
                "[DialogBot]: Missing parameter. conversation_state is required"
            )
        if user_state is None:
            raise Exception(
                "[DialogBot]: Missing parameter. user_state is required")
        if dialog is None:
            raise Exception(
                "[DialogBot]: Missing parameter. dialog is required")

        self.conversation_state = conversation_state
        self.user_state = user_state
        self.dialog = dialog

    async def on_turn(self, turn_context: TurnContext):
        # transform adaptive card postback to text to pass textprompt validation
        if turn_context.activity.type == ActivityTypes.message:
            if turn_context.activity.text is None and turn_context.activity.value is not None:
                turn_context.activity.text = json.dumps(
                    turn_context.activity.value)
        # call original method
        await super().on_turn(turn_context)

        # Save any state changes that might have occurred during the turn.
        await self.conversation_state.save_changes(turn_context, False)
        await self.user_state.save_changes(turn_context, False)

    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            # Greet anyone that was not the target (recipient) of this message.
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text(
                        f"Добро пожаловать в первую версию бота отдела ФАО, {member.name}. Пока что, я ничего толком не умею, но "
                        f"это мы скоро исправим. Отправьте мне любой текст, чтобы начать работу"
                    )
                )

    async def on_message_activity(self, turn_context: TurnContext):
        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )
