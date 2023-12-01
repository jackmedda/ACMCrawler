#%%
import os
import math
import json
import time
import argparse

import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


class ACMScrapingCheckpoint(object):

    CKPT_URL_KEY = "ckpt"
    CKPT_PAGE_EXHAUSTED = "query_completed"

    def __init__(self, path='acm_papers_info.ckpt'):
        self.path = path

        if os.path.exists(self.path):
            with open(self.path, 'r') as ckpt_f:
                self._ckpt = json.load(ckpt_f)
        else:
            self._ckpt = {}

    @property
    def checkpoint(self):
        return self._ckpt

    def get_checkpoint_url(self, query, conf_id):
        if query in self._ckpt:
            if self.CKPT_URL_KEY in self._ckpt[query][conf_id]:
                return self._ckpt[query][conf_id][self.CKPT_URL_KEY]

        return None

    def save_checkpoint(self, acm_papers_info, query, conf_id):
        next_url = get_next_page()
        if next_url is not None:
            acm_papers_info[query][conf_id][self.CKPT_URL_KEY] = next_url.get_attribute("href")
        else:
            acm_papers_info[query][conf_id][self.CKPT_URL_KEY] = self.CKPT_PAGE_EXHAUSTED

        with open(self.path, 'w') as ckpt_f:
            json.dump(acm_papers_info, ckpt_f, indent=4)
        self._ckpt = acm_papers_info


class ExhaustedPapersException(Exception):
    def __repr__(self):
        return "There are no other pages to extract papers from."

    def __str__(self):
        return self.__repr__()


def selector(elem_name):
    elems = {
        "no_results": (By.XPATH, "//div[@class='search-result__no-result']"),
        "cookies": (By.ID, "CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll"),
        "results_hits": (By.XPATH, '//span[@class="hitsLength"]'),
        "next_page": (By.XPATH, './/a[@title="Next Page"]'),
        "papers_list": (By.XPATH, '//*[@id="skip-to-main-content"]/main/div[1]/div/div[2]/div/ul'),
        "inner_papers": (By.XPATH, 'li[contains(@class, "issue-item-container")]'),
        # paper_INFO or authors_list => needs to be used on a WebElement of a paper
        "paper_pub_date": (By.XPATH, './/div[contains(@class, "bookPubDate")]'),
        "paper_title": (By.XPATH, './/h5[@class="issue-item__title"]'),
        "paper_short_abstract": (By.XPATH, './/div[contains(@class, "issue-item__abstract")]/p'),
        "paper_short_abstract_more": (By.XPATH, './/div[contains(@class, "issue-item__abstract")]/p/span'),
        "paper_venue": (By.XPATH, './/div[@class="issue-item__detail"]/a/span[@class="epub-section__title"]'),
        "paper_doi": (By.XPATH, './/div[@class="issue-item__detail"]/span/a[contains(@class, "issue-item__doi")]'),
        "paper_type": (By.XPATH, './/div[contains(@class, "issue-item__citation")]/div[@class="issue-heading"]'),
        "paper_citations": (By.XPATH, './/li[@class="metric-holder"]//span[@class="citation"]'),
        "paper_downloads": (By.XPATH, './/li[@class="metric-holder"]//span[@class="metric"]'),
        "paper_free_access": (By.XPATH, './/div[contains(@class, "issue-item__footer-links")]/ul[2]/li[1]'),
        "authors_list": (By.XPATH, './/ul[@aria-label="authors"]'),
        # inner_authors => needs to be used on a WebElement of an authors_list
        "inner_authors": (By.XPATH, 'li'),
        # single_author => needs to be used on a WebElement of an inner_authors
        "single_author": (By.XPATH, 'a'),
        # authors_INFO => needs to be used on a WebElement of a single_author
        "authors_count_list": (By.XPATH, './/li[@class="count-list"]/a'),
        "author_profile_mail": (By.XPATH, './/a[@data-title="Author’s Email"]')
    }

    return elems[elem_name]


