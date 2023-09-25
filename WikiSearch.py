"""
WikiAPI
~~~~~~~~~~~~~~~~

This API defines the interface to Wikipedia.

Author: Lorenz Hexemer
"""

import requests
from bs4 import BeautifulSoup
from WikiArticle import WikiArticle


class WikiSearch:
    BASE_URL = (
        "https://en.wikipedia.org/w/index.php?fulltext=1&"
        "limit=<chunk_size>&offset=<offset>&search="
    )

    def __init__(self, search_str: str) -> None:
        """
        """
        self.search_str = search_str
        self.results = []
        self.offset = 0

        self._load()
        self.getResultsInfo()

    def _load(self,
              increments_offset: int = 0,
              chunk_size: int = 20
              ) -> None:
        """
        Requests current paige containing search results.
        """
        self.offset += increments_offset
        query = self.BASE_URL
        query = query.replace('<offset>', str(self.offset))
        query = query.replace("<chunk_size>", str(chunk_size))
        response = requests.get(query + self.search_str)
        response.raise_for_status()
        self.doc = BeautifulSoup(response.text, 'html.parser')

    def getResultsInfo(self) -> None:
        """
        Gets information of total result count.
        """
        res_info = self.doc.find('div', class_="results-info")
        self.n_matches = int(res_info.attrs["data-mw-num-results-total"])
        print(f"Found {self.n_matches} results.")

    def grepMoreResults(self, chunk_size: int = 20) -> None:
        """
        Loads next page of results and extracts article links.
        """
        self._load(increments_offset=chunk_size)
        res_links = self.doc.find_all('div', class_="mw-search-result-heading")
        self.results += [
            WikiArticle(div.a.text, div.a.attrs["href"])
            for div in res_links
        ]

    def search_results(self,
                       limit: int = 100,
                       chunk_size: int = 20
                       ) -> WikiArticle:
        """
        Generator yielding an WikiArticle object for each iteration.
        Automatically loads next chung of articles when needed.

        Args:
            limit (int): Number of articles to return. Defautls to 100.

        Returns:
            Generator of WikiArtilces.
        """
        for at in range(self.n_matches):
            if at == limit:
                break
            if at == len(self.results):
                self.grepMoreResults(chunk_size=chunk_size)

            yield self.results[at]
