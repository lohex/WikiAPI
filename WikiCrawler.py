"""
WikiAPI
~~~~~~~~~~~~~~~~

This API defines the interface to Wikipedia.

Author: Lorenz Hexemer
"""

import re
import os
import hashlib
import dill
import yaml
from typing import List, Dict

from collections import defaultdict
from IPython.display import clear_output

from .WikiCategory import WikiCategory
from .WikiArticle import WikiArticle


class WikiCrawler:

    def __init__(self, start: str = None, ) -> None:
        """
        Initialize the WikiCrawler.

        Args:
            start (str, optional): Initial category to start crawling from.
             Defaults to None.
        """
        self.setPrintMode()
        self._initVariables()

        if start is not None:
            self.startFrom(start)

    def startFrom(self, category: str) -> None:
        """
        Adds a category to the category_list which is used to scann for sub-
        categories by the followDeeper method.

        Args:
            category (str): Name of category to be added to the category_list.

        Returns:
            None
        """
        init_category = self.addCategory(category)
        self.category_list[init_category.link] = category

    def _initVariables(self):
        """
        Helper function defining all variables. Can be used to reset an
        instance to an unused state.

        Args:
            None

        Returns:
            None
        """
        self.log = []
        self.keep_flag = False
        self.archive_path = None

        self.category_tree = defaultdict(list)
        dict_list = [
            "category_tree",
            "category_list",
            "article_list",
            "open_categories",
            "skip_categories",
            "skip_category_rules",
            "article_texts",
            "article_links",
            "article_categories",
            "article_hieracy_categories",
            "skip_articles",
            "skip_article_rules",
            "skip_article_categories",
            "skip_article_category_rules",
            "skipped_articles"
            ]
        for var in dict_list[1:]:
            setattr(self, var, {})

    def save(self, file_name: str) -> None:
        """
        Save the state of the crawler to a file.

        Args:
            file_name (str): The name of the file to save the state to.

        Returns:
            None
        """
        self.save_path = file_name
        child_vars = []
        for var in dir(self):
            ref = getattr(self, var)
            if "__" in var or callable(ref):
                continue
            child_vars.append(var)

        with open(file_name, 'wb') as fp:
            dill.dump(child_vars, fp)
            for var in child_vars:
                dill.dump(getattr(self, var), fp)

    @staticmethod
    def load(file_name: str) -> 'WikiCrawler':
        """
        Load the state of the crawler from a file.

        Args:
            file_name (str): The name of the file to load the state from.

        Returns:
            WikiCrawler: The loaded instance of the WikiCrawler.
        """
        empty = WikiCrawler()
        with open(file_name, 'rb') as fp:
            child_vars = dill.load(fp)
            for var in child_vars:
                loaded = dill.load(fp)
                setattr(empty, var, loaded)
        return empty

    def skipRulesFromYaml(self, file_path: str) -> None:
        """
        Use a yml file to define the skip-rules which are used to ignore
        categories or articles.

        Args:
            file_path (str): Path to the yml file that defines the skip-rules.

        Returns:
            None
        """
        with open(file_path) as fileStream:
            loaded_rules = yaml.safe_load(fileStream)
        for rule_type, rule_set in loaded_rules.items():
            add_mode = f'add{rule_type}'
            if add_mode in dir(self):
                getattr(self, add_mode)(rule_set)

            add_mode = f'set{rule_type}'
            if add_mode in dir(self):
                getattr(self, add_mode)(rule_set)

    def addCategory(self, name: str, link: str = None, root: List[str] = None
                    ) -> 'WikiCategory':
        """
        Add a category to the crawler and crawl its subcategories and pages.

        Args:
            name (str): Name of the category.
            link (str, optional): Link to the category. Defaults to None.
            root (List[str], optional): Root categories. Defaults to None.

        Returns:
            WikiCategory: The newly added category.
        """
        new_category = WikiCategory(name, link=link)
        self.category_tree[new_category.link] = [''] if root is None else root

        sub_categories = new_category.getSubCategories()
        self.category_list.update(sub_categories)
        self.open_categories.update(sub_categories)
        for new_link in sub_categories.keys():
            self.category_tree[new_link].append(new_category.link)

        category_pages = new_category.getPages()
        self.article_list.update(category_pages)
        for new_link in category_pages.keys():
            self.category_tree[new_link].append(new_category.link)

        info_message = (
            f"{new_category.name}:"
            f" {len(sub_categories)} categories,"
            f" {len(category_pages)} pages."
        )
        self.print(info_message)
        self.printStatus()
        return new_category

    def addSkipCategoryExplicit(self, skip_categories: List[str]) -> None:
        """
        Adds categories to the list of explicitly skipped categories.

        Args:
            skip_categories (List[str]):
                A list of category names to be skipped.
        """
        self.skip_categories = set(skip_categories)

    def addSkipCategoryRulebased(self, skip_rules: List[str]) -> None:
        """
        Adds rule-based skipping rules for categories.

        Args:
            skip_rules (List[str]): A list of regular expression patterns.
                Categories matching these patterns will be skipped.
        """
        self.skip_category_rules = skip_rules

    def categoryIsValid(self, name: str) -> bool:
        """
        Checks if a category is valid for further analysis.

        Args:
            name (str): The name of the category.

        Returns:
            bool: True if the category is valid, False otherwise.
        """
        if name in self.skip_categories:
            self.print(f'\t{name} skipped explicitly.')
            return False

        for rule in self.skip_category_rules:
            if re.match(rule, name):
                self.print(f'\t{name} skipped by rule.')
                return False

        return True

    def followDeeper(self, levels: int = 1) -> None:
        """
        Recursively explores subcategories for a specified number of levels.

        Args:
            levels (int): The number of levels to explore.

        Returns:
            None
        """
        for lvl in range(levels):
            process_categories = self.open_categories.copy()
            self.open_categories = {}
            n_total = len(process_categories)
            message = (
                f"{len(process_categories)} categories "
                "to analyze for subcategories:"
            )
            self.print(message)
            for i, (link, name) in enumerate(process_categories.items()):
                if self.categoryIsValid(name):
                    root = self.category_tree[link]
                    self.print("%3d/%3d: " % (i+1, n_total), keep=True)
                    self.addCategory(name, link, root)

    def retrieveCategories(self, article):
        """
        Collect all categories an article belongs to,
          including inhereted categories.

        Args:
            artilce (str): name of article.

        Returns:
            list of categories (str)
        """
        article_link = [
            link for link, name in self.article_list.items()
            if name == article
        ][0]
        ancestor_generation = set(self.category_tree[article_link])
        ancestors = set([])
        while any(a for a in ancestor_generation) > 0 and len(ancestors) < 100:
            next_ancestor_generation = set([])
            for parent in ancestor_generation:
                next_ancestor_generation.update(self.category_tree[parent])
            next_ancestor_generation.difference_update(ancestors)
            ancestor_generation = next_ancestor_generation
            ancestors.update(ancestor_generation)
        categories = [
            self.category_list[a].replace('Category:', '')
            for a in ancestors
            if not a == ''
        ]
        return categories

    def addSkipArticleExplicit(self, skip_articles: List[str]) -> None:
        """
        Add categories to the list of categories that should be
          explicitly skipped.

        Args:
            skip_categories (List[str]): List of category names to skip.

        Returns:
            None
        """
        self.skip_articles = set(skip_articles)

    def addSkipArticleRulebased(self, skip_rules: List[str]) -> None:
        """
        Add rules for skipping articles based on regular expressions.

        Args:
            skip_rules (List[str]): List of regular expression rules
                for skipping articles.

        Returns:
            None
        """
        self.skip_article_rules = skip_rules

    def addSkipArticleCategoryBased(self, skip_categories: List[str]) -> None:
        """
        Add categories for skipping articles based on explicit category names.

        Args:
            skip_categories (List[str]): List of category names
                to skip articles.

        Returns:
            None
        """
        self.skip_article_categories = skip_categories

    def addSkipArticleCategoryRuleBased(self, skip_rules: List[str]) -> None:
        """
        Add rules for skipping articles based on regular expressions
            for category names.

        Args:
            skip_rules (List[str]): List of regular expression rules for
            skipping articles based on categories.

        Returns:
            None
        """
        self.skip_article_category_rules = skip_rules

    def articleIsValid(self, name: str) -> bool:
        """
        Check if an article is valid based on explicit skipping and
          rule-based skipping.

        Args:
            name (str): Name of the article.

        Returns:
            bool: True if the article is valid, False if it should be skipped.
        """
        if name in self.skip_articles:
            self.print(f'\t{name} skipped explicitly.')
            self.skipped_articles.append[name] = f'Explicit: {name}'
            return False

        for rule in self.skip_article_rules:
            if re.match(rule, name):
                self.print(f'\t{name} skipped by rule.')
                self.skipped_articles.append[name] = f'Rule: {rule}'
                return False

        return True

    def articleCategoriesAreValid(self,
                                  name: str,
                                  article_categories: Dict[str, str]
                                  ) -> bool:
        """
        Check if the categories of an article are valid based on explicit
            category skipping and rule-based category skipping.

        Args:
            name (str): Name of the article.
            article_categories (Dict[str, str]): Dictionary of article
              categories.

        Returns:
            bool: True if the article categories are valid, False if the
              article should be skipped.
        """
        for category in article_categories.values():
            if category in self.skip_article_categories:
                self.print(f'\t{name} skipped by explict category.')
                self.skipped_articles[name] = f'Category: {category}'
                return False
            for rule in self.skip_article_category_rules:
                if re.match(rule, category):
                    self.print(f'\t{name} skipped by category rule.')
                    self.skipped_articles[name] = f'Rule: {rule}'
                    return False

        return True

    def setArchivePath(self, archive_path: str) -> None:
        """
        Set the path to the archive directory where meta information
          and article texts will be saved.

        Args:
            archive_path (str): Path to the archive directory.
        """
        self.archive_path = archive_path
        if not os.path.isdir(self.archive_path):
            os.mkdir(self.archive_path)

    def collectArticles(self, links: bool = True, text: bool = True,
                        categories: bool = True, limit: int = None,
                        save_intervall: int = 10) -> None:
        """
        Collect articles based on specified options.

        Args:
            links (bool, optional): Whether to collect article links.
                Defaults to True.
            text (bool, optional): Whether to collect article text.
                Defaults to True.
            categories (bool, optional): Whether to collect article categories.
                Defaults to True.
            limit (int, optional): Maximum number of articles to collect.
                Defaults to None.

        Returns:
            None
        """
        if self.archive_path is not None:
            artilces_loaded = self.readIndex()
        else:
            artilces_loaded = self.article_texts.keys()

        articles_to_collect = set(self.article_list) - set(artilces_loaded)
        n_collect = len(articles_to_collect)
        limit = n_collect if limit is None else limit
        self.print(f'{limit} articles to collect:')
        for i, article_link in enumerate(articles_to_collect):
            if i == limit:
                break

            article_is_valid = True
            name = self.article_list[article_link]
            if not self.articleIsValid(name):
                article_is_valid = False

            try:
                page = WikiArticle(name, article_link)
            except Exception as e:
                self.print(f"Article {name} was not found at {article_link}!")
                self.broken_links.append(f"Link broken: {article_link}:" + e)
                article_is_valid = False

            article_categories = page.getHeadCategories()
            if not self.articleCategoriesAreValid(name, article_categories):
                article_is_valid = False

            if article_is_valid:
                meta_info = self.collectMetaInfo(
                    name,
                    article_link,
                    article_categories,
                    categories
                )
                if links:
                    page_links = page.getLinks()
                    meta_info.update({
                        'Article_links': list(page_links.keys())
                    })
                if text:
                    article_text = page.getText()
                    self.saveArticle(article_link, article_text)

                self.writeMetaInfo(article_link, meta_info)
                self.print("%4d/%4d collecting %s" % (i+1, n_collect, name))

            if hasattr(self, 'save_path') and (i+1) % save_intervall == 0:
                self.save(self.save_path)

    def readIndex(self) -> list:
        """
        Read articles saved in path.
        """
        links = []
        with open(f"{self.archive_path}/index.txt", "r") as fp:
            for line in fp:
                _, link = line.strip().split('=')
                links.append(link)
        return links

    def collectMetaInfo(
            self, name, article_link,
            article_categories, categories
            ) -> dict:
        """
        """
        meta_info = {'Article': name, 'Link': article_link}
        if categories:
            hierachical_categories = self.retrieveCategories(name)
            meta_info.update({
                'Hierachical_categories': hierachical_categories
            })
            category_link = [
                c.replace("Category:", "")
                for c in article_categories.values()
                if ' stubs' not in c
            ]
            meta_info.update({'Article_categories': category_link})
        return meta_info

    def writeMetaInfo(self,
                      article_link: str,
                      meta_infos: Dict[str, List[str]]
                      ) -> None:
        """
        Write meta information to a file.

        Args:
            article_link (str): Link of the article.
            meta_infos (Dict[str, List[str]]): Meta information dictionary.

        Returns:
            None
        """
        if "Article_categories" in meta_infos.keys():
            self.article_categories[article_link] = \
                  meta_infos["Article_categories"]
        if "Hierachical_categories" in meta_infos.keys():
            self.article_hieracy_categories[article_link] = \
                meta_infos["Hierachical_categories"]
        if "Article_links" in meta_infos.keys():
            self.article_links[article_link] = meta_infos["Article_links"]

        if self.archive_path is not None:
            identifyer = hashlib.md5(article_link.encode('utf-8')).hexdigest()
            with open(f"{self.archive_path}/{identifyer}.meta", "w") as fp:
                for name, value in meta_infos.items():
                    if isinstance(value, list):
                        value = ", ".join(value)

                    print(f"{name}: {value}", file=fp)

    def saveArticle(self, article_link: str, article_text: str) -> None:
        """
        Save article text to a file.

        Args:
            article_link (str): Link of the article.
            article_text (str): Article text.

        Returns:
            None
        """
        save_link = article_text if self.archive_path is None else True
        self.article_texts[article_link] = save_link

        if self.archive_path is not None:
            identifyer = hashlib.md5(article_link.encode('utf-8')).hexdigest()
            with open(f"{self.archive_path}/{identifyer}.txt", "w") as fp:
                for text_line in article_text:
                    print(text_line, file=fp)

            with open(f"{self.archive_path}/index.txt", "a") as fp:
                print(f'{identifyer}={article_link}')

    def printCategoryHierachy(self, node: str, max_level: int = 1) -> None:
        """
        Print the hierarchy of categories starting from a specific node.

        Args:
            node (str): The category node from which to start printing.
            max_level (int, optional): The maximum level of hierarchy to print.
                Defaults to 1.

        Returns:
            None
        """
        self._printChildNodes('', level=1, max_level=max_level)

    def _printChildNodes(self, node: str, level: int, max_level: int) -> None:
        """
        Print child nodes of a given category node in a hierarchical manner.

        Args:
            node (str): The category node to print children for.
            level (int): The current level of hierarchy.
            max_level (int): The maximum level of hierarchy to print.
        """
        children = [
            link for link, roots in self.category_tree.items()
            if node in roots and "/wiki/Category:" in link
        ]
        for child in children:
            child_articles = [
                link for link, roots in self.category_tree.items()
                if child in roots and "/wiki/Category:" not in link
            ]
            child_categories = [
                link for link, roots in self.category_tree.items()
                if child in roots and "/wiki/Category:" in link
            ]
            print(
                '\t'*(level-1) +
                self.category_list[child].replace('Category:', '') +
                f"({len(child_categories)} Categories,"
                f"{len(child_articles)} Articles)"
            )
            if max_level >= level:
                self._printChildNodes(
                    child,
                    level=level+1,
                    max_level=max_level
                )

    def printStatus(self) -> None:
        """
        Print the current status of the crawler, including the number of
          pages and categories.
        """
        print(
            f"{len(self.article_list)} pages"
            f"from {len(self.category_list)} categories."
        )

    def setPrintMode(self,
                     print_last: bool = True,
                     logfile: str = None
                     ) -> None:
        """
        Set the print mode for the crawler.

        Args:
            print_last (bool): Whether to print the last message
                without line break.
            logfile (str): The path to the log file.

        Returns:
            None
        """
        self.print_last = print_last
        self.logfile = logfile

    def print(self, message: str, keep: bool = False) -> None:
        """
        Print a message.

        Args:
            message (str): The message to be printed.
            keep (bool): Whether to keep the message without line break.

        Returns:
            None
        """
        self.log.append(message)
        line_break = "" if keep else "\n"
        if self.logfile is not None:
            with open(self.logfile, 'a') as fp:
                print(message, file=fp, end=line_break)

        if self.print_last and not self.keep_flag:
            clear_output(True)

        if self.logfile is None or self.print_last:
            print(message, end=line_break)
        self.keep_flag = keep

    def printLog(self) -> None:
        """
        Print the log entries.

        Returns:
            None
        """
        for entry in self.log:
            print(entry)

    def deleteFiles(self) -> bool:
        """
        Delte all files from archive.

        Returns:
            True if files were delted
            False if abborted.
        """
        question = (
            'Do you really want to delte alle files?'
            'Type "yes" to confirm:'
        )
        want_del = input(question)
        if want_del not in ["y", "Y", "yes", "Yes"]:
            return False

        if os.path.exists(self.logfile):
            os.unlink(self.logfile)

        if os.path.exists(self.archive_path):
            for file in os.scandir(self.archive_path):
                os.unlink(file.path)
            os.rmdir(self.archive_path)
        return True
