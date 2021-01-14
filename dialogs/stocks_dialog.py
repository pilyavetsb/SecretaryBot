import yfinance as yf
import json
import os
from typing import List
from botbuilder.dialogs import (
    DialogTurnResult,
    ComponentDialog,
    WaterfallDialog,
    WaterfallStepContext,
)
from botbuilder.core import MessageFactory, CardFactory
from botbuilder.schema import Attachment, Activity, ActivityTypes


class StocksDialog(ComponentDialog):
    """A dialog sending Tikkurila's stock price to the user

        Attributes:
            CARD_PATH(list): path to an Adaptive Card json template
            initial_dialog_id(str): UID for this dialog
    """

    def __init__(self, dialog_id: str):
        """inits the StocksDialog instance

        Args:
            dialog_id (str): a unique name identifying specific dialog.
        """
        super().__init__(dialog_id or StocksDialog.__name__)

        self.CARD_PATH = ["cards_templates", "Stock_card"]

        self.add_dialog(
            WaterfallDialog(WaterfallDialog.__name__,
                            [
                                self.only_step
                            ])
        )

        self.initial_dialog_id = WaterfallDialog.__name__

    async def only_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        """Sends an adaptive card containing the following information re Tikkurila stock:
            - current price
            - open price
            - max price (inside a day)
            - min price (inside a day)
            - diff to the previous close price

        Args:
            step_context (WaterfallStepContext): the context for the current dialog turn

        Returns:
            DialogTurnResult: result of calling the end_dialog stack manipulation method.
        """
        message = "В следующем сообщении будет отправлен курс акции Тиккурила. Это может занять около 5 секунд"
        await step_context.context.send_activity(
            MessageFactory.text(message)
        )

        card_msg = Activity(
            type=ActivityTypes.message,
            attachments=[self._populate_with_data(self.CARD_PATH)],
        )
        await step_context.context.send_activity(card_msg)

        return await step_context.end_dialog()

    def _populate_with_data(self, rel_path: list) -> Attachment:
        """pulls the stock data from the Yahoo Finance API, populates the Adaptive card with that data
        and creates an Attachment instance with that Card

        Args:
            rel_path (list): path to the Adaptive card json file structured as a list [folder, filename]

        Returns:
            Attachment: An Attachment instance ready to be attached to a message
        """
        tikk = yf.Ticker("TIK1V.HE")
        res = tikk.history(period='2d')

        open_price = res.tail(1)['Open'][0]
        high_price = res.tail(1)['High'][0]
        low_price = res.tail(1)['Low'][0]
        # if we already have a closing price - use it, otherwise take an open
        # price
        actual_price = res.tail(1)['Close'][0] if res.tail(
            1)['Close'][0] > 0 else res.tail(1)['Open'][0]

        day = res.tail(1).index[0]
        day = day.to_pydatetime()
        day = day.date().strftime("%B %d %Y")

        diff_open = res.diff()['Close'][1] if res.diff()[
            'Close'][1] != 0 else res.diff()['Open'][1]
        diff_open = round(diff_open, 2)

        # construct a string comparing the price with the previous day
        diff_percent = round((diff_open / actual_price) * 100, 2)
        if diff_open > 0:
            symbol, color = "▲", "Good"
        elif diff_open < 0:
            symbol, color = "▼", "Attention"
        else:
            symbol, color = "►", "Default"
        diff_percent_str = "(" + str(diff_percent) + "%)"

        price_string = " ".join([symbol, str(diff_open), diff_percent_str])

        this_file = os.getcwd()
        full_path = os.path.join(this_file, *rel_path)
        with open(full_path, "r") as card_file:
            card_json = json.load(card_file)

        # atm there is no dynamic templating for Python Adaptive cards SDK,
        # hence the brute force approach
        card_json["body"][0]["items"][1]["text"] = day
        card_json["body"][1]["items"][0]["columns"][0]["items"][0]["text"] = actual_price
        card_json["body"][1]["items"][0]["columns"][0]["items"][1]["text"] = price_string
        card_json["body"][1]["items"][0]["columns"][0]["items"][1]["color"] = color
        card_json["body"][1]["items"][0]["columns"][1]["items"][0]["facts"][0]["value"] = open_price
        card_json["body"][1]["items"][0]["columns"][1]["items"][0]["facts"][1]["value"] = high_price
        card_json["body"][1]["items"][0]["columns"][1]["items"][0]["facts"][2]["value"] = low_price

        return CardFactory.adaptive_card(card_json)
