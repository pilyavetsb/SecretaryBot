from typing import List
from botbuilder.dialogs import (
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
    ComponentDialog,
)
from botbuilder.dialogs.prompts import ChoicePrompt, PromptOptions
from botbuilder.dialogs.choices import Choice, FoundChoice
from botbuilder.core import MessageFactory


class LinksDialog(ComponentDialog):
    """
        A dialog designed to help a user with navigating the internal company documentation such as
        travel policy, cost accounts description, assets writedown instruction etc

        Attributes:
            SELECTED_LINK(str): Key name to store this dialogs state info in the StepContext
            DONE_OPTION(str): word a user has to send to the bot to cancel the dialog at any stage
            options_dict(dict): dictionary containing all the options presented for a user to choose from.
            initial_dialog_id:(str) UID for this dialog
    """

    def __init__(self, dialog_id: str = None):
        super().__init__(dialog_id or LinksDialog.__name__)

        self.SELECTED_LINK = "value-selectedLink"
        self.DONE_OPTION = "Завершить"

        self.options_dict = {
            "Вопрос по статьям затрат": "[Справка по статьям затрат](https://vk.com/feed)",
            "Вопрос по командировочным документам": "[Формы командировочных документов](https://www.google.com)",
            "Вопрос по процедуре списания": "[Инструкция по списанию ТМЦ](https://www.kinopoisk.ru)"}

        self.add_dialog(ChoicePrompt('links_options'))
        self.add_dialog(
            WaterfallDialog("LinksWF",
                            [
                                self.selection_step,
                                self.loop_step,
                                self.end_step,
                            ])
        )

        self.initial_dialog_id = "LinksWF"

    async def selection_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts the user to choose the topic they want to get they want to get the docs about

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        selected: List[str] = step_context.options if step_context.options is not None else []
        step_context.values[self.SELECTED_LINK] = selected

        if len(selected) == 0:
            message = (
                f"Какой у вас вопрос? Если вы хотите завершить работу с ботом, выберите '{self.DONE_OPTION}'."
            )
        else:
            message = (
                f"Ваш выбор: {selected[0]}. Вы можете выбрать еще один вопрос."
                f"Чтобы подтвердить выбор, выберите '{self.DONE_OPTION}'."
            )

        options = self.options_dict.copy()
        if len(selected) > 0:
            for key in selected:
                if key in options:
                    del options[key]

        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            retry_prompt=MessageFactory.text(
                "Пожалуйста выберите вариант из списка."),
            choices=self._to_choices(options),
        )

        return await step_context.prompt("links_options", prompt_options)

    async def loop_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts the user to make an additional selection or to finish the process

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: the result of calling the selected stack manipulation method
        """
        selected: List[str] = step_context.values[self.SELECTED_LINK]
        choice: FoundChoice = step_context.result
        done = choice.value == self.DONE_OPTION

        if done and len(selected) == 0:
            return await step_context.end_dialog()

        if not done:
            selected.append(choice.value)

        if done or len(selected) == 3:
            return await step_context.next(selected)

        return await step_context.replace_dialog("LinksWF", selected)

    async def end_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Sends the requested links to the user

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the end_dialog stack manipulation method.
        """
        asked_links = step_context.result

        message = ("Ссылки по вашему запросу:\n\n" +
                   "  \n".join([self.options_dict[key] for key in asked_links]))

        await step_context.context.send_activity(
            MessageFactory.text(message)
        )

        return await step_context.end_dialog()

    def _to_choices(self, choices: dict) -> List[Choice]:
        """Converts the list of strings to the list of instances of Choice objects
            Args:
                choices (List[str]): list of strings to be converted
            Returns:
                List[Choice]: list of Choice objects which can now be passed to a prompt method.
        """
        choice_list: List[Choice] = []
        for key in choices:
            choice_list.append(Choice(value=key))
        choice_list.append(Choice(self.DONE_OPTION))
        return choice_list
