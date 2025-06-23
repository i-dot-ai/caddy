"""Caddy scraper module."""

import asyncio
import json
import os
import re
from typing import Dict, List, Optional, Any
from ratelimit import limits, sleep_and_retry

import html2text
import pandas as pd
import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
from tqdm import tqdm
from aiohttp import ClientError, TooManyRedirects

from scrape_utils import (
    extract_urls,
    get_all_urls,
    logger,
    remove_anchor_urls,
    remove_markdown_index_links,
    check_if_link_in_base_domain,
    retry,
    clean_urls,
)


class CaddyScraper:
    """CaddyScraper definition."""

    def __init__(
        self,
        base_url: str,
        sitemap_url: Optional[str] = None,
        crawling_method: str = "brute",
        downloading_method: str = "scrape",
        scrape_depth: Optional[int] = 4,
        div_classes: Optional[List] = ["main-content", "cads-main-content"],
        div_ids: Optional[List] = ["main-content", "cads-main-content"],
        batch_size: int = 1000,
        output_dir: str = "scrape_result",
    ):
        """Initialise CaddyScraper.

        Args:
            base_url (str): base URL of the website to be scraped
            sitemap_url (Optional[str]): sitemap of domain, if available. Defaults to None.
            crawling_method (str): Crawling method for fetching URLS to download options: ["brute", "sitemap"]. Defaults to "brute".
            downloading_method (str): Downloading method for fetched URLS: ["scrape", "api"]. Defaults to "scrape".
            scrape_depth (Optional[int]): depth of recursive crawler used by "brute" crawling method. Defaults to 4.
            div_classes: (Optional[List]): HTML div classes to scrape. Defaults to ["main-content", "cads-main-content"],
            div_ids: (Optional[List]) = HTML div ids to scrape. Defaults to ["main-content", "cads-main-content"],
            batch_size (int): Number of URLS to be scraped in a batch. Defaults to 1000.
            output_dir (str): output directory to store scraper results. Defaults to "scrape_result".
        """
        self.base_url = base_url
        self.sitemap_url = sitemap_url
        self.crawling_method = crawling_method
        self.downloading_method = downloading_method
        self.scrape_depth = scrape_depth
        self.div_classes = div_classes
        self.div_ids = div_ids
        self.batch_size = batch_size
        self.output_dir = output_dir
        self.excluded_domains = self.get_excluded_domains()
        self.problematic_urls = set()
        self.bs_transformer = BeautifulSoupTransformer()

    def run(self):
        """Run the caddy scraper, fetching relevant urls then downloading and saving their scraped content."""
        urls = self.fetch_urls()
        logger.info(f"{len(urls)} urls fetched")
        asyncio.run(self.download_urls(urls))

    def get_excluded_domains(self) -> List[str]:
        """Returns the list of excluded domains from the json file as a list

        Returns:
            excluded_domains (List[str]): a list of excluded domains for the domain
        """
        file_path = "excluded_domains.json"
        with open(file_path, "r") as file:
            data = json.load(file)
            excluded_domains = data["excluded_urls"]
        return excluded_domains

    def fetch_urls(self) -> List[str]:
        """Fetch list of urls to scrape.

        Raises:
            ValueError: scrape_depth attribute must be set to use brute crawling_method.
            ValueError: sitemap_url attribute must be set to use sitemap crawling_method.

        Returns:
            List[str]: list of fetched urls.
        """
        if self.crawling_method == "brute":
            if not isinstance(self.scrape_depth, int):
                raise ValueError(
                    "Valid int must be passed as scrape depth for brute crawling method."
                )
            urls = self.recursive_crawler()
        elif self.crawling_method == "sitemap":
            if not isinstance(self.sitemap_url, str):
                raise ValueError(
                    "Valid string must be passed as sitemap_url for sitemap crawling method."
                )
            urls = self.fetch_urls_from_sitemap()
        else:
            urls = []

        return clean_urls(urls)

    async def fetch_pages(self, urls):
        """
        Asynchronously fetch multiple pages in batches, handling errors for individual URLs.

        This method attempts to fetch URLs in batches. If a fetch fails,
        the URL is added to the problematic_urls set and the error is logged.

        Args:
            urls (List[str]): A list of URLs to fetch.

        Returns:
            List[Document]: A list of successfully fetched pages as Document objects.
        """
        results = []
        authentication_cookie = self.get_authentication_cookie()
        header_template = (
            {"Cookie": authentication_cookie} if authentication_cookie else None
        )

        for i in range(0, len(urls), self.batch_size):
            batch_urls = urls[i : i + self.batch_size]
            loader = AsyncHtmlLoader(batch_urls, header_template=header_template)

            try:
                batch_pages = await loader.aload()
                for url, page in zip(batch_urls, batch_pages):
                    if page:
                        results.append(page)
                    else:
                        logger.warning(f"Failed to fetch {url}")
                        self.problematic_urls.add(url)
            except Exception as e:
                logger.error(f"Error in batch fetching: {str(e)}")
                for url in batch_urls:
                    try:
                        page = await self.fetch_single_page(url, header_template)
                        if page:
                            results.append(page)
                    except Exception as e:
                        logger.error(f"Error fetching {url}: {str(e)}")
                        self.problematic_urls.add(url)

        return results

    @retry()
    async def fetch_single_page(self, url, header_template):
        """
        Asynchronously fetch a single page using AsyncHtmlLoader.

        This method attempts to fetch a single URL using AsyncHtmlLoader. It includes
        a retry mechanism for handling ClientError and TooManyRedirects exceptions.

        Args:
            url (str): The URL of the page to fetch.
            header_template (dict): Headers to use for the request, including authentication if needed.

        Returns:
            Optional[Document]: The fetched page as a Document object if successful, None otherwise.

        Raises:
            ClientError: If there's a client-related error during fetching after all retries.
            TooManyRedirects: If there are too many redirects during fetching after all retries.
        """
        try:
            loader = AsyncHtmlLoader([url], header_template=header_template)
            pages = await loader.aload()
            return pages[0] if pages else None
        except (ClientError, TooManyRedirects) as e:
            logger.warning(f"Failed to fetch {url} after retries: {str(e)}")
            self.problematic_urls.add(url)
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {str(e)}")
            self.problematic_urls.add(url)
            return None

    def recursive_crawler(self) -> List[str]:
        """Starting from a base url, recursively crawl a domain for urls.

        Returns:
            links (List[str]): a list of links found on the pages.
        """
        links = [self.base_url]
        for depth in range(self.scrape_depth):
            try:
                logger.info(f"Crawling depth {depth + 1}/{self.scrape_depth}")
                all_pages = asyncio.run(self.fetch_pages(links))
                new_links = []
                for page in all_pages:
                    current_url = page.metadata["source"]
                    page_html = BeautifulSoup(page.page_content, features="lxml")
                    extracted_links, links = self.extract_links_from_soup(
                        page_html, current_url, links
                    )

                    new_links.extend(extracted_links)

                links = list(set(new_links) - self.problematic_urls)

                logger.info(f"Found {len(links)} unique links at depth {depth + 1}")
                logger.info(f"Problematic URLs removed: {len(self.problematic_urls)}")
            except Exception as e:
                logger.error(
                    f"Error in recursive crawler at depth {depth + 1}: {str(e)}"
                )

        self.log_problematic_urls()
        return links

    def fetch_urls_from_sitemap(self) -> List[str]:
        """Fetch urls from a sitemap.

        Returns:
            List[str]: list of urls extracted from sitemap.
        """
        df_of_urls = pd.concat(get_all_urls(self.sitemap_url))
        df_of_urls = df_of_urls[df_of_urls["loc"].str.contains(self.base_url)]
        return self.remove_excluded_domains(df_of_urls["loc"].tolist())

    def remove_excluded_domains(self, url_list: List[str]) -> List[str]:
        """Remove excluded domains from a list of urls.

        Args:
            url_list (List[str]): list of urls to process.

        Returns:
            List[str]: processed list of urls.
        """
        return [
            url
            for url in url_list
            if not any(
                excluded_domain in url for excluded_domain in self.excluded_domains
            )
        ]

    async def download_urls(self, urls: List[str]) -> List[Dict[str, str]]:
        """Split urls into batches and scrape their content.

        Args:
            urls (List[str]): urls to scrape.

        Returns:
            List[Dict[str, str]]: List of dicts containing scraped data from urls.
        """
        url_batches = [
            urls[i : i + self.batch_size] for i in range(0, len(urls), self.batch_size)
        ]
        for ind, url_batch in enumerate(url_batches):
            if self.downloading_method == "scrape":
                results = await self.scrape_url_batch(url_batch)
            elif self.downloading_method == "api":
                results = self.download_batch_from_govuk_api(url_batch)
            self.save_results(results, ind)

    @retry()
    async def scrape_url_batch(self, url_list: List[str]) -> List[Dict[str, str]]:
        """Takes a batch of urls, iteratively scrapes the content of each page.

        Args:
            url_list (List[str]): list of urls in batch.

        Returns:
            List[Dict[str, str]]: List of dicts containing scraped data from urls.
        """
        authentication_cookie = self.get_authentication_cookie()
        header_template = (
            {"Cookie": authentication_cookie} if authentication_cookie else None
        )

        loader = AsyncHtmlLoader(url_list, header_template=header_template)
        scraped_pages = []

        try:
            docs = await loader.aload()
            for page in docs:
                try:
                    current_url = page.metadata["source"]
                    soup = BeautifulSoup(page.page_content, "html.parser")
                    main_section_html = self.extract_main_content(soup)
                    if main_section_html and len(main_section_html) > 0:
                        current_page_markdown = html2text.html2text(
                            str(main_section_html)
                        )
                        current_page_markdown = remove_markdown_index_links(
                            current_page_markdown
                        )
                        page_dict = {
                            "source": current_url,
                            "markdown": current_page_markdown,
                            "markdown_length": len(current_page_markdown),
                        }
                        scraped_pages.append(page_dict)
                    else:
                        logger.warning(f"No main content found for {current_url}")
                        self.problematic_urls.add(current_url)
                except Exception as e:
                    logger.error(f"Error processing page {current_url}: {str(e)}")
                    self.problematic_urls.add(current_url)
        except Exception as e:
            logger.error(f"Error in batch scraping: {str(e)}")

        return scraped_pages

    def get_authentication_cookie(self) -> Optional[str]:
        """Get authentication cookie for domain access.

        Returns:
            Optional[str]: authentication cookie.
        """
        if "advisernet" in self.base_url:
            return f".CitizensAdviceLogin={os.getenv('ADVISOR_NET_AUTHENTICATION')}"
        return None

    def extract_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Extract the main content from the BeautifulSoup object.

        Args:
            soup (BeautifulSoup): BeautifulSoup object of the page.

        Returns:
            Optional[BeautifulSoup]: Main content section or None if not found.
        """
        for div_id in self.div_ids:
            main_section = soup.find("div", id=div_id)
            if main_section:
                return main_section

        for div_class in self.div_classes:
            main_section = soup.find("div", class_=div_class)
            if main_section:
                return main_section

        return soup

    @sleep_and_retry
    @limits(calls=10, period=1)
    def download_single_url(
        self, url: str, base_url: str, min_body_length: int
    ) -> Optional[Dict[str, Any]]:
        """
        Download and process content from a single URL using the gov.uk API.

        This method is rate-limited to 10 calls per second for the GOV UK Content API.

        Args:
            url (str): The URL to download content from.
            base_url (str): The base URL of the gov.uk website.
            min_body_length (int): The minimum required length for the body content.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the processed content and metadata,
                                    or None if the URL couldn't be processed.

        Raises:
            ValueError: If the base_url is not a gov.uk URL.
        """
        if "gov.uk" not in base_url:
            raise ValueError("Can only use gov.uk API to scrape government urls.")

        if url.startswith(base_url):
            api_call = url.replace(base_url, "https://www.gov.uk/api/content/")
        else:
            logger.warning(f"Skipping non gov.uk url: {url}")
            return None

        try:
            response = requests.get(api_call, timeout=100)
            response.raise_for_status()

            response_json = response.json()
            details = response_json.get("details", {})
            json_body = details.get("body")
            if json_body is None:
                parts = details.get("parts", [])
                json_body = "".join(part.get("body", "") for part in parts)

            if len(json_body) > min_body_length:
                linked_urls = re.findall(r"(?P<url>https?://[^\s]+)", json_body)
                if len(linked_urls) > 0:
                    linked_urls = [u[:-1] for u in set(linked_urls)]
                return {
                    "source": url,
                    "markdown": json_body,
                    "markdown_length": len(json_body),
                    "linked_urls": linked_urls,
                }
            else:
                logger.warning(f"Skipping {url} due to insufficient body length")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error processing {url}: {str(e)}")
            self.problematic_urls.add(url)
            return None

    def download_batch_from_govuk_api(
        self, url_list: List[str], min_body_length: int = 50
    ) -> List[Dict[str, str]]:
        """
        Download and process content from a batch of URLs using the gov.uk API.

        This method iterates through the provided list of URLs, downloading and processing
        the content for each. It includes error handling and rate limiting management.

        Args:
            url_list (List[str]): A list of URLs to process.
            min_body_length (int, optional): The minimum required length for the body content.
                                            Defaults to 50.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, each containing the processed
                                content and metadata for a successfully downloaded URL.
        """
        pages = []
        for url in tqdm(url_list, desc="Downloading gov.uk URLs"):
            result = self.download_single_url(url, self.base_url, min_body_length)
            if result:
                pages.append(result)
        return pages

    def save_results(
        self, pages: List[Dict[str, str]], file_index: Optional[int] = None
    ):
        """Save downloaded pages to file.

        Args:
            pages (List[Dict[str, str]]): downloaded web pages including meta-data.
            file_index (Optional[int]): batch index, used to create file name.
        """
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        with open(f"{self.output_dir}/scrape_result_{file_index}.json", "w+") as f:
            json.dump(pages, f)

    def extract_links_from_soup(self, soup, current_url, links):
        """Extract links from BeautifulSoup object.

        Args:
            soup (BeautifulSoup): BeautifulSoup object of the page.

        Returns:
            List[str]: List of extracted links.
        """
        extracted_tags = self.bs_transformer.extract_tags(str(soup), ["a"])
        current_page_links = extract_urls(current_url, extracted_tags)
        current_page_links = [
            link
            for link in current_page_links
            if check_if_link_in_base_domain(self.base_url, link)
        ]
        links += current_page_links
        links = self.remove_excluded_domains(links)
        extracted_links = remove_anchor_urls(list(set(links)))
        return extracted_links, links

    def log_problematic_urls(self):
        """Log problematic URLs encountered during scraping."""
        if self.problematic_urls:
            logger.warning(
                "The following URLs were problematic and excluded from crawling:"
            )
            for url in self.problematic_urls:
                logger.warning(f"- {url}")
        else:
            logger.info("No problematic URLs encountered during crawling.")