def remove_cookies_dialog():
    try:
        driver.find_element(*selector("cookies")).click()
    except NoSuchElementException:
        pass


def get_next_page():
    try:
        next_page_elem = driver.find_element(*selector("next_page"))
    except NoSuchElementException:
        return None

    return next_page_elem


def next_page():
    try:
        next_page_arrow = driver.find_element(*selector("next_page"))
        webdriver.ActionChains(driver).scroll_to_element(next_page_arrow).perform()
        next_page_arrow.click()
    except NoSuchElementException:
        raise ExhaustedPapersException()


def extract_author_info(author):
    author_info = dict.fromkeys(["author_name", "author_ID", "author_email"])

    if author.text == "(Less)":
        return None

    author_info["author_name"] = author.text

    profile_url = author.get_attribute("href")
    if "profile" in profile_url:
        author_info["author_ID"] = os.path.basename(profile_url)

        if author_info["author_ID"] not in visited_authors:
            driver.get(profile_url)
            try:
                author_info["author_email"] = driver.find_element(*selector("author_profile_mail")).get_attribute("href")
                author_info["author_email"] = author_info["author_email"].replace('mailto:', '')
            except NoSuchElementException:
                author_info["author_email"] = None
            driver.back()

            visited_authors[author_info["author_ID"]] = (author_info["author_name"], author_info["author_email"])
        else:
            author_info["author_email"] = visited_authors[author_info["author_ID"]][1]
    else:
        author_info["author_ID"] = author_info["author_name"]

    return author_info


def extract_authors(authors_list):
    try:
        authors_list.find_element(*selector("authors_count_list")).click()
    except NoSuchElementException:
        pass  # the list of authors is not folded

    inner_authors = authors_list.find_elements(*selector("inner_authors"))
    authors_info = []
    for author in inner_authors:
        author_info = extract_author_info(author.find_element(*selector("single_author")))
        if author_info is not None:
            authors_info.append(author_info)

    # update visited authors
    with open(args.authors_info_file, 'w') as v_auth_f:
        json.dump(visited_authors, v_auth_f, indent=4)

    return authors_info


