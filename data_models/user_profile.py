from typing import List


class UserProfile:
    """Class used to store user data as part of a user_state.

    Attributes:
    email (str): User's email. Defaults to None.
    phone (str): User's phone number (mobile). Defaults to None.
    names (List[str]): names of employees who can cover for the user while they are out of office.
    Defaults to None.
    areas (List[str]): areas of expertise associated with employees covering for the user. Defaults to None.
    lang (str): target language of the user. Defaults to "RU".
    """

    def __init__(
            self,
            email: str = None,
            phone: str = None,
            names: List[str] = None,
            areas: List[str] = None,
            lang: str = "RU"):
        """inits the UserProfile instance

        Args:
            email (str, optional): User's email. Defaults to None.
            phone (str, optional): User's phone number (mobile). Defaults to None.
            names (List[str], optional): names of employees who can cover for the user while they are out of office.
            Defaults to None.
            areas (List[str], optional): areas of expertise associated with employees covering for the user. Defaults to None.
            lang (str, optional): target language of the user. Defaults to "RU".
        """
        self.email: str = email
        self.phone: str = phone
        self.names: List[str] = names
        self.areas: List[str] = areas
        self.lang: str = lang
