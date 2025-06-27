"""URL List scraper module."""

import asyncio
import json
import os
from typing import Dict, List, Optional

import html2text
from bs4 import BeautifulSoup
from langchain_community.document_loaders import AsyncHtmlLoader
from tqdm import tqdm

from scrape_utils import (
    logger,
    remove_markdown_index_links,
    retry,
)


class URLListScraper:
    """URLListScraper definition for processing a list of URLs with metadata."""

    def __init__(
        self,
        input_file: str,
        div_classes: Optional[List] = ["main-content", "cads-main-content"],
        div_ids: Optional[List] = ["main-content", "cads-main-content"],
        batch_size: int = 1000,
        output_dir: str = "url_list_scrape_result",
    ):
        """Initialise URLListScraper.

        Args:
            input_file (str): Path to JSON file containing URL list with metadata
            div_classes: (Optional[List]): HTML div classes to scrape. Defaults to ["main-content", "cads-main-content"],
            div_ids: (Optional[List]) = HTML div ids to scrape. Defaults to ["main-content", "cads-main-content"],
            batch_size (int): Number of URLS to be scraped in a batch. Defaults to 1000.
            output_dir (str): output directory to store scraper results. Defaults to "url_list_scrape_result".
        """
        self.input_file = input_file
        self.div_classes = div_classes
        self.div_ids = div_ids
        self.batch_size = batch_size
        self.output_dir = output_dir
        self.problematic_urls = set()
        self.url_metadata = {}  # Store metadata for each URL

    def run(self):
        """Run the URL list scraper, loading URLs from file then downloading and saving their scraped content."""
        url_data = self.load_url_list()
        logger.info(f"{len(url_data)} URLs loaded from {self.input_file}")
        asyncio.run(self.download_urls(url_data))

    def load_url_list(self) -> List[Dict[str, str]]:
        """Load URL list from JSON file.

        Returns:
            List[Dict[str, str]]: List of URL data with metadata.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            ValueError: If the JSON file is malformed or missing required fields.
        """
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"Input file {self.input_file} not found")

        try:
            with open(self.input_file, "r") as f:
                url_data = json.load(f)

            # Validate required fields (ignoring content_id as requested)
            required_fields = ["title", "baseUrl"]
            for item in url_data:
                for field in required_fields:
                    if field not in item:
                        raise ValueError(
                            f"Missing required field '{field}' in URL data"
                        )

                # Store metadata for later use (only title, ignore content_id)
                self.url_metadata[item["baseUrl"]] = {"title": item["title"]}

            return url_data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {self.input_file}: {str(e)}")

    async def download_urls(self, url_data: List[Dict[str, str]]):
        """Split URLs into batches and scrape their content.

        Args:
            url_data (List[Dict[str, str]]): URL data with metadata to scrape.
        """
        urls = [item["baseUrl"] for item in url_data]
        url_batches = [
            urls[i : i + self.batch_size] for i in range(0, len(urls), self.batch_size)
        ]

        for ind, url_batch in enumerate(url_batches):
            logger.info(
                f"Processing batch {ind + 1}/{len(url_batches)} ({len(url_batch)} URLs)"
            )
            results = await self.scrape_url_batch(url_batch)
            self.save_results(results, ind)
            logger.info(
                f"Batch {ind + 1} completed. {len(results)} pages scraped successfully."
            )

        self.log_problematic_urls()

    @retry()
    async def scrape_url_batch(self, url_list: List[str]) -> List[Dict[str, str]]:
        """Takes a batch of URLs, iteratively scrapes the content of each page.

        Args:
            url_list (List[str]): list of URLs in batch.

        Returns:
            List[Dict[str, str]]: List of dicts containing scraped data from URLs.
        """
        authentication_cookie = self.get_authentication_cookie(
            url_list[0] if url_list else ""
        )
        header_template = (
            {"Cookie": authentication_cookie} if authentication_cookie else None
        )

        loader = AsyncHtmlLoader(url_list, header_template=header_template)
        scraped_pages = []

        try:
            docs = await loader.aload()
            for page in tqdm(docs, desc="Processing pages"):
                try:
                    current_url = page.metadata["source"]
                    soup = BeautifulSoup(page.page_content, "html.parser")
                    main_section_html = self.extract_main_content(soup)

                    if main_section_html and len(str(main_section_html)) > 0:
                        current_page_markdown = html2text.html2text(
                            str(main_section_html)
                        )
                        current_page_markdown = remove_markdown_index_links(
                            current_page_markdown
                        )

                        # Get metadata for this URL
                        metadata = self.url_metadata.get(current_url, {})

                        page_dict = {
                            "source": current_url,
                            "title": metadata.get("title", ""),
                            "markdown": current_page_markdown,
                            "markdown_length": len(current_page_markdown),
                        }
                        scraped_pages.append(page_dict)
                    else:
                        logger.warning(f"No main content found for {current_url}")
                        self.problematic_urls.add(current_url)

                except Exception as e:
                    current_url = (
                        page.metadata.get("source", "unknown")
                        if hasattr(page, "metadata")
                        else "unknown"
                    )
                    logger.error(f"Error processing page {current_url}: {str(e)}")
                    self.problematic_urls.add(current_url)

        except Exception as e:
            logger.error(f"Error in batch scraping: {str(e)}")
            # Add all URLs in batch to problematic_urls if batch fails
            self.problematic_urls.update(url_list)

        return scraped_pages

    def get_authentication_cookie(self, sample_url: str) -> Optional[str]:
        """Get authentication cookie for domain access.

        Args:
            sample_url (str): A sample URL to determine the domain.

        Returns:
            Optional[str]: authentication cookie.
        """
        if "advisernet" in sample_url:
            return f".CitizensAdviceLogin={os.getenv('ADVISOR_NET_AUTHENTICATION')}"
        return None

    def extract_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Extract the main content from the BeautifulSoup object.

        Args:
            soup (BeautifulSoup): BeautifulSoup object of the page.

        Returns:
            Optional[BeautifulSoup]: Main content section or None if not found.
        """
        # Try to find content by div IDs first
        for div_id in self.div_ids:
            main_section = soup.find("div", id=div_id)
            if main_section:
                return main_section

        # Then try div classes
        for div_class in self.div_classes:
            main_section = soup.find("div", class_=div_class)
            if main_section:
                return main_section

        # If no specific content div found, return the whole soup
        # but log a warning
        logger.warning("No specific main content div found, using entire page content")
        return soup

    def save_results(
        self, pages: List[Dict[str, str]], file_index: Optional[int] = None
    ):
        """Save downloaded pages to individual files named after their titles.

        Args:
            pages (List[Dict[str, str]]): downloaded web pages including meta-data.
            file_index (Optional[int]): batch index, used for logging purposes.
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        saved_count = 0
        for page in pages:
            try:
                # Use title as filename, sanitize it for filesystem
                title = page.get("title", "untitled")
                # Remove/replace characters that aren't filesystem-safe
                safe_title = "".join(
                    c for c in title if c.isalnum() or c in (" ", "-", "_")
                ).rstrip()
                safe_title = safe_title.replace(" ", "_")

                # Ensure filename isn't too long
                if len(safe_title) > 200:
                    safe_title = safe_title[:200]

                filename = f"{self.output_dir}/{safe_title}.json"

                # Handle duplicate filenames by adding a counter
                counter = 1
                original_filename = filename
                while os.path.exists(filename):
                    base_name = original_filename.replace(".json", "")
                    filename = f"{base_name}_{counter}.json"
                    counter += 1

                with open(filename, "w+") as f:
                    json.dump([page], f, indent=2)

                saved_count += 1
                logger.debug(f"Saved page '{title}' to {filename}")

            except Exception as e:
                logger.error(
                    f"Error saving page '{page.get('title', 'unknown')}': {str(e)}"
                )

        logger.info(
            f"Saved {saved_count} pages from batch {file_index} to {self.output_dir}"
        )

    def log_problematic_urls(self):
        """Log problematic URLs encountered during scraping."""
        if self.problematic_urls:
            logger.warning(
                f"The following {len(self.problematic_urls)} URLs were problematic and could not be scraped:"
            )
            for url in sorted(self.problematic_urls):
                logger.warning(f"- {url}")
        else:
            logger.info("No problematic URLs encountered during scraping.")