def extract_paper_info(paper):
    paper_info = dict.fromkeys([
        "paper_pub_month",
        "paper_pub_year",
        "paper_title",
        "paper_short_abstract",
        "paper_venue",
        "paper_doi",
        "paper_type",  # short paper, research article
        "paper_citations",
        "paper_downloads",
        "paper_free_access",
        "authors_info",
    ])

    paper_pub_date = paper.find_element(*selector("paper_pub_date")).text
    paper_info["paper_pub_month"], paper_info["paper_pub_year"] = paper_pub_date.split()

    paper_info["paper_title"] = paper.find_element(*selector("paper_title")).text

    paper_short_abstract = None
    try:
        paper_short_abstract = paper.find_element(*selector("paper_short_abstract"))
    except NoSuchElementException:
        paper_info["paper_short_abstract"] = ""

    if paper_short_abstract is not None:
        try:
            paper.find_element(*selector("paper_short_abstract_more")).click()
            paper_info["paper_short_abstract"] = paper_short_abstract.text.replace(' ...', '')
        except NoSuchElementException:
            paper_info["paper_short_abstract"] = paper_short_abstract.text.replace(' ...', '').replace('…', '')

    try:
        paper_info["paper_venue"] = paper.find_element(*selector("paper_venue")).text.split(':')[0]
    except NoSuchElementException:  # could be raised if the page includes proceedings entries
        paper_type = paper.find_element(*selector("paper_type")).text
        if "PROCEEDING" in paper_type.upper():
            paper_info["paper_venue"] = ""
        else:
            raise NoSuchElementException("Problem with paper venue")

    try:
        paper_doi = paper.find_element(*selector("paper_doi"))
        paper_info["paper_doi"] = '/'.join(paper_doi.get_attribute("href").split('/')[-2:])
    except NoSuchElementException:  # could be raised if the page includes proceedings entries
        paper_type = paper.find_element(*selector("paper_type")).text
        if "PROCEEDING" in paper_type.upper():
            paper_info["paper_doi"] = ""
        else:
            print(
                "Problem with paper DOI for paper: ", paper_info["paper_title"], ". Some papers do not include the DOI."
            )
            paper_info["paper_doi"] = None

    paper_info["paper_type"] = paper.find_element(*selector("paper_type")).text

    try:
        paper_info["paper_citations"] = paper.find_element(*selector("paper_citations")).text
    except NoSuchElementException:
        paper_info["paper_citations"] = None

    try:
        paper_info["paper_downloads"] = paper.find_element(*selector("paper_downloads")).text
    except NoSuchElementException:
        print(
            "Problem with paper Downloads for paper: ", paper_info["paper_title"],
            "!!! This can happen if the paper entry was pre-uploaded on ACM before its release"
        )
        paper_info["paper_downloads"] = None

    try:
        paper_free_access = paper.find_element(*selector("paper_free_access"))
        paper_info["paper_free_access"] = paper_free_access.get_attribute("aria-label") == "View online with eReader"
    except NoSuchElementException:  # could be raised if the page includes proceedings entries
        paper_type = paper.find_element(*selector("paper_type")).text
        if "PROCEEDING" in paper_type.upper():
            paper_info["paper_free_access"] = None
        else:
            print(
                "Problem with paper Free Access Check for paper: ", paper_info["paper_title"],
                ". This can happen if the paper entry was pre-updated on ACM before its release"
            )
            paper_info["paper_free_access"] = None

    try:
        authors_list = paper.find_element(*selector("authors_list"))
        paper_info["authors_info"] = extract_authors(authors_list)
    except NoSuchElementException:  # could be raised for proceedings with image
        paper_type = paper.find_element(*selector("paper_type")).text
        if "PROCEEDING" in paper_type.upper():
            paper_info["authors_info"] = None
        else:
            raise NoSuchElementException("Problem with paper authors list")

    return paper_info


def extract_inner_papers(ps_list):
    inner_papers_info = []
    inner_papers = ps_list.find_elements(*selector("inner_papers"))
    for paper in tqdm.tqdm(inner_papers, desc="Extracting papers info",
                           position=1, leave=False, ncols=80, colour="blue"):
        webdriver.ActionChains(driver).scroll_to_element(paper).perform()
        inner_papers_info.append(extract_paper_info(paper))

    return inner_papers_info


def extract_papers():
    papers_list = driver.find_element(*selector("papers_list"))
    return extract_inner_papers(papers_list)


def load_page(query, ckpt_key, c_id):
    ckpt_url = ckpt_manager.get_checkpoint_url(ckpt_key, c_id)
    if ckpt_url == ckpt_manager.CKPT_PAGE_EXHAUSTED:
        print(f"All the papers with query `{ckpt_key}` and conf `{c_id}` have already been extracted!")
        return None
    elif ckpt_url is not None:
        driver.get(ckpt_url)
        return ckpt_url
    else:
        driver.get(query)
        return query


def build_query(query_temp, **kwargs):
    q = kwargs.pop("query")
    concept_id = kwargs.pop("concept_id")

    return query_temp.format(query=q, concept_id=concept_id)


def build_query_template(q_templates, q_temp, year_attrs=None, page_attrs=None):
    q_temp = q_templates[q_temp]
    if year_attrs is not None:
        year_attrs_temp = q_templates["after_before_year_attrs"]
        q_temp += year_attrs_temp.format(**dict(zip(["after_year", "before_year"], year_attrs)))
    if page_attrs is not None:
        page_crawling_attrs_temp = q_templates["page_crawling_attrs"]
        q_temp += page_crawling_attrs_temp.format(**dict(zip(["page_size", "start_page"], page_attrs)))

    return q_temp


