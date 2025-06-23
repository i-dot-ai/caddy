import functools
import logging
import re
import time
from typing import List
from urllib.parse import urlparse, urljoin

import html2text
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from joblib import Memory
from langchain_community.document_loaders import AsyncHtmlLoader, DataFrameLoader
from tqdm.auto import tqdm

LOCATION = "./cachedir"
MEMORY = Memory(LOCATION, verbose=0)

load_dotenv()  # take environment variables from .env.

BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format=f"{BLUE}CADDY SCRAPER{RESET} | {GREEN}%(asctime)s{RESET} | {
            YELLOW
        }%(levelname)s{RESET} | {CYAN}%(message)s{RESET}",
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger(__name__)


logger = setup_logger()


def retry(num_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Retry decorator

    Parameters:
    num_retries (int): Number of times to retry before giving up
    delay (int): Initial delay between retries in seconds
    backoff (int): Factor by which the delay should be multiplied each retry
    exceptions (tuple): Exceptions to trigger a retry
    """

    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            _num_retries, _delay = num_retries, delay
            while _num_retries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    _num_retries -= 1
                    if _num_retries == 0:
                        raise
                    time.sleep(_delay)
                    _delay *= backoff
                    logger.warning(
                        f"Retrying {_num_retries} more times after exception: {e}"
                    )

        return wrapper_retry

    return decorator_retry


def remove_anchor_urls(urls):
    """
    Removes anchor URLs (URLs with a # followed by text at the end) from a list of URLs.
    Args:
        urls (list): A list of URLs (strings).
    Returns:
        list: A new list containing only the URLs that are not anchor URLs.
    """
    anchor_pattern = re.compile(r"#.*$")
    cleaned_urls = []

    for url in urls:
        if not anchor_pattern.search(url):
            cleaned_urls.append(url)

    return cleaned_urls


def crawl_url_batch(
    url_list: List,
    domain_description: str,
    div_classes: List = None,
    div_ids: List = None,
    authentication_cookie: str = None,
):
    """Takes a list of URLS, iterartively scrapes the content of each page, and returns a list of langchain Documents"""

    if authentication_cookie:
        cookie_dict = {"Cookie": authentication_cookie}
        loader = AsyncHtmlLoader(url_list, header_template=cookie_dict)
    else:
        loader = AsyncHtmlLoader(url_list)

    docs = loader.load()

    scraped_pages = []

    for page in tqdm(docs):
        current_url = page.metadata["source"]

        # get main section of page
        soup = BeautifulSoup(page.page_content, "html.parser")

        main_section_html = ""

        if div_ids:
            for div_id in div_ids:
                selected_div_id_html = soup.find("div", id=div_id)
                if selected_div_id_html:
                    main_section_html += str(selected_div_id_html)

        if div_classes:
            for div_class in div_classes:
                selected_div_classes_html = soup.find("div", class_=div_class)
                if selected_div_classes_html:
                    main_section_html += str(selected_div_classes_html)

        if not main_section_html:
            main_section_html = str(soup)

        # page content
        current_page_markdown = html2text.html2text(str(main_section_html))
        page_dict = {"source_url": current_url, "markdown": current_page_markdown}
        scraped_pages.append(page_dict)

    document_df = pd.DataFrame(scraped_pages)

    unique_pages = document_df.drop_duplicates(subset=["source_url"]).reset_index(
        drop=True
    )

    unique_pages["domain_description"] = domain_description
    unique_pages["scraped_at"] = pd.to_datetime("today")
    unique_pages["updated_at"] = pd.to_datetime("today")

    dataframe_loader = DataFrameLoader(unique_pages, page_content_column="markdown")

    docs_to_upload = dataframe_loader.load()

    return docs_to_upload


def get_sitemap(url):
    """Scrapes an XML sitemap from the provided URL and returns XML source.

    Args:
        url (string): Fully qualified URL pointing to XML sitemap.

    Returns:
        xml (string): XML source of scraped sitemap.
    """

    response = requests.get(url)  # nosec
    response.raise_for_status()  # Ensure we get a valid response or raise an HTTPError
    # Set the apparent encoding if not provided
    response.encoding = response.apparent_encoding
    xml = BeautifulSoup(response.content, "lxml-xml")
    return xml


def get_sitemap_type(xml):
    """Parse XML source and returns the type of sitemap.

    Args:
        xml (string): Source code of XML sitemap.

    Returns:
        sitemap_type (string): Type of sitemap (sitemap, sitemapindex, or None).
    """

    sitemapindex = xml.find_all("sitemapindex")
    sitemap = xml.find_all("urlset")

    if sitemapindex:
        return "sitemapindex"
    elif sitemap:
        return "urlset"
    else:
        return


def get_child_sitemaps(xml):
    """Return a list of child sitemaps present in a XML sitemap file.

    Args:
        xml (string): XML source of sitemap.

    Returns:
        sitemaps (list): Python list of XML sitemap URLs.
    """

    sitemaps = xml.find_all("sitemap")

    output = []

    for sitemap in sitemaps:
        output.append(sitemap.findNext("loc").text)
    return output


def sitemap_to_dataframe(xml, name=None, verbose=False):
    """Read an XML sitemap into a Pandas dataframe.

    Args:
        xml (bs4): XML source of sitemap as a beau
        name (optional): Optional name for sitemap parsed.
        verbose (boolean, optional): Set to True to monitor progress.

    Returns:
        dataframe: Pandas dataframe of XML sitemap content.
    """

    urls = xml.find_all("url")

    # Prepare lists to collect data
    data = []

    for url in urls:
        loc = url.find("loc").text if url.find("loc") else ""
        domain = urlparse(loc).netloc if loc else ""
        changefreq = url.find("changefreq").text if url.find("changefreq") else ""
        priority = url.find("priority").text if url.find("priority") else ""
        sitemap_name = name if name else ""

        row = {
            "domain": domain,
            "loc": loc,
            "changefreq": changefreq,
            "priority": priority,
            "sitemap_name": sitemap_name,
        }

        if verbose:
            logger.debug(row)

        data.append(row)

    # Create DataFrame from collected data
    df = pd.DataFrame(data)

    return df


def get_all_urls(url, domains_to_exclude=None):
    """Return a dataframe containing all of the URLs from a site's XML sitemaps.

    Args:
        url (string): URL of site's XML sitemap. Usually located at /sitemap.xml
        domains_to_exclude (list, optional): List of domains to exclude from the sitemap.

    Returns:
        list_of_dfs (list): a list of pandas dataframes

    """
    try:
        xml = get_sitemap(url)
        sitemap_type = get_sitemap_type(xml)

        if sitemap_type == "sitemapindex":
            sitemaps = get_child_sitemaps(xml)
        else:
            sitemaps = [url]

        list_of_dfs = []

        for sitemap in sitemaps:
            try:
                logger.info(f"Processing sitemap: {sitemap}")
                sitemap_xml = get_sitemap(sitemap)
                df_sitemap = sitemap_to_dataframe(sitemap_xml, name=sitemap)
                logger.info(f"Sitemap processed: {sitemap}")
                df = pd.DataFrame(
                    columns=["loc", "changefreq", "priority", "domain", "sitemap_name"]
                )
                # remove any rows which contain any of the excluded domains
                if domains_to_exclude:
                    df_sitemap = df_sitemap[
                        ~df_sitemap["loc"].str.contains("|".join(domains_to_exclude))
                    ]

                df = pd.concat([df, df_sitemap], ignore_index=True)
                list_of_dfs.append(df)

            except Exception as e:
                logger.error(f"Error processing sitemap {sitemap}: {e}")

        return list_of_dfs

    except Exception as e:
        logger.error(f"Error initializing sitemap processing for {url}: {e}")
        return []


def clean_urls(urls: List[str]) -> List[str]:
    """Remove or clean problematic URLs."""
    return [url for url in urls if url.startswith(("http://", "https://"))]


def extract_urls(base_url, text):
    """Extracts URLs from a string of text.

    Args:
        base_url (string): The base URL of the page.
        text (string): The text to extract URLs from.

    Returns:
        urls (list): A list of URLs found in the text.
    """

    # Regular expression to find URLs in parentheses
    pattern = re.compile(r"\((.*?)\)")

    # Extract all URLs
    urls = pattern.findall(text)

    # if any urls start with a /, add the base_url
    urls = [urljoin(base_url, url) if url.startswith("/") else url for url in urls]

    # Remove any urls that don't start with http
    urls = [url for url in urls if url.startswith("http")]

    # remove duplicate urls
    urls = list(set(urls))

    return urls


def remove_markdown_index_links(markdown_text: str) -> str:
    """Clean markdown text by removing index links.

    Args:
        markdown_text (str): markdown text to clean.

    Returns:
        str: cleaned markdown string.
    """
    # Regex patterns
    list_item_link_pattern = re.compile(
        r"^\s*\*\s*\[[^\]]+\]\([^\)]+\)\s*$", re.MULTILINE
    )
    list_item_header_link_pattern = re.compile(
        r"^\s*\*\s*#+\s*\[[^\]]+\]\([^\)]+\)\s*$", re.MULTILINE
    )
    header_link_pattern = re.compile(r"^\s*#+\s*\[[^\]]+\]\([^\)]+\)\s*$", re.MULTILINE)
    # Remove matches
    cleaned_text = re.sub(list_item_header_link_pattern, "", markdown_text)
    cleaned_text = re.sub(list_item_link_pattern, "", cleaned_text)
    cleaned_text = re.sub(header_link_pattern, "", cleaned_text)
    # Removing extra newlines resulting from removals
    cleaned_text = re.sub(r"\n\s*\n", "\n", cleaned_text)
    cleaned_text = re.sub(
        r"^\s*\n", "", cleaned_text, flags=re.MULTILINE
    )  # Remove leading newlines
    return cleaned_text


def check_if_link_in_base_domain(base_url, link):
    """checks if a link is in the same domain as the base url. If it is, returns the link"""

    if link.startswith(base_url):
        return link

    elif not link.startswith("http"):
        return f"{base_url}{link}"

    else:
        return False
