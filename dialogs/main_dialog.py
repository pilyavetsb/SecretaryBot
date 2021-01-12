from botbuilder.dialogs import (
    ComponentDialog,
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
)
from botbuilder.core import MessageFactory, UserState

from data_models import UserProfile
from dialogs.top_level_dialog import TopLevelDialog


class MainDialog(ComponentDialog):
    """Class representing the main dialog, from which all the branches span.
    Inherits from ComponentsDialog class
    """

    def __init__(self, user_state: UserState):
        """inits the MainDialog instance, creates the TopLevelDialog from which all the branching occurs

        Args:
            user_state (UserState): user state storage object. Each user bot communicates with
            will have its own isolated storage object that can be used to persist information
            about the user across the entire conversation(s) with that user.
        """
        super(MainDialog, self).__init__(MainDialog.__name__)

        self.user_state = user_state

        self.add_dialog(
            TopLevelDialog(
                dialog_id=TopLevelDialog.__name__,
                user_state=self.user_state))
        self.add_dialog(
            WaterfallDialog("WFDialog", [self.initial_step, self.final_step])
        )

        self.initial_dialog_id = "WFDialog"

    async def initial_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        """First step of the Main Dialog. Serves the sole purpose of starting the Top Level Dialog.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the begin_dialog stack manipulation method.
        """
        return await step_context.begin_dialog(TopLevelDialog.__name__)

    async def final_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Receives the results of a conversation from the top level dialog and ends the dialog.
        Prompts the user to send any message to restart this dialog.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the end_dialog stack manipulation method.
        """
        # TODO store the UserProfile (gonna need the storage)
        #user_info: UserProfile = step_context.result

        message = f"Чтобы сделать новый запрос, отправьте мне любое сообщение"

        await step_context.context.send_activity(MessageFactory.text(message))

        # TODO store the UserProfile (gonna need the storage)
        #accessor = self.user_state.create_property("UserProfile")
        # await accessor.set(step_context.context, user_info)

        return await step_context.end_dialog()
