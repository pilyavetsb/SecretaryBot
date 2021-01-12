import yfinance as yf
import pandas as pd
from datetime import date
import json
import os
from typing import List
from botbuilder.dialogs import (
    DialogTurnResult,
    ComponentDialog,
    WaterfallDialog,
    WaterfallStepContext,
)
from botbuilder.dialogs.prompts import TextPrompt
from botbuilder.core import MessageFactory, CardFactory
from botbuilder.schema import Attachment, Activity, ActivityTypes


class StocksDialog(ComponentDialog):
    def __init__(self, dialog_id: str = None):
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
        tikk = yf.Ticker("TIK1V.HE")
        res = tikk.history(period='2d')

        open_price = res.tail(1)['Open'][0]
        high_price = res.tail(1)['High'][0]
        low_price = res.tail(1)['Low'][0]
        actual_price = res.tail(1)['Close'][0] if res.tail(
            1)['Close'][0] > 0 else res.tail(1)['Open'][0]

        day = res.tail(1).index[0]
        day = day.to_pydatetime()
        day = day.date().strftime("%B %d %Y")

        diff_open = res.diff()['Close'][1] if res.diff()[
            'Close'][1] != 0 else res.diff()['Open'][1]
        diff_open = round(diff_open, 2)

        diff_percent = round((diff_open/actual_price)*100, 2)
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

        card_json["body"][0]["items"][1]["text"] = day
        card_json["body"][1]["items"][0]["columns"][0]["items"][0]["text"] = actual_price
        card_json["body"][1]["items"][0]["columns"][0]["items"][1]["text"] = price_string
        card_json["body"][1]["items"][0]["columns"][0]["items"][1]["color"] = color
        card_json["body"][1]["items"][0]["columns"][1]["items"][0]["facts"][0]["value"] = open_price
        card_json["body"][1]["items"][0]["columns"][1]["items"][0]["facts"][1]["value"] = high_price
        card_json["body"][1]["items"][0]["columns"][1]["items"][0]["facts"][2]["value"] = low_price

        return CardFactory.adaptive_card(card_json)
