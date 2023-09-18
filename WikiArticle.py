"""
WikiAPI
~~~~~~~~~~~~~~~~

This API defines the interface to Wikipedia.

Author: Lorenz Hexemer
"""

import re
import requests
from bs4 import BeautifulSoup, Comment
from typing import Dict


class WikiArticle:
    BASE_URL = "https://en.wikipedia.org"
    ARTICLE_URL_PREFIX = "/wiki/"

    def __init__(self, name: str, link: str = None, load: bool = True) -> None:
        """
        Initializes a WikiArticle instance.

        Args:
            name (str): The name of the article.
            link (str): The URL link to the article page.
            load (bool  ): Whether to immediately load article data.
        """
        self.name = name
        self.link = link or self.ARTICLE_URL_PREFIX + self.name.replace(' ', "_")
        self.doc = None
        if load:
            self._load()

    def _load(self) -> None:
        """
        Loads the article content using an HTTP request.
        """
        response = requests.get(self.BASE_URL + self.link)
        response.raise_for_status()
        self.doc = BeautifulSoup(response.text, 'html.parser')

    def getHeadCategories(self) -> Dict[str, str]:
        """
        Retrieves the head categories of the article.

        Returns:
            A dictionary of head category URLs and titles.
        """
        link_area = self.doc.find('div', id="mw-normal-catlinks")
        if link_area:
            head_category_links = link_area.ul.find_all('a')
            head_categories = {
                s.attrs['href']: s.attrs['title']
                for s in head_category_links
                }
            return head_categories
        return {}

    def getLinks(self) -> Dict[str, str]:
        """
        Retrieves the links within the article.

        Returns:
            A dictionary of links URLs and titles.
        """
        all_a = self.doc.find("div", class_="mw-parser-output").find_all('a')
        links = {a.attrs['href']: a.attrs['title'] for a in all_a if 'href' in a.attrs and re.match("^/wiki/[^:]+$", a.attrs['href'])}
        return links
           
    def getText(self) -> str:
        """
        Retrieves the text content of the article.

        Returns:
            A dictionary of chapter titles and corresponding text.
        """
        content = self.doc.find("div", id="mw-content-text")
        title = self.doc.find('h1').text
        closing_span = content.find('span', string='See also')
        if not closing_span:
            closing_span = content.find('span', string='References')
        if not closing_span:
            closing_span = content.find('span', string='Further reading')
        if closing_span:
            closing_h2 = closing_span.find_parent('h2')
            if closing_h2:
                for sibling in closing_h2.find_all_next():
                    sibling.extract()
                closing_h2.extract()

        for table in content.find_all(['table','style','script','figure']):
            if table.name == 'figure':
                capt_text = table.text.strip()
                if len(capt_text) > 0:
                    table.replace_with("<CAP> " + capt_text + "\n")
            else:
                table.decompose()
        for div in content.find_all('div',class_="shortdescription"):
            div.replace_with("<DES> " + div.text + "\n")
        for img in content.find_all('div',class_="thumbcaption"):
            img.replace_with("<CAP> " + img.text + "\n")        
        for img in content.find_all('div',class_="thumbimage"):
            img.decompose()
        for math in content.find_all('span',class_="mwe-math-element"):
            math.replace_with("[[MATH_EXPRESSION]]")
        for edits in content.find_all('span',class_="mw-editsection"):
            edits.decompose()
        for refs in content.find_all('sup', class_="reference"):
            refs.decompose()
        for refs in content.find_all('div', role="note"):
            refs.decompose()
        for h_tag in content.find_all(['h2','h3','h4','h5']):
            tag_type = h_tag.name.upper().replace('H','HL')
            h_tag.replace_with(f"<{tag_type}> " + h_tag.text + "\n")
        for refs in content.find_all(['li','dd','dt']):
            refs.replace_with("<LST> " + refs.text + "\n")
        for refs in content.find_all('p'):
            refs.replace_with("<PAR> " + refs.text + "\n")
        for comment in content.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        text = f'<HL1> {title}\n' + content.text
        text = text.replace('[[MATH_EXPRESSION]]','<MATH>')
        text = re.sub("\<[A-Z]{3}>: \n","",text)
        text = re.sub("\s+\n","\n",text)
        text = re.sub("\n+","\n",text)
        text = re.sub("\r?\n([^<])"," $1",text)
        return [line for line in text.split('\n') if len(line) > 0]