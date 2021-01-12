from graph_client import GraphClient
from typing import List
from botbuilder.dialogs import (
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
    ComponentDialog,
)
from botbuilder.dialogs.prompts import ChoicePrompt, PromptOptions, TextPrompt, PromptValidatorContext
from botbuilder.dialogs.choices import Choice
from botbuilder.dialogs.choices.list_style import ListStyle
from botbuilder.core import MessageFactory
from graph_client import GraphClient
import re


class HKDialog(ComponentDialog):
    """Dialog designed to provide the users with ChemCourier reports. User chooses a channel (deco or industry) and a set of dates
    then the bot sends a list of download links to the user.

        Attributes:
            DONE_OPTION(str): word a user has to send to the bot to cancel the dialog at any stage
            LAST_OPTION(str): word a user has to send to the bot to get the latest available report
            SELECTED_CHANNEL(str): Key name to store this dialogs state info in the StepContext
            DRIVE_ID(str): id of the drive resource where the report files reside
            SITE_ID(str): id of the Sharepoint site where the report files reside
            client(GraphClient): MS Graph client instance associated with this dialog. Used to perform all calls to the Graph API
            options_list(dict): dictionary containing the names of all top level branches of this dialog
            initial_dialog_id(str): UID for this dialog

    """

    def __init__(self, client: GraphClient, dialog_id: str):
        """inits a HKDialog instance

        Args:
            client (GraphClient): MS Graph client instance associated with this dialog. Used to perform all calls to the Graph API
            dialog_id (str): a unique name identifying specific dialog.
        """
        super().__init__(dialog_id or HKDialog.__name__)

        self.DONE_OPTION = 'завершить'
        self.LAST_OPTION = 'свежий'
        self.SELECTED_CHANNEL = 'value-selectedChannel'
        self.DRIVE_ID = "b!iRCqps0M3E6-aQPU3EqrwtQWpaUslmNGiehCSqvs_PgkFFzTCYK_Sa7Y0KpehzLj"
        self.SITE_ID = "tikkurila.sharepoint.com,a6aa1089-0ccd-4edc-be69-03d4dc4aabc2,a5a516d4-962c-4663-89e8-424aabecfcf8"
        self.client = client
        self._query = ""
        self._max_period = ""

        self.options_list = {
            "Деко": "Deco",
            "Индастри": "Industry",
            self.DONE_OPTION: self.DONE_OPTION,
        }

        self.add_dialog(ChoicePrompt('channels'))
        self.add_dialog(TextPrompt('dates', HKDialog.query_validator))
        self.add_dialog(WaterfallDialog(
            "WFDiag", [
                self.channel_step,
                self.dates_step,
                self.final_step,
            ]
        ))

        self.initial_dialog_id = "WFDiag"

    async def channel_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts user to choose a channel for which they want to get the reports.
        Validates user input to ensure that only existing channels are sent back to the bot.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        selected = step_context.options if step_context.options is not None else []
        step_context.values[self.SELECTED_CHANNEL] = selected

        if len(selected) == 0:
            message = (
                f"Данные по какому рынку вас интересуют? Чтобы завершить диалог с ботом, выберите '{self.DONE_OPTION}'."
            )
        else:
            message = (
                f"Ваш выбор: {selected[0]}."
            )

        options = self.options_list.copy()
        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            retry_prompt=MessageFactory.text(
                "Пожалуйста выберите вариант из списка."),
            choices=self._to_choices(options),
            style=ListStyle.suggested_action,
        )

        return await step_context.prompt('channels', options=prompt_options)

    async def dates_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompt a user to enter no more than 4 dates on which they want to get the reports.
        Validates the user input and re-promts is the validation isn't passed.


        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        selected = step_context.result.value
        step_context.values["max"] = self.LAST_OPTION
        if selected == self.DONE_OPTION:
            return await step_context.end_dialog()

        max_period = await self.client.get_latest(channel=self.options_list[selected])
        self._max_period = max_period[0:-4]
        self._query = self.options_list[selected]

        message = (
            f"Введите максимум 4 периода через запятую в следующем формате: 2019Q1, 2019Q2 и т.п."
            f"Для получения данных за полный год выбирайте четвертый квартал."
            f"Чтобы получить только самый последний отчет, отправьте слово '{self.LAST_OPTION}' и только его"
            f"(запрос вида '2018Q2, {self.LAST_OPTION}' не сработает).  \n"
            f"Последний доступный отчет: {self._max_period}.  \n Чтобы завершить диалог, отправьте '{self.DONE_OPTION}'")

        retry_message = (
            f"Пожалуйста, введите данные в правильном формате и на дату не позднее последней доступной."
            f"Напоминаю, последний доступный отчет: {self._max_period}\n\n"
            f"Правильный формат данных: 2019Q1, 2019Q2.\n\nЧтобы завершить диалог, отправьте '{self.DONE_OPTION}'")

        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            retry_prompt=MessageFactory.text(retry_message),
            validations=self._max_period.replace(self._query, ""),
        )

        return await step_context.prompt('dates', options=prompt_options)

    async def final_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Sends the download links according to requirements specified by the user on previous stages and exits the dialog

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: the result of calling the end_dialog stack manipultaion method
        """
        selected = step_context.result
        if selected == self.DONE_OPTION:
            return await step_context.end_dialog()
        if selected == self.LAST_OPTION:
            selected = self._max_period.replace("Deco", "").replace("Ind", "")

        for_graph = self._choice_to_list(prefix=self._query, selected=selected)
        for_message = await self.client.get_links(site_id=self.SITE_ID, drive_id=self.DRIVE_ID, checklist=for_graph)
        for_message = [
            "[" + key + "](" + for_message[key] + ")" for key in for_message]

        message_links = "  \n".join(for_message)
        message = f"Вот ссылки на скачивание запрошенных отчетов:\n\n {message_links}"

        await step_context.context.send_activity(
            MessageFactory.text(message)
        )
        return await step_context.end_dialog()

    def _choice_to_list(self, prefix: str, selected: str) -> list:
        """converts the string of format "2019q2, 2019q3" to a list of format [Deco2019Q2.pdf, Deco2019Q3.pdf]

        Args:
            prefix (str): a string to be used as a prefix for every member of a list
            selected (str): string to be transformed

        Returns:
            list: list of filenames
        """
        res = selected.strip().replace("q", "Q").split(",")
        res = [prefix + i.strip() + ".pdf" for i in res]
        return res

    def _to_choices(self, choices: dict) -> List[Choice]:
        """Converts the list of strings to the list of instances of Choice objects
            Args:
                choices (List[str]): list of strings to be converted
            Returns:
                List[Choice]: list of Choice objects which can now be passed to a prompt method.
        """
        choice_list: List[Choice] = []
        for choice in choices:
            choice_list.append(Choice(value=choice))
        return choice_list

    @staticmethod
    async def query_validator(prompt_context: PromptValidatorContext) -> bool:
        """Validates the user input. Should only be used in conjuction with the
        prompt method of a dialog

        Args:
            prompt_context (PromptValidatorContext): contextual information passed to a custom PromptValidator.
            Happens automatically when this method is passed as a parameter for a prompt method.

        Returns:
            bool: True if validation is passed, False otherwise
        """
        max_value = prompt_context.options.validations
        if prompt_context.recognized.succeeded and prompt_context.recognized.value == "завершить":
            return (
                prompt_context.recognized.succeeded
                and True
            )
        if prompt_context.recognized.succeeded and prompt_context.recognized.value == "свежий":
            return (
                prompt_context.recognized.succeeded
                and True
            )
        elif prompt_context.recognized.succeeded:
            # valid dates should be between 2016 and whatever the year is rn.
            # Will break in 2030:)
            regex = rf"(201[6-9]|202[0-{max_value[3]}])(Q[1-4])"
            to_split = prompt_context.recognized.value
            to_check = to_split.replace(" ", "").upper().split(",")
            data_valid = all([True if re.fullmatch(regex, word)
                              else False for word in to_check])

            # ensuring that we don't get dates that are correct in terms of format but hasn't happened yet
            # also check that we don't get more than 4 requested dates
            if data_valid:
                to_check = [i.split("Q") for i in to_check]
                max_value = max_value.split("Q")
                max_value = [int(i) for i in max_value]

                def comparer(long_list, max_per):
                    long_list = [int(i) for i in long_list]
                    return (long_list[0] * 10 + long_list[1]
                            ) <= (max_per[0] * 10 + max_per[1])
                valid = [comparer(period, max_value) for period in to_check]
                return (
                    prompt_context.recognized.succeeded
                    and all(valid) and len(valid) < 5
                )
            else:
                await prompt_context.context.send_activity(
                    "Некорректный формат данных. Пожалуйста, следуйте инструкциям"
                )
                return False
        else:
            return prompt_context.recognized.succeeded
