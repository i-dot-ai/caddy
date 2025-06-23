# 🕷️ Caddy Scraper

A set of web scraper solutions designed for the Caddy collections. The scraper supports multiple crawling methods, authentication handling, and content processing with AI-powered summarisation and keyword extraction. This enables Caddy to be then used with lexical and semantic search.

## 🚀 Features

- Multiple crawling methods (brute force, sitemaps, depth-first)
- Support for authenticated websites
- Support to exclude certain URLs from the crawl
- PDF and DOCX document handling
- Rate limiting and retry mechanisms
- AI-powered content summarization and keyword extraction
- Batch processing capabilities
- Configurable content extraction
- S3 integration for document storage

## 📋 Requirements

- Python 3.12+
- Poetry for dependency management

Optional:
- LLM access (for summarization features, here we use Azure OpenAI)
- AWS credentials (for S3 features)

## 🛠️ Installation

1. Install Poetry if you haven't already:

```bash
pip install poetry
```

2. Install dependencies:

```bash
poetry install
```

### Environment Variables

Required environment variables:
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
- `OPENAI_API_VERSION`: API version for Azure OpenAI

For authenticated sites:
- Site-specific credentials (e.g., `GCOE_USERNAME` and `GCOE_PASSWORD` for GCOE sites)

## 🏃‍♂️ Usage

### Basic Scraping

Run the scraper with your configuration:

```bash
poetry run python run_scrape.py
```

This will start the scraping process based on the configuration in `scrape_config.json`.


```json
[
    {
    "base_url": "https://www.example.com/",
    "sitemap_url": "https://www.example.com/sitemap.xml",
    "crawling_method": "sitemap",
    "downloading_method": "scrape",
    "output_dir": "example_scrape"
    }
]
```


### PDF Processing

To process PDF documents and generate summaries:

```bash
poetry run python pdf_to_json.py
```

### Authenticated Site Scraping

For sites requiring authentication (like GCOE):

```bash
poetry run python gcoe_scraper.py
```

## 🔧 Customization

### Excluded Domains

Create an `excluded_domains.json` file to specify URLs to exclude from scraping:

```json
{
    "excluded_urls": [
        "https://example.com/exclude-this",
        "https://example.com/also-exclude"
    ]
}
```

### Content Extraction

The scraper supports customizable content extraction through div classes and IDs. Configure these in your scraping configuration:

```json
{
    "div_classes": ["main-content", "article-body"],
    "div_ids": ["content", "main"]
}
```

## 🏗️ Architecture

The scraper is built around several key components:

1. **CaddyScraper**: Main scraping engine that handles:
   - URL discovery and validation
   - Content extraction
   - Rate limiting
   - Batch processing
   - Error handling

2. **Utility Functions**: Helper functions for:
   - URL processing
   - Content cleaning
   - HTML to markdown conversion
   - File handling

3. **Authentication Handling**: Support for:
   - Basic authentication
   - Cookie-based sessions
   - WordPress authentication
   - Custom authentication schemes

## 🐳 Docker Support

The scraper can be run in a Docker container. Build and run using:

```bash
docker build -t caddy-scraper .
docker run caddy-scraper
```

## Rate Limiting

Please be friendly to the target websites. The scraper implements rate limiting to be respectful to target websites but you may want to change these. Default settings:
- 10 calls per second for API endpoints
- Configurable delays between requests

## 📝 Output

The scraper generates JSON files containing:
- Source URL
- Extracted content in markdown format
- AI-generated summary
- Keywords
- Metadata (title, date, etc.)

This output can be uploaded to the Caddy resource using the `upload_files.py` script in the `model` folder.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
