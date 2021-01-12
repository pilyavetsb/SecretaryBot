from botbuilder.core import MessageFactory, UserState
from botbuilder.dialogs import (
    WaterfallDialog,
    DialogTurnResult,
    WaterfallStepContext,
    ComponentDialog,
)
from botbuilder.dialogs.prompts import PromptOptions, ChoicePrompt
from botbuilder.dialogs.choices.list_style import ListStyle
from botbuilder.dialogs.choices import Choice

from typing import List
from data_models import UserProfile
from dialogs.links_dialog import LinksDialog
from dialogs.stocks_dialog import StocksDialog
from dialogs.hk_dialog import HKDialog
from dialogs.pers_sel_dialog import PersonDialog
from dialogs.autoreply_dialog import AutoreplyDialog
from graph_client import GraphClient


class TopLevelDialog(ComponentDialog):
    """Dialog containing the branching logic

    Attributes:

        SELECTED_WAY(str): Key name to store this dialogs state info in the StepContext
        DONE_OPTION(str): word a user has to send to the bot to cancel the dialog at any stage
        client(GraphClient): MS Graph client instance associated with this dialog. Used to perform all calls to the Graph API
        user_state(UserState): user state storage object
        options_dict(dict): dictionary containg all the top-level branches' names along with the
        associated dialog and storage object name if applicable.
        ways_options(list): list of options as seen by the user
        initial_dialog_id: UID for this dialog
    """

    def __init__(self, user_state: UserState, dialog_id: str):
        """inits the TopLevelDialog instance.

        Args:
            user_state (UserState): user state storage object. Each user bot communicates with
            will have its own isolated storage object that can be used to persist information
            about the user across the entire conversation(s) with that user.
            dialog_id (str): a unique name identifying specific dialog.
        """
        super(TopLevelDialog, self).__init__(
            dialog_id or TopLevelDialog.__name__)

        self.SELECTED_WAY = "value-selectedWay"
        self.DONE_OPTION = "Завершить"

        self.client = GraphClient()
        self.user_state = user_state

        self.options_dict = {
            'bdg': ("Текущее состояние бюджета (WIP)", "", None),
            'hk': ("Отчеты Химкурьер", HKDialog.__name__, None),
            'links': ("Полезные ссылки", LinksDialog.__name__, None),
            'stocks': ("Котировки акций Tikkurila", StocksDialog.__name__, None),
            'person': ("Не знаю, к кому обратиться с вопросом", PersonDialog.__name__, None),
            'autoreply': ('Хочу поставить красивый автоответ', AutoreplyDialog.__name__, "UserProfile"),
        }

        self.ways_options = [self.options_dict[key][0]
                             for key in self.options_dict] + [self.DONE_OPTION]

        self.add_dialog(ChoicePrompt("top_level_choice"))
        self.add_dialog(LinksDialog(LinksDialog.__name__))
        self.add_dialog(StocksDialog(StocksDialog.__name__))
        self.add_dialog(HKDialog(self.client, HKDialog.__name__))
        self.add_dialog(PersonDialog(self.client, PersonDialog.__name__))
        self.add_dialog(
            AutoreplyDialog(
                self.user_state,
                self.client,
                AutoreplyDialog.__name__))

        self.add_dialog(
            WaterfallDialog(
                "top_level_WFDialog",
                [
                    self.selection_step,
                    self.branching_step,
                    self.end_step,
                ],
            )
        )

        self.initial_dialog_id = "top_level_WFDialog"

    async def _dialog_initializer(self, selection: str, step_context: WaterfallStepContext):
        """Starts a dialog corresponding to a string specified in the selection argument.

        Args:
            selection (str): Should be present in a options_dict attributtes, otherwise dialog can't be started
            step_context (WaterfallStepContext): the context for the current dialog turn
        """
        for key in self.options_dict:
            if self.options_dict[key][0] == selection:
                self.chosen = self.options_dict[key][2]
                return await step_context.begin_dialog(self.options_dict[key][1])

    async def selection_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts user to choose a branch (task the user want to perform via the bot).
        List of branches is contained in the ways_options attribute.
        Also checks if the user entered something that is not in the list and re-promts if that's the case.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        # Create an object in which to collect information within the dialog.
        selected: List[str] = step_context.options if step_context.options is not None else []
        step_context.values[self.SELECTED_WAY] = selected

        if len(selected) == 0:
            message = (
                f"Выберите из списка, какую информацию вы хотите получить"
                f"или выберите '{self.DONE_OPTION}', чтобы закончить работу")

        else:
            message = (f"Ваш выбор: {selected[0]}")

        # Ask the user to select the action they want to perform
        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            choices=self._to_choices(
                self.ways_options),
            retry_prompt=MessageFactory.text(
                "Пожалуйста выберите вариант из списка."),
            style=ListStyle.list_style,
        )
        return await step_context.prompt("top_level_choice", prompt_options)

    async def branching_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        """
        Initiates a dialog according to the user selection at the selection_step.
        If user chooses to terminate the session, this method immediately skips to the end_step.
        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of the initiated dialog or an empty result if user chooses to terminate the session
        """
        selection = step_context.result.value
        if selection == self.DONE_OPTION:
            # If we are terminating it is needed to pass an empty list
            await step_context.context.send_activity(
                MessageFactory.text("Штош")
            )
            return await step_context.next([])

        return await self._dialog_initializer(selection, step_context)

    async def end_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        """Thanks the user and exits the dialog passing the results to the MainDialog instance

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the end_dialog stack manipulation method.
        """
        await step_context.context.send_activity(
            MessageFactory.text(f"Спасибо что воспользовались ботом ФАО!")
        )

        return await step_context.end_dialog()

    def _to_choices(self, choices: List[str]) -> List[Choice]:
        """converts the list of strings to the list of instances of Choice objects
        Args:
            choices (List[str]): list of strings to be converted
        Returns:
            List[Choice]: list of Choice objects which can now be passed to a prompt method.
        """
        choice_list: List[Choice] = []
        for choice in choices:
            choice_list.append(Choice(value=choice))
        return choice_list