def main(queries, query_temp, c_ids_list, page_size=20):
    acm_info = ckpt_manager.checkpoint

    for q in queries:
        if q not in acm_info:
            acm_info[q] = {}
        print("Using query:", q)
        for c_id in c_ids_list:
            if c_id not in acm_info[q]:
                acm_info[q][c_id] = {"papers": []}
            print("Parsing proceedings of:", c_id)

            query = build_query(
                query_temp,
                **dict(
                    query=q,
                    concept_id=concept_ids[c_id]
                )
            )

            current_page = load_page(query, q, c_id)
            if current_page is None:
                continue
            time.sleep(2)
            print(f"Starting from {current_page}")

            remove_cookies_dialog()

            results_hits = int(driver.find_element(*selector("results_hits")).text.replace(',', ''))
            print("# Results", results_hits)

            if "startPage" in current_page:
                initial_step = int(current_page.split("startPage=")[1].split('&')[0]) + 1
            else:
                initial_step = 0
            for _ in tqdm.tqdm(range(math.ceil(results_hits / page_size)), desc="Parsing page",
                               initial=initial_step, position=0, leave=False, ncols=80, colour="green"):

                try:
                    driver.find_element(*selector("no_results"))
                    print("\n" + "#" * 100)
                    print("ACM does not provide more than 2,000 results for each query and invites the user to "
                          "refine the query. This script then skips to the next concept ID.")
                    print("#" * 100, "\n")
                    break
                except NoSuchElementException:
                    pass

                page_papers_info = extract_papers()
                acm_info[q][c_id]["papers"].extend(page_papers_info)

                ckpt_manager.save_checkpoint(acm_info, q, c_id)
                if get_next_page() is not None:
                    next_page()
                else:
                    break


#%%
if __name__ == "__main__":
    """
    python main.py -q "graph AND retriev* OR graph AND recommend*" -yi 2020 2023
    python main.py -q "graph* OR gnn* OR rank* OR knowledge* OR topolog* OR social net* OR recomm* OR retriev*" -yi 2020 2023
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--queries', '-q', default="Graph", nargs="+")
    parser.add_argument('--query_template', '-qt', default="allfield_query")
    parser.add_argument('--concept_ids', '-cid', default="all", nargs='+')
    parser.add_argument('--year_interval', '-yi', default=None, nargs=2)
    parser.add_argument('--page_info', '-pi', help="page size & start page", default=None, nargs=2)
    parser.add_argument('--authors_info_file', '-aif', default="visited_authors_info.json")

    with open('concept_ids.json', 'r') as cids_file:
        concept_ids = json.load(cids_file)

    with open('query_templates.json', 'r') as qt_file:
        query_templates = json.load(qt_file)

    options = webdriver.EdgeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Edge(options=options)

    ckpt_manager = ACMScrapingCheckpoint()

    args, _ = parser.parse_known_args()
    args.queries = [args.queries] if not isinstance(args.queries, list) else args.queries
    args.concept_ids = list(concept_ids.keys()) if args.concept_ids == "all" else args.concept_ids
    args.year_interval = ["2020", "2023"] if args.year_interval is None else args.year_interval

    query_template = build_query_template(
        query_templates,
        args.query_template,
        year_attrs=args.year_interval,
        page_attrs=args.page_info
    )

    if os.path.exists(args.authors_info_file):
        with open(args.authors_info_file, 'r') as visited_f:
            visited_authors = json.load(visited_f)
    else:
        visited_authors = {}  # ID: e-mail

    try:
        main(
            args.queries,
            query_template,
            args.concept_ids,
            page_size=args.page_info[1] if args.page_info is not None else 20
        )
    except Exception as e:
        print(e)
        print("!!!! Error in page:", driver.current_url)
    driver.close()
