"""Script to pull and upload caddy data."""

import asyncio
import json
import os


from opensearch_document_manager import OpenSearchDocumentManager
from scrape_utils import logger

from os_tools import get_os_client
from caddy_scraper import CaddyScraper

os_manager = OpenSearchDocumentManager(
    get_os_client(), index_name="caddy-hybrid-search-index"
)
os_manager.create_index()

if __name__ == "__main__":
    logger.info("Starting Caddy Scrape")
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
    for scrape_dir in ["govuk_scrape"]:
        logger.info(f"Uploading {scrape_dir}")
        if not os.path.exists(scrape_dir):
            logger.error(f"Directory {scrape_dir} does not exist. Skipping upload.")
            continue
        asyncio.run(os_manager.async_bulk_upload(scrape_dir, domain=scrape_dir))
    logger.info("Finished Caddy Scrape")
