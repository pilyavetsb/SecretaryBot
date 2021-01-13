from typing import List
from botbuilder.dialogs import (
    WaterfallDialog,
    WaterfallStepContext,
    DialogTurnResult,
    ComponentDialog,
)
from botbuilder.dialogs.prompts import ChoicePrompt, PromptOptions, TextPrompt, PromptValidatorContext, DateTimePrompt
from botbuilder.dialogs.choices import Choice, FoundChoice
from botbuilder.dialogs.choices.list_style import ListStyle
from botbuilder.core import MessageFactory, CardFactory, ConversationState, UserState
from botbuilder.schema import Attachment, Activity, ActivityTypes
import re
import json
import os
from datetime import datetime
from graph_client import GraphClient
from yattag import Doc
from data_models import UserProfile


class AutoreplyDialog(ComponentDialog):
    """Dialog contaning the autoreply setting logic. Helps the user to set the
    nicely formatted autoreply message without touching MS Outlook by sending an
    Adaptive card to fill out.

    Attributes:
        DONE_OPTION(str): word a user has to send to the bot to cancel the dialog at any stage
        CARD_PATH(list): path to an Adaptive Card json template
        client(GraphClient): MS Graph client instance associated with this dialog. Used to perform all calls to the Graph API
        user_state(UserState): user state storage object
        accessor(StatePropertyAccessor): State property accessors are used to read or write state properties,
        and provide get, set, and delete methods for accessing state properties from within a turn.
        today: today's date
        initial_dialog_id: UID for this dialog
    """

    def __init__(
            self,
            user_state: UserState,
            client: GraphClient,
            dialog_id: str):
        """inits an AutoreplyDialog instance

        Args:
            user_state (UserState): user state storage object
            client (GraphClient): MS Graph client instance associated with this dialog. Used to perform all calls to the Graph API
            dialog_id (str): a unique name identifying specific dialog.
        """
        super().__init__(dialog_id or AutoreplyDialog.__name__)

        self.DONE_OPTION = 'завершить'
        self.CARD_PATH = ["cards_templates", "Autoreply_card"]
        self.client = client
        self.user_state = user_state
        self.accessor = self.user_state.create_property("UserProfile")
        self.today = datetime.date(datetime.today())

        # add validator if it flies
        self.add_dialog(TextPrompt("fake", AutoreplyDialog.validation_wrapper))
        self.add_dialog(WaterfallDialog(
            "WFDiag", [
                self.card_step,
                self.final_step,
            ]
        ))
        self.initial_dialog_id = "WFDiag"

    async def card_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Sends a message with an Adaptive card attachment for a user to fill.
        The autoreply will be set based on the user input in this step. All inputs are also validated.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the prompt stack manipulation method.
            Contains the users' response.
        """
        self.user_info: UserProfile = await self.accessor.get(step_context.context, UserProfile)
        msg = "Я помогу тебе установить автоответ и ничего не забыть! Для этого заполни, пожалуйста, маленькую форму ниже или отправь 'Завершить'"
        await step_context.context.send_activity(msg)
        # не забыть удалить messageback из джейсона карты, т.к. код уже заточен
        # под postback
        card_msg = Activity(
            type=ActivityTypes.message,
            attachments=[self._populate_with_data(rel_path=self.CARD_PATH)],
        )
        prompt_options = PromptOptions(
            prompt=None,
            retry_prompt=MessageFactory.text("Пожалуйста, исправь ошибки")
        )
        await step_context.context.send_activity(MessageFactory.text(msg))
        response = await step_context.context.send_activity(card_msg)
        # Adaptive cards don't support validation, so to ensure it
        # we need to create a fake prompt which won't be visible to the user
        return await step_context.prompt("fake", options=prompt_options)

    async def final_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Writes the user input to the user_info attribute and sets the autoreply.

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn


        Returns:
            DialogTurnResult: result of calling the end_dialog stack manipulation method.
        """
        msg = step_context.result
        if msg.lower() == self.DONE_OPTION:
            return await step_context.end_dialog()
        msg_json = json.loads(msg)
        names = [
            msg_json['name1'],
            msg_json['name2'],
            msg_json['name3'],
            msg_json['name4']]
        areas = [
            msg_json['area1'],
            msg_json['area2'],
            msg_json['area3'],
            msg_json['area4']]

        self.user_info.areas = areas
        self.user_info.names = names
        self.user_info.lang = msg_json['language']
        self.user_info.phone = msg_json['phone']
        await self.accessor.set(step_context.context, self.user_info)
        await self.user_state.save_changes(step_context.context)

        msg = self._message_constructor(
            msg_json['reason'],
            msg_json['startdate'],
            msg_json['enddate'],
            msg_json['language'],
            names,
            areas,
            msg_json['phone'])
        if not await self.client.set_autoreply("Bogdan.Pilyavets@tikkurila.com", msg, msg_json['startdate'], msg_json['enddate']):
            step_context.context.send_activity(MessageFactory.text(
                "Что-то пошло не так😿Вероятно, проблема на стороне сервера. Попробуйте еще раз позднее"))
        await self.client.set_oof("Bogdan.Pilyavets@tikkurila.com", msg_json['reason'], msg_json['startdate'], msg_json['enddate'])
        # step_context.context.update_activity(ids)
        return await step_context.end_dialog()

    def _to_choices(self, choices: list) -> List[Choice]:
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

    def _phone_str_constructor(self, phone: str) -> dict:
        """ Constructs containing both russian and english versions of the message re contacts during the users' absence

        Args:
            phone (str): phone number

        Returns:
            dict: dictionary containing both russian and english versions of the message re contacts during the users' absence
        """
        if phone != "" and phone is not None:
            phone = phone.replace("-", "")
            if phone[0] == '8':
                phone = "+7" + phone[1:]
            pretty = phone[0:2] + "-" + phone[2:5] + "-" + \
                phone[5:8] + "-" + phone[8:10] + "-" + phone[10:12]
            ru_str = f"При возникновении срочных вопросов звоните {pretty}"
            eng_str = f"In case you have urgent matters to discuss - please call {pretty}"
            return {"RU": ru_str, "ENG": eng_str}
        return {"RU": "", "ENG": ""}

    def _names_areas_constructor(self, names: list, areas: list) -> dict:
        """Constructs both russian and english versions of the message re substituting employees

        Args:
            names (list): Names of employees covering for the user.
            This arguments is connected to the rep_areas argument, i.e. rep_names[0] is responsible for rep_areas[0].
            areas (list): Areas of responsibility of the employees from the rep_names argument.

        Returns:
            dict: dictionary containing both russian and english versions of the message re substituting employees
        """
        names_areas = list(zip(names, areas))
        names_areas = dict([i for i in names_areas if i != ('', '')])
        if names_areas == {}:
            repl_str_ru = f"Буду рад ответить на ваши вопросы по возращении."
            repl_str_eng = f"I will be happy to answer all your questions on my return."
        elif len(names_areas) == 1:
            repl_str_ru = f"По любым вопросам вы можете обратиться к этому сотруднику: {list(names_areas.keys())[0]}."
            repl_str_eng = f"For any enquiries, please contact the following employee: {list(names_areas.keys())[0]}."
        elif set(names_areas.values()) == {''}:
            repl_str_ru = "По любым вопросам вы можете обратиться к следующим сотрудникам: "
            repl_str_eng = "For any enquiries, please contact the following employees: "
            for name in names_areas.keys():
                repl_str_ru = repl_str_ru + name + ", "
                repl_str_eng = repl_str_eng + name + ", "
            repl_str_ru = repl_str_ru[:-2] + "."
            repl_str_eng = repl_str_eng[:-2] + "."
        else:
            repl_str_ru = "В мое отсутствие вы можете обратиться к следующим сотрудникам: "
            repl_str_eng = "For any enquiries, please contact the following employees: "
            for name, area in names_areas.items():
                repl_str_ru = repl_str_ru + name + " - " + area + ", "
                repl_str_eng = repl_str_eng + name + ", "
            repl_str_ru = repl_str_ru.replace(' - , ', ', ')
            repl_str_ru = repl_str_ru[:-2] + "."
            repl_str_eng = repl_str_eng[:-2] + "."
        return {"RU": repl_str_ru, "ENG": repl_str_eng}

    def _message_constructor(
            self,
            reason: str,
            startdate: str,
            enddate: str,
            lang: str,
            names: list,
            areas: list,
            phone='') -> str:
        """Constructs an HTML-tagged message to be used as an autoreply

        Args:
            reason (str): reason of autoreply, i.e. "vacation"
            startdate (str): autoreply's start date
            enddate (str): autoreply's end date
            lang (str): user target language
            names (list): Names of employees covering for the user.
            This arguments is connected to the rep_areas argument, i.e. rep_names[0] is responsible for rep_areas[0].
            areas (list): Areas of responsibility of the employees from the rep_names argument.
            phone (str, optional): Phone number. Defaults to ''.

        Returns:
            str: autoreply message as a string with HTML-tags
        """
        reasons_dict = {
            'Vacation': {'RU': 'находиться в отпуске.', 'ENG': 'on vacation'},
            'Travel': {'RU': 'находиться в командировке.', 'ENG': 'travelling on business'},
            'Sickleave': {'RU': 'находиться на больничном.', 'ENG': 'on sick leave'},
            'Other': {'RU': 'отсутствовать на рабочем месте.', 'ENG': 'absent from work'}
        }
        startdate = datetime.strftime(
            datetime.strptime(
                startdate,
                "%Y-%m-%d"),
            "%d.%m.%Y")
        enddate = datetime.strftime(
            datetime.strptime(
                enddate,
                "%Y-%m-%d"),
            "%d.%m.%Y")
        phone_dict = self._phone_str_constructor(phone)
        repl_dict = self._names_areas_constructor(names=names, areas=areas)
        ru_temp = (
            f"Уважаемые коллеги,<br>Информирую вас о том, что в период с {startdate} по {enddate} "
            f"я буду {reasons_dict[reason]['RU']} {repl_dict['RU']} {phone_dict['RU']} ")
        eng_temp = (
            f"Dear colleagues,<br>please be informed that from {startdate} to {enddate} I will be {reasons_dict[reason]['ENG']}."
            f" {repl_dict['ENG']} {phone_dict['ENG']}")
        doc, tag, text = Doc().tagtext()
        with tag('html'):
            with tag('body'):
                if lang == "RU":
                    with tag('p'):
                        doc.asis(ru_temp)
                elif lang == "EN":
                    with tag('p'):
                        doc.asis(eng_temp)
                else:
                    with tag('p'):
                        doc.asis(ru_temp)
                    with tag('p'):
                        doc.asis(eng_temp)
        return doc.getvalue()

    def _populate_with_data(
            self,
            rel_path: list,
            startdate=None,
            enddate=None,
            phone=None,
            lang=None,
            rep_names: list = None,
            rep_areas: list = None) -> Attachment:
        """Pre-fills the Adaptive card template based on the info from the user_info attribute
        so the user doesn't have to make all the inputs in case of input mistakes

        Args:
            rel_path (list): path to the Adaptive card json file structured as a list [folder, filename]
            startdate (datetime.date, optional): Start date of an autoreply. Defaults to None.
            enddate (datetime.date, optional): End date of an rutoreply. Defaults to None.
            phone (str, optional): phone number. Defaults to None.
            lang (str, optional): User's target language. Defaults to None.
            rep_names (list, optional): Names of employees covering for the user.
            This arguments is connected to the rep_areas argument, i.e. rep_names[0] is responsible for rep_areas[0].
            Defaults to None.
            rep_areas (list, optional): Areas of responsibility of the employees from the rep_names argument. Defaults to None.

        Returns:
            Attachment: An Attachment instance ready to be attached to a message
        """
        # this trick is needed because it's the only way to use the attributes
        # as the default values because of Python's order of evaluation
        if startdate is None:
            startdate = self.today
        if enddate is None:
            enddate = self.today
        if rep_names is None:
            rep_names = self.user_info.names
        if rep_areas is None:
            rep_areas = self.user_info.areas
        if lang is None:
            lang = self.user_info.lang
        if phone is None:
            phone = self.user_info.phone

        # constructing the full path and accesing the name.
        # This whole "folder-filename" as a list thing is needed to make a
        # filepath OS-agnostic
        this_file = os.getcwd()
        full_path = os.path.join(this_file, *rel_path)
        with open(full_path, "r", encoding='utf-8') as card_file:
            card_json = json.load(card_file)

        start = datetime.strftime(startdate, "%Y-%m-%d")
        end = datetime.strftime(enddate, "%Y-%m-%d")

        card_json['body'][2]["min"] = start
        card_json['body'][2]["value"] = start
        card_json['body'][4]["min"] = end
        card_json['body'][4]["value"] = end
        card_json['body'][6]['value'] = phone
        if rep_names:
            for i in range(4):
                card_json['body'][8]['columns'][0]['items'][i]['value'] = rep_names[i]
                card_json['body'][8]['columns'][1]['items'][i]['value'] = rep_areas[i]
        card_json['body'][10]['value'] = lang
        return CardFactory.adaptive_card(card_json)

    @staticmethod
    async def phone_validator(num_to_validate: str) -> bool:
        """Checks whether the user entered a valid phone number.
        Currently supports only russian numbers.

        Args:
            num_to_validate (str): number entered by a user

        Returns:
            bool: True if the validation is passed, False otherwise
        """
        if num_to_validate == "" or num_to_validate is None:
            return True
        cleaned = num_to_validate.replace("-", "")
        if num_to_validate[0] == '8':
            cleaned = "+7" + cleaned[1:]
        validity = len(cleaned) == 12
        if validity:
            return True
        return False

    @staticmethod
    async def date_validator(startdate, enddate) -> bool:
        """Checks whether selected dates are valid. enddate should be >=startdate

        Args:
            startdate (str): start date. Should be <=end date to pass the validation
            enddate (str): end date. Should be >= startdate to pass the validation

        Returns:
            bool: True if dates are valid, False otherwise
        """
        try:
            return datetime.strptime(
                enddate, "%Y-%m-%d") >= datetime.strptime(startdate, "%Y-%m-%d")
        except ValueError:
            return False

    @staticmethod
    async def validation_wrapper(prompt_context: PromptValidatorContext) -> bool:
        """Wrapper for all validation methods. Should only be used in conjuction with the
        prompt method of a dialog. If all validations are passed then the dialog goes to the next step,
        otherwise user is re-promted to correct the mistakes

        Args:
            prompt_context (PromptValidatorContext): Contextual information passed to a custom PromptValidator.
            Happens automatically when this method is passed as a parameter for a prompt method.

        Returns:
            bool: True if all validattions are passed succesfully, False otherwise
        """
        # validations are considered to be passed automatically if user wants
        # to terminate the session
        if prompt_context.recognized.succeeded and prompt_context.recognized.value.lower() == "завершить":
            return (
                prompt_context.recognized.succeeded
                and True
            )
        # otherwise we call all the individual validators
        elif prompt_context.recognized.succeeded:
            val_json = json.loads(prompt_context.recognized.value)
            phone = await AutoreplyDialog.phone_validator(val_json['phone'])
            dates = await AutoreplyDialog.date_validator(val_json['startdate'], val_json['enddate'])
            # reason must be always filled in
            try:
                reason = val_json['reason']
            except KeyError:
                await prompt_context.context.send_activity(
                    "Выберите, пожалуйста, причину. Коллег снедает любопытство!"
                )
                return False
            if not phone:
                await prompt_context.context.send_activity(
                    "Проверьте, пожалуйста, правильно ли введен номер телефона"
                )
                return False
            if not dates:
                await prompt_context.context.send_activity(
                    "Проверьте, пожалуйста, правильно ли выбраны даты. Подсказка - конечная дата не может быть раньше начальной😏"
                )
                return False
            return True
        else:
            return prompt_context.recognized.succeeded
