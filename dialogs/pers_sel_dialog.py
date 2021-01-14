from typing import Iterable, List
from botbuilder.dialogs import (
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
    ComponentDialog,
)
from botbuilder.dialogs.prompts import ChoicePrompt, PromptOptions, TextPrompt, PromptValidatorContext
from botbuilder.dialogs.choices import Choice, FoundChoice
from botbuilder.dialogs.choices.list_style import ListStyle
from botbuilder.schema import Attachment, Activity, ActivityTypes
from botbuilder.core import MessageFactory, CardFactory
from graph_client import GraphClient
from functools import reduce
import os
import operator
import json


class PersonDialog(ComponentDialog):
    """This is a dialog designed to guide a user through a decision tree
    to help them choose the right person to contact with their inquiry

        Attributes:
            DONE_OPTION(str): word a user has to send to the bot to cancel the dialog at any stage
            SITE_ID(str): id of the Sharepoint site where the json file describing the tree structure resides
            DRIVE_ID(str): id of the drive resource where the json file describing the tree structure resides
            selected_keys(list): list of jsoon keys selected by the user
            client(GraphClient): MS Graph client instance associated with this dialog. Used to perform all calls to the Graph API
            json_path(str): json file describing a tree structure being navigated by the user
            options_list(list): a list containing all the top level choices available to the user.
            Can be also viewed as a list of the top-level keys in the tree structure
            initial_dialog_id(str): UID for this dialog
    """

    def __init__(self, client: GraphClient, dialog_id: str = None):
        """inits a PersonDialog instance

        Args:
            client (GraphClient): MS Graph client instance associated with this dialog. Used to perform all calls to the Graph API
            dialog_id (str): a unique name identifying specific dialog.
        """
        super().__init__(dialog_id or PersonDialog.__name__)

        self.DONE_OPTION = "завершить"
        self.EXCEL_LINK = ""
        self.SITE_ID = "tikkurila.sharepoint.com,a6aa1089-0ccd-4edc-be69-03d4dc4aabc2,a5a516d4-962c-4663-89e8-424aabecfcf8"
        self.DRIVE_ID = "b!iRCqps0M3E6-aQPU3EqrwtQWpaUslmNGiehCSqvs_PjR9APmWaAIRJ2s7cN4zjqu"

        self.selected_keys = []
        self.client = client
        self.json_path = None

        self.options_list = ["ФАО", "Бухгалтерия", self.DONE_OPTION]

        self.add_dialog(ChoicePrompt('level1'))
        self.add_dialog(ChoicePrompt('level2'))
        self.add_dialog(ChoicePrompt('level3'))
        self.add_dialog(ChoicePrompt('level4'))

        self.add_dialog(WaterfallDialog(
            "WFDiag", [
                self.dep_step,
                self.type_step,
                self.subtype_step,
                self.lvl4_step,
                self.final_step,
            ]
        ))

        self.initial_dialog_id = "WFDiag"

    async def dep_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts the user to choose the department to which their question is related and stores the choice.
        Validates the input and re-promts the user if the validation is not passed.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        self.selected_keys = []

        message = (
            f"К какому отделу относится ваш вопрос? Подсказка: ФАО отвечает за всевозможные "
            f"согласования и расчеты, бухгалтерия - за правильный документооборот."
            f"Чтобы завершить работу с ботом, выберите '{self.DONE_OPTION}'.")

        options = self.options_list.copy()
        path_link = await self.client.download_file(
            self.SITE_ID,
            self.DRIVE_ID,
            "FunctionalAreas/selector_dialog_tree.json:/content"
        )

        self.json_path = json.loads(path_link.decode("utf-8"))

        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            retry_prompt=MessageFactory.text(
                "Пожалуйста, выберите вариант из списка."),
            choices=self._to_choices(options),
            style=ListStyle.suggested_action,
        )
        return await step_context.prompt('level1', options=prompt_options)

    async def type_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts the user to choose the functional area to which their question is related and stores the choice.
        Validates the input and re-promts the user if the validation is not passed.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        selected = step_context.result.value

        if selected == self.DONE_OPTION:
            return await step_context.end_dialog()

        self.selected_keys.append(selected)

        message = f"К какой части функционала {selected} относится ваш вопрос? Выберите вариант из списка. "
        f"Чтобы завершить работу с ботом, выберите '{self.DONE_OPTION}'."
        options = list(self._dict_traverser(
            self.selected_keys, self.json_path).keys())
        options.append(self.DONE_OPTION)

        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            retry_prompt=MessageFactory.text(
                "Пожалуйста, выберите вариант из списка."),
            choices=self._to_choices(options),

        )
        return await step_context.prompt('level2', options=prompt_options)

    async def subtype_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts the user to choose further details of a functional area to which their question is related and stores the choice.
        Validates the input and re-promts the user if the validation is not passed.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        selected = step_context.result.value

        if selected == self.DONE_OPTION:
            return await step_context.end_dialog()

        self.selected_keys.append(selected)

        # if we already reached the end of a branch, silently go to the next stage,
        # no additional prompt is needed
        json_node = self._dict_traverser(self.selected_keys, self.json_path)
        if "@tikkurila.com" in "\t".join(json_node):
            return await step_context.next(json_node)

        message = f"Ваш выбор: {selected}. Пожалуйста конкретизируйте его, выбрав вариант из списка, "
        f"или выберите '{self.DONE_OPTION}', чтобы закончить работу с ботом."
        options = list(json_node.keys())
        options.append(self.DONE_OPTION)

        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            retry_prompt=MessageFactory.text(
                "Пожалуйста, выберите вариант из списка."),
            choices=self._to_choices(options),

        )
        return await step_context.prompt('level3', options=prompt_options)

    async def lvl4_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Prompts the user to choose further details of a functional area to which their question is related and stores the choice.
        Validates the input and re-promts the user if the validation is not passed.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        selected = step_context.result

        if selected == self.DONE_OPTION:
            return await step_context.end_dialog()

        if not isinstance(selected, FoundChoice):
            return await step_context.next(selected)

        self.selected_keys.append(selected.value)

        json_node = self._dict_traverser(self.selected_keys, self.json_path)

        # if we already reached the end of a branch, silently go to the next stage,
        # no additional prompt is needed
        if "@tikkurila.com" in "\t".join(json_node):
            return await step_context.next(json_node)

        message = f"{selected.value} - в этом не так-то просто разобраться! "
        f"Осталось сделать последнее уточнение и выбрать вариант из списка:"
        options = list(json_node.keys())

        prompt_options = PromptOptions(
            prompt=MessageFactory.text(message),
            retry_prompt=MessageFactory.text(
                "Пожалуйста, выберите вариант из списка."),
            choices=self._to_choices(options),

        )
        return await step_context.prompt('level4', options=prompt_options)

    async def final_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Sends one or more Adaptive cards containing the information on the best employee to contact
        given the previous choices of the user

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the end_dialog stack manipulation method.
        """
        selected = step_context.result

        # if the email was already identified on the previous steps, use it
        # if not - identify it first
        if not isinstance(selected, FoundChoice):
            emails = selected
        else:
            self.selected_keys.append(selected.value)
            emails = self._dict_traverser(self.selected_keys, self.json_path)

        messages = [await self._populate_adaptive(i) for i in emails]
        card_msg = Activity(
            type=ActivityTypes.message,
            attachments=messages,
        )

        await step_context.context.send_activities(
            [MessageFactory.text("Отлично! Вот кто может вам помочь:"),
             card_msg]
        )

        return await step_context.end_dialog()

    def _dict_traverser(self, lookup: Iterable, nested: dict) -> str:
        # traverses the tree based on the list of keys
        return reduce(operator.getitem, lookup, nested)

    def _to_choices(self, choices: list) -> List[Choice]:
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

    async def _populate_adaptive(self, email: str) -> Attachment:
        """Fetches the data from the Graph API and populates the Adaptive card
        with this information

        Args:
            email (str): an email of the employee to be used in Graph calls

        Returns:
            Attachment: An Attachment instance ready to be attached to a message
        """
        manager = await self.client.get_manager(email)
        status = await self.client.get_presence(email)
        autoreply = await self.client.get_autorepl_date(email)
        picture = await self.client.get_picture_for_adap(email)
        name, title, mail = await self.client.get_user(email)

        # constructing the full path and accesing the name.
        # This whole "folder-filename" as a list thing is needed to make a
        # filepath OS-agnostic
        rel_path = ["cards_templates", "Person_card"]
        this_file = os.getcwd()
        full_path = os.path.join(this_file, *rel_path)
        with open(full_path, "r") as card_file:
            card_json = json.load(card_file)

        card_json["body"][0]['columns'][0]['items'][0]['url'] = picture
        card_json["body"][0]['columns'][1]['items'][0]['items'][0]['text'] = name
        card_json["body"][0]['columns'][1]['items'][0]['items'][1]['text'] = title
        card_json["body"][0]['columns'][1]['items'][0]['items'][2]['text'] = mail
        card_json["body"][0]['columns'][1]['items'][0][
            'items'][3]['text'] = f"Текущий статус: {status}"
        card_json["body"][0]['columns'][1]['items'][1]['items'][0][
            'text'] = autoreply if autoreply == "" else f"Автоответ до {autoreply}"
        card_json["body"][1]['text'] = f"Непосредственный руководитель: {manager}"

        return CardFactory.adaptive_card(card_json)
