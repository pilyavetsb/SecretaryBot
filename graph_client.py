import os
from io import BytesIO
from PIL import Image, ImageOps
from babel.dates import format_date
from datetime import datetime
import config
import json
import pyperclip
import base64
import webbrowser
import requests
import msal
from urllib.parse import urlparse, urljoin
site_id = "tikkurila.sharepoint.com,a6aa1089-0ccd-4edc-be69-03d4dc4aabc2,a5a516d4-962c-4663-89e8-424aabecfcf8"
drive_id = "b!iRCqps0M3E6-aQPU3EqrwtQWpaUslmNGiehCSqvs_PgkFFzTCYK_Sa7Y0KpehzLj"
AUTHORITY_URL = "https://login.microsoftonline.com/tikkurila.onmicrosoft.com"
RESOURCE_URI = "https://graph.microsoft.com/"
RESOURCE = RESOURCE_URI + "v1.0"
full_for_latest = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/Deco:/children?$expand=listItem($expand=fields)"


class GraphClient:
    """
    A class used to interface with the Microsoft Graph API.
    It relies on an Microsoft Authentication library (msal). More detailed information re different authentication
    flows is available here - https://docs.microsoft.com/en-us/azure/active-directory/develop/msal-authentication-flows
    """

    def __init__(self):
        """Inits the GraphClient instance

        Raises:
            ValueError: raised if no response or error reponse are received from MS servers
            and hence the device flow can't be initiated.
        """
        # scope is defined explicitly to have a visibility of the exact access
        # rights
        scope = [
            RESOURCE_URI + "/" + "Files.ReadWrite",
            RESOURCE_URI + "/" + "Sites.ReadWrite.All",
            RESOURCE_URI + "/" + "Calendars.ReadWrite",
            RESOURCE_URI + "/" + "MailboxSettings.ReadWrite",
        ]
        app = msal.PublicClientApplication(
            config.client_id, authority=AUTHORITY_URL)

        # TODO switch to Integrated Windows Authentication flow in prod. RN it
        # is device_flow which isn't scalable
        flow = app.initiate_device_flow(scopes=scope)
        if "user_code" not in flow:
            raise ValueError(
                "Fail to create device flow. Err: %s" %
                json.dumps(
                    flow, indent=4))
        pyperclip.copy(flow['user_code'])
        webbrowser.open(flow['verification_uri'])
        # acquiring token and updating headers for all requsets in a current
        # session
        token = app.acquire_token_by_device_flow(flow)
        self.session = requests.Session()
        self.session.headers.update(
            {'Authorization': 'Bearer ' + token['access_token']})

    async def _api_endpoint(self, url: str, version="v1.0") -> str:
        """Convert a relative path such as /me/photo/$value to a full URI based
        on the current RESOURCE and API_VERSION settings in config.py.

        Args:
            url (str): [description]
            version (str, optional): Which Graph endpoint to use. Only two valid options: "beta" and "v1.0".
            Defaults to "v1.0".

        Returns:
            str: full URI, i.e. "https://graph.microsoft.com/me/photo/$value"
        """
        if urlparse(url).scheme in ["http", "https"]:
            return url  # url is already complete
        return urljoin(f"{RESOURCE_URI}{version}/", url.lstrip("/"))

    async def file_loader(self, site_id: str, drive_id: str, query: str) -> str:
        """Returns a full URI to download a file from a Sharepoint site

        Args:
            site_id (str): Sharepoint site to download from
            drive_id (str): drive containing the desired driveItem
            query (str): path to the file in the form of {item-path}:/content (without brackets)

        Returns:
            str: full URI to download a file
        """
        relative_url = f"/sites/{site_id}/drives/{drive_id}/root:/{query}"
        return await self._api_endpoint(relative_url)

    async def download_file(self, site_id: str, drive_id: str, query: str) -> bytes:
        """Returns a byte-content of a file from a Sharepoint site

        Args:
            site_id (str): Sharepoint site to download from
            drive_id (str): drive containing the desired driveItem
            query (str): path to the file in the form of {item-path}:/content (without brackets)

        Returns:
            bytes: file content in bytes
        """
        link = await self.file_loader(site_id, drive_id, query)
        call = self.session.get(link)
        return call.content

    async def get_latest(self, channel: str) -> str:
        """Returns the name of the latest file from the Sharepoint folder

        Args:
            channel (str): address of the folder where we are serching for the latest element

        Raises:
            ValueError: raised if no response or error reponse are received from MS server

        Returns:
            str: name of the latest file from the Sharepoint folder.
            Latest is defined as having the latest "last changes" date.
        """
        query = f"{channel}:/children?$expand=listItem($expand=fields($select=Latest))"
        latest_file = await self.file_loader(site_id, drive_id, query)
        call = self.session.get(latest_file)
        if call.status_code == 200:
            for i in call.json()['value']:
                if i['listItem']['fields']['Latest']:
                    return i['name']
        else:
            raise ValueError(
                f"Some connection problems. Error code: {call.status_code}")

    async def get_links(self, site_id: str, drive_id: str, checklist: list) -> dict:
        """Returns the dictionary of filenames and corresponding download links, selected according to checklist argument

        Args:
            site_id (str): Sharepoint site to download from
            drive_id (str): drive containing the desired driveItem
            checklist (list): list of filenames for which to get the download links

        Raises:
            ValueError: raised if no response or error reponse are received from MS server

        Returns:
            dict: dictionary with filenames and download links, such as {name:link}
        """
        channel = checklist[0].split("2")[0]  # year always starts with a 2
        query = f"{channel}:/children?$expand=listItem"
        url = await self.file_loader(site_id, drive_id, query)
        call = self.session.get(url)
        res = {}
        if call.status_code == 200:
            for i in call.json()['value']:
                if i['name'] in checklist:
                    res[i['name']] = i['@microsoft.graph.downloadUrl']
            return res
        else:
            raise ValueError(
                f"Some connection problems. Error code: {call.status_code}")

    async def get_manager(self, email: str) -> str:
        """Returns a name of a manager of an employee (defined by email arg)

        Args:
            email (str): email of an employee whose manager we want to get

        Returns:
            str: name of a manager or "Not Available" in case Azure AD lacks the data
        """
        url = await self._api_endpoint(f"/{email}/manager", "v1.0")
        res = self.session.get(url)
        if res.status_code == 200:
            return res.json()['displayName']
        else:
            return "Not Available"

    async def get_autorepl_date(self, email: str) -> str:
        """Returns the date till which the autoreply is active for the user specified in the email argument.
        If no autoreply is set, returns an empty string

        Args:
            email (str): email of an employee whose autoreply date we are trying to fetch

        Returns:
            str: string representation of a date until which autoreply is active, formatted like %d.%m.%Y.
            If autoreply is not set - an empty string.
        """
        url = await self._api_endpoint(f"/users/{email}/getMailTips", "v1.0")
        payload = {
            "EmailAddresses": [
                email
            ],
            "MailTipsOptions": "automaticReplies, mailboxFullStatus"
        }
        res = self.session.post(url=url, json=payload).json()
        try:
            repl_date = res['value'][0]['automaticReplies']['scheduledEndTime']['dateTime']
            repl_date = repl_date.split("T")[0]
            repl_date = datetime.strptime(repl_date, "%Y-%m-%d").date()
            repl_date = format_date(repl_date, format='short', locale='ru')
            return str(repl_date)
        except KeyError:
            return ""

    async def get_presence(self, email: str) -> str:
        """Returns the current status of an employee specified in the email parameter.
        I.e. 'free', 'busy', 'do not disturb' etc

        Args:
            email (str): email of a person whose status we are fetching

        Returns:
            str: current status of an employee. If no data is available for any reason the value is set to "No info"
        """
        url = await self._api_endpoint(f"/users/{email}/presence", "beta")
        res = self.session.get(url)
        if res.status_code == 200:
            res = res.json()
            return res['availability'] + ", " + res['activity']
        else:
            return "No info"

    async def get_picture_for_adap(self, email: str) -> str:
        """Returns a base64-encoded picture of an employee specified in the email argument.
        If no picture is set returns a placeholder

        Args:
            email (str): an email of a user whose picture we are fetching

        Returns:
            str: base-64 encoded image of size (96,96) to be used in the Adaptive cards.
            If there is no image for the selected employee uses a placeholder image instead.
        """
        url = await self._api_endpoint(f"/users/{email}/photo/$value", "v1.0")
        url1 = await self._api_endpoint(f"/users/{email}/photos/96x96/$value", "v1.0")
        res1 = self.session.get(url1)
        # try to fetch 96x96 image directly, if not possible - resize it
        # accordingly
        if res1.status_code == 200:
            base = base64.b64encode(res1.content).decode()
            data_uri = "data:image/png;base64," + base
            return data_uri

        res = self.session.get(url)
        if res.status_code == 200:
            with Image.open(BytesIO(res.content)) as img:
                img = ImageOps.fit(img, (96, 96), centering=(0.5, 0.0))
                buffered = BytesIO()
                img.save(buffered, format="JPEG")
                base = base64.b64encode(buffered.getvalue()).decode()
            data_uri = "data:image/png;base64," + base
        else:
            this_file = os.getcwd()
            full_path = os.path.join(this_file, *
                                     ["cards_templates", "placeholder.png"])
            with open(full_path, "rb") as f:
                base = base64.b64encode(f.read()).decode()
            data_uri = "data:image/png;base64," + base
        return data_uri

    # User.Read.All scope would be neccessary
    async def get_user(self, email: str) -> list:
        """Fetches the user name and job title data. If any of them is not available
        uses a "Not Available" placeholder instead

        Args:
            email (str): email of a user whose title and name we are fetcing

        Returns:
            list: [name, title, email], any missing element is replaced with the "Not Available placeholder"
        """
        url = await self._api_endpoint(f"/users/{email}?$select=displayName,jobTitle", "v1.0")
        res = self.session.get(url)
        if res.status_code == 200:
            res = res.json()
            return [res['displayName'], res['jobTitle']
                    if res['jobTitle'] else "Not Available", email]
        else:
            return ["Not Available" for i in range(3)]

    # TODO add the country selection so users form different countries get
    # different timezones
    async def set_autoreply(self, email: str, message: str, startdate: str, enddate: str) -> bool:
        """Sets an autoreply for an employee specified in the email argument

        Args:
            email (str): email of an employee we are setting the autoreply for
            message (str): autoreply body
            startdate (str): start date for the autoreply. Should be formatted like "%Y-%m-%d"
            enddate (str): end date for the autoreply. Should be formatted like "%Y-%m-%d"

        Returns:
            bool: True if the autoreply was succesfully set, False otherwise
        """
        url = await self._api_endpoint(f"/users/{email}/mailboxSettings", "v1.0")
        payload = {
            "automaticRepliesSetting": {
                "status": "scheduled",
                "internalReplyMessage": message,
                "scheduledStartDateTime": {
                    "dateTime": startdate + "T07:00:00",
                    "timeZone": "Russian Standard Time"
                },
                "scheduledEndDateTime": {
                    "dateTime": enddate + "T23:59:00",
                    "timeZone": "Russian Standard Time"
                }
            }
        }
        response = self.session.patch(url=url, json=payload)
        if response.status_code == 200:
            return True
        else:
            print(response.status_code, response.json())
            return False

    async def set_oof(self, email: str, subject: str, startdate: str, enddate: str) -> bool:
        """Sets an "out of office" status between the startdate and enddate arguments
         for an employee specified in the email argument

        Args:
            email (str): email of an employee we are setting the status for
            subject (str): reason of the status, e.g. "vacation, sick leave" etc
            startdate (str): Should be formatted like "%Y-%m-%d"
            enddate (str): Should be formatted like "%Y-%m-%d"

        Returns:
            bool: True if the status has been succesfully set, False otherwise
        """
        url = await self._api_endpoint(f"/users/{email}/events", "v1.0")
        payload = {
            "subject": subject,
            "start": {
                "dateTime": startdate + "T00:00:00",
                "timeZone": "Russian Standard Time"
            },
            "end": {
                "dateTime": enddate + "T00:00:00",
                "timeZone": "Russian Standard Time"
            },
            "showAs": "oof",
            "isAllDay": True
        }
        response = self.session.post(url=url, json=payload)
        if response.status_code == 201:
            return True
        else:
            return False
