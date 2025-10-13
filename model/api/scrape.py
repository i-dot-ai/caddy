import re
from typing import List, Optional

import html2text
from bs4 import BeautifulSoup
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from langchain_community.document_loaders import AsyncHtmlLoader
from tqdm import tqdm

from api.decorators import retry
from api.environment import config
from api.models import utc_now

metric_writer = config.get_metrics_writer()


class ScrapedPage:
    def __init__(
        self,
        source: str,
        title: str,
        markdown: str,
        markdown_length: int,
        content_type: str,
        url: str,
    ) -> None:
        self.source = source
        self.title = title
        self.markdown = markdown
        self.markdown_length = markdown_length
        self.content_type = content_type
        self.url = url


class Scraper:
    def __init__(
        self,
        logger: StructuredLogger,
        batch_size=100,
    ):
        self.batch_size = batch_size
        self.problematic_urls = set()
        self.div_classes: Optional[List] = ["main-content", "cads-main-content"]
        self.div_ids: Optional[List] = ["main-content", "cads-main-content"]
        self.logger = logger

    def remove_markdown_index_links(self, markdown_text: str) -> str:
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
        header_link_pattern = re.compile(
            r"^\s*#+\s*\[[^\]]+\]\([^\)]+\)\s*$", re.MULTILINE
        )
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

    async def download_urls(self, urls: List[str]) -> list[ScrapedPage]:
        """Split URLs into batches and scrape their content.
        Args:
            urls (List[str]): URL list to scrape
        """
        url_batches = [
            urls[i : i + self.batch_size] for i in range(0, len(urls), self.batch_size)
        ]
        pages = []

        for ind, url_batch in enumerate(url_batches):
            self.logger.info(
                "Processing batch {current_batch}/{total_batches} ({batch_length} URLs)",
                current_batch=(ind + 1),
                total_batches=len(url_batches),
                batch_length=len(url_batch),
            )
            results = await self.scrape_url_batch(url_batch)
            pages.extend(results)
            self.logger.info(
                "Batch {current_batch} completed. {completed_count} pages scraped successfully.",
                current_batch=(ind + 1),
                completed_count=len(results),
            )
        self.log_problematic_urls()
        return pages

    @retry(logger_attr="logger")
    async def scrape_url_batch(self, url_list: List[str]) -> List[ScrapedPage]:
        """Takes a batch of URLs, iteratively scrapes the content of each page.
        Args:
            url_list (List[str]): list of URLs in batch.
        Returns:
            List[Dict[str, str]]: List of dicts containing scraped data from URLs.
        """
        loader = AsyncHtmlLoader(url_list)
        scraped_pages = []

        try:
            docs = await loader.aload()
            for page in tqdm(docs, desc="Processing pages"):
                processing_start_time = utc_now()
                try:
                    current_url = page.metadata["source"]
                    soup = BeautifulSoup(page.page_content, "html.parser")
                    main_section_html = await self.extract_main_content(soup)

                    if main_section_html and len(str(main_section_html)) > 0:
                        current_page_markdown = html2text.html2text(
                            str(main_section_html)
                        )
                        current_page_markdown = self.remove_markdown_index_links(
                            current_page_markdown
                        )

                        page_title = ""
                        title_tag = soup.find("title")
                        if title_tag:
                            page_title = title_tag.get_text().strip()
                        content_type = ""
                        content_type_tag = soup.meta.get("content", "text/html")
                        if content_type_tag:
                            content_type = content_type_tag.split(";")[0]

                        scraped_page = ScrapedPage(
                            source=current_url,
                            title=page_title if page_title else current_url,
                            markdown=current_page_markdown,
                            markdown_length=len(current_page_markdown),
                            content_type=content_type,
                            url=current_url,
                        )
                        scraped_pages.append(scraped_page)
                        metric_writer.put_metric(
                            metric_name="resource_url_scraped",
                            value=1,
                        )
                        metric_writer.put_metric(
                            metric_name="resource_url_scraped_duration_ms",
                            value=(utc_now() - processing_start_time).total_seconds()
                            * 1000,
                        )
                    else:
                        self.logger.warning(
                            "No main content found for {current_url}",
                            current_url=current_url,
                        )
                        self.problematic_urls.add(current_url)

                except Exception:
                    current_url = (
                        page.metadata.get("source", "unknown")
                        if hasattr(page, "metadata")
                        else "unknown"
                    )
                    self.logger.exception(
                        "Error processing page {current_url}", current_url=current_url
                    )
                    self.problematic_urls.add(current_url)

        except Exception:
            self.logger.exception("Error in batch scraping")
            # Add all URLs in batch to problematic_urls if batch fails
            self.problematic_urls.update(url_list)

        return scraped_pages

    async def extract_main_content(
        self, soup: BeautifulSoup
    ) -> Optional[BeautifulSoup]:
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
        self.logger.warning(
            "No specific main content div found, using entire page content"
        )
        return soup

    def log_problematic_urls(self):
        """Log problematic URLs encountered during scraping."""
        if self.problematic_urls:
            self.logger.warning(
                "The following {problematic_url_count} URLs were problematic and could not be scraped:",
                problematic_url_count=len(self.problematic_urls),
            )
            for url in sorted(self.problematic_urls):
                self.logger.warning(
                    "Problematic URL during scrape processing - {url}", url=url
                )
        else:
            self.logger.info("No problematic URLs encountered during scraping.")
