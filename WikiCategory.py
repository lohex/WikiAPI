"""
WikiAPI
~~~~~~~~~~~~~~~~

This API defines the interface to Wikipedia.

Author: Lorenz Hexemer
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List


class WikiCategory:
    """
    Represents a Wikipedia category.

    Attributes:
        name (str): The name of the category.
        link (str): The link to the category page on Wikipedia.
        exists (bool) Boolsch flag if the category was found.
        doc (BeautifulSoup): Parsed HTML document of the category page.
        sub_categories (dict): Dictionary of subcategories' links and titles.
        head_categories (dict): Dictionary containing  upstream
          categories' links and titles.
        pages (dict): Dictionary of page links and titles.

    Methods:
        __init__(self, name, link=None, load=True):
            Initializes a WikiCategory instance.

        getSubCategories(self) -> dict:
            Retrieves subcategories of the category.

        getHeadCategories(self) -> dict:
            Retrieves head categories of the category.

        getPages(self) -> dict:
            Retrieves pages in the category.
    """
    BASE_URL = "https://en.wikipedia.org"
    CATEGORY_URL_PREFIX = "/wiki/"
    MAX_RETRY = 3

    def __init__(self, name: str, link: str = None, load: bool = True) -> None:
        """
        Initializes a WikiCategory instance.

        Args:
            name (str): The name of the category.
            link (str, optional): The link to the category page on Wikipedia.
              Defaults to None.
            load (bool, optional): Whether to load the category page.
              Defaults to True.
        """
        if not re.match('^Category:.*', name):
            name = f'Category:{name}'
        self.name = name
        if link is None:
            link = self.CATEGORY_URL_PREFIX + self.name.replace(' ', "_")
        self.link = link
        self.doc = None
        if load:
            self._requestCategory()

    @classmethod
    def from_link(cls, link: str, load: bool = True) -> 'WikiCategory':
        """
        Creates a WikiCategory instance from a given URL link.

        Args:
            link (str): The URL link to the category page.
            load (bool): Whether to immediately load category data.

        Returns:
            The created WikiCategory instance.
        """
        new_category = cls('temp_name', link, load)
        if load:
            new_category.name = new_category.doc.find(
                'h1', class_='firstHeading').text
        return new_category

    @classmethod
    def from_name(cls, name: str, load: bool = True) -> 'WikiCategory':
        """
        Creates a WikiCategory instance from a given category name.

        Args:
            name (str): The name of the category.
            load (bool): Whether to immediately load category data.

        Returns:
            The created WikiCategory instance.
        """
        name = name if re.match('^Category:.*', name) else 'Category:' + name
        link = cls.CATEGORY_URL_PREFIX + name.replace(' ', "_")
        return cls.from_link(link, load)

    @staticmethod
    def _make_request(url: str) -> requests.Response:
        """
        Makes an HTTP request to the given URL.

        Args:
            url (str): The URL to request.

        Returns:
            The HTTP response.
        """
        for retry in range(WikiCategory.MAX_RETRY):
            try:
                response = requests.get(url)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if retry < WikiCategory.MAX_RETRY - 1:
                    continue
                raise e

    def _requestCategory(self) -> None:
        """
        Requests and parses the category page.
        """
        response = self._make_request(self.BASE_URL + self.link)
        self.doc = BeautifulSoup(response.text, 'html.parser')
        empty = self.doc.find('div', id='mw-category-empty')
        self.exists = empty is None
        if not self.exists:
            raise Exception(f'The category "{self.name}" does not exist.')

    def getSubCategories(self) -> Dict[str, str]:
        """
        Retrieves subcategories of the category.

        Returns:
            dict: Dictionary containing subcategory links and titles.
        """
        sub_category_links = self.doc.find('div', id="mw-subcategories")
        if sub_category_links is None:
            return {}

        sub_categories = {
            s.attrs['href']: s.attrs['title']
            for s in sub_category_links.find_all('a')
        }
        return sub_categories

    def getHeadCategories(self) -> Dict[str, str]:
        """
        Retrieves head categories of the category.

        Returns:
            dict: Dictionary containing head category links and titles.
        """
        head_category_links = self.doc.find(
            'div',
            id="mw-normal-catlinks"
        ).ul.find_all('a')
        head_categories = {
            s.attrs['href']: s.attrs['title']
            for s in head_category_links
        }
        return head_categories

    def getPages(self) -> Dict[str, str]:
        """
        Retrieves pages in the category.

        Returns:
            dict: Dictionary containing page links and titles.
        """
        self.pages = {}
        next_link = self._loadPageLinks()
        while len(next_link) > 0:
            response = self._make_request(self.BASE_URL + next_link[0])
            self.doc = BeautifulSoup(response.text, 'html.parser')
            next_link = self._loadPageLinks()
        return self.pages

    def _loadPageLinks(self) -> List[str]:
        """
        Loads page links from paginated view.

        Returns:
            list: List of links to the next page.
        """
        mw_pages = self.doc.find("div", id="mw-pages")
        if mw_pages is None:
            return []

        self.pages.update({
            p.a.attrs['href']: p.a.attrs['title']
            for p in mw_pages.find_all("li")
        })
        next_page_links = mw_pages.find_all("a")
        next_link = [
            a.attrs['href']
            for a in next_page_links
            if 'next page' in a.text
        ]
        return next_link
