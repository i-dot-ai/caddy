"""Script to pull and upload caddy data."""

import asyncio
import enum
import json
import os

import click

from opensearch_document_manager import OpenSearchDocumentManager
from scrape_utils import logger

from os_tools import get_os_client
from caddy_scraper import CaddyScraper
from url_scraper import URLListScraper

os_manager = OpenSearchDocumentManager(
    get_os_client(), index_name="reduced-farming-grants-index"
)
os_manager.create_index()


class ScrapeType(enum.Enum):
    SITEMAP = enum.auto()
    URL_LIST = enum.auto()


@click.command()
@click.option(
    "--upload-to-os",
    default=True,
    help="Whether to upload the scraped output directly to opensearch after scraping",
)
@click.option(
    "--scrape-type",
    type=click.Choice(ScrapeType, case_sensitive=False),
    default=ScrapeType.SITEMAP,
    help="Whether to scrape using a sitemap or using url list, options are `sitemap` or `url_list`",
)
def scrape(upload_to_os: bool, scrape_type: ScrapeType):
    if scrape_type == ScrapeType.SITEMAP:
        logger.info("Starting SITEMAP Scraper")
        with open("scrape_config.json", "r+") as f:
            scrap_configs = json.load(f)
        for config in scrap_configs:
            logger.info(f"Scraping {config['base_url']}")
            scraper = CaddyScraper(**config)
            scraper.run()
            logger.info(
                f"Scrape completed for {config['base_url']}. Output directory: {
                    scraper.output_dir
                }"
            )
            if not os.path.exists(scraper.output_dir):
                logger.warning(
                    f"Output directory {
                        scraper.output_dir
                    } does not exist after scraping. Creating..."
                )
                os.makedirs(scraper.output_dir)
        if upload_to_os:
            for scrape_dir in ["govuk_scrape"]:
                logger.info(f"Uploading {scrape_dir}")
                if not os.path.exists(scrape_dir):
                    logger.error(
                        f"Directory {scrape_dir} does not exist. Skipping upload."
                    )
                    continue
                asyncio.run(os_manager.async_bulk_upload(scrape_dir, domain=scrape_dir))
        logger.info("Finished Caddy Scrape")
    elif scrape_type == ScrapeType.URL_LIST:
        logger.info("Starting URL_LIST Scraper")
        if not os.path.exists("url_scrape.json"):
            logger.error(
                "URL list file url_scrape.json not found. Please create this file."
            )
            return
        scraper_config = {}
        if os.path.exists("url_list_config.json"):
            logger.info(
                "Loading URL list scraper configuration from url_list_config.json"
            )
            with open("url_list_config.json", "r") as f:
                scraper_config = json.load(f)
        else:
            logger.info(
                "Configuration file url_list_config.json not found. Using default settings."
            )

        # Set the input file in the config
        scraper_config["input_file"] = "url_scrape.json"

        try:
            # Create and run the URL list scraper
            scraper = URLListScraper(**scraper_config)
            scraper.run()
            logger.info(
                f"URL list scrape completed. Output directory: {scraper.output_dir}"
            )

            # Note: OpenSearch upload is not implemented for URL list scraper as requested
            if upload_to_os:
                logger.info(f"Uploading {scraper.output_dir} to OpenSearch")
                if not os.path.exists(scraper.output_dir):
                    logger.error(
                        f"Directory {scraper.output_dir} does not exist. Skipping upload."
                    )
                else:
                    try:
                        asyncio.run(
                            os_manager.async_bulk_upload(
                                scraper.output_dir, domain=scraper.output_dir
                            )
                        )
                        logger.info("OpenSearch upload completed successfully")
                    except Exception as upload_error:
                        logger.error(
                            f"Error during OpenSearch upload: {str(upload_error)}"
                        )

        except Exception as e:
            logger.error(f"Error during URL list scraping: {str(e)}")
            return

        logger.info("Finished URL List Scrape")

    else:
        logger.info("No action taken")


if __name__ == "__main__":
    scrape()
