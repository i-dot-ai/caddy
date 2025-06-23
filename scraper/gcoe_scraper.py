import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urljoin, urlparse
import io

import PyPDF2
from docx import Document

from openai import AzureOpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

global_cookies = {}

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-12-01-preview",
)


def get_fresh_cookies_with_selenium(username, password):
    """Use Selenium to log in and get fresh cookies."""
    print("Attempting to get fresh cookies with Selenium...")

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        login_url = "https://gcoe.civilservice.gov.uk/sign-in/"
        print(f"Navigating to login page: {login_url}")
        driver.get(login_url)

        driver.save_screenshot("login_page.png")

        time.sleep(3)

        form = driver.find_element(By.CSS_SELECTOR, "form[action*='sign-in']")

        username_field = form.find_element(By.ID, "user-name")
        username_field.clear()
        username_field.send_keys(username)

        password_field = form.find_element(By.ID, "password")
        password_field.clear()
        password_field.send_keys(password)

        submit_button = form.find_element(By.ID, "login-button")
        submit_button.click()

        print("Waiting for login to complete...")
        time.sleep(5)

        driver.save_screenshot("after_login.png")

        if "sign-in" in driver.current_url:
            print("Still on login page, login may have failed")
            return None

        print(f"Login successful! Current URL: {driver.current_url}")

        cookies = driver.get_cookies()
        cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}

        print(f"Retrieved {len(cookie_dict)} cookies")
        return cookie_dict

    except Exception as e:
        print(f"Error during Selenium login: {e}")
        if "driver" in locals():
            driver.save_screenshot("selenium_error.png")
        return None

    finally:
        driver.quit()


def is_same_domain(url, base_url):
    """Check if URL belongs to the same domain as the base URL."""
    return urlparse(url).netloc == urlparse(base_url).netloc


def is_document_url(url):
    """Check if URL points to a PDF or DOCX file."""
    lower_url = url.lower()
    return lower_url.endswith(".pdf") or lower_url.endswith(".docx")


def extract_text_from_pdf(pdf_content):
    """Extract text from PDF content."""
    try:
        pdf_file = io.BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            text += pdf_reader.pages[page_num].extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""


def extract_text_from_docx(docx_content):
    """Extract text from DOCX content."""
    try:
        docx_file = io.BytesIO(docx_content)
        doc = Document(docx_file)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {e}")
        return ""


def download_document(url, cookies=None):
    """Download a document file and extract its text."""
    global global_cookies
    cookies = cookies or global_cookies

    try:
        session = requests.Session()

        if cookies:
            for key, value in cookies.items():
                session.cookies.set(key, value)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://gcoe.civilservice.gov.uk/",
        }

        print(f"Downloading document: {url}")
        response = session.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"Failed to download document. Status code: {response.status_code}")
            return None

        filename = os.path.basename(urlparse(url).path)

        if url.lower().endswith(".pdf"):
            text = extract_text_from_pdf(response.content)
            print(f"Extracted {len(text.split())} words from PDF")
        elif url.lower().endswith(".docx"):
            text = extract_text_from_docx(response.content)
            print(f"Extracted {len(text.split())} words from DOCX")
        else:
            text = ""
            print("Unknown document type")

        return {"filename": filename, "text_content": text}
    except Exception as e:
        print(f"Error downloading document {url}: {e}")
        return None


def request_page_content(
    url, cookies=None, username=None, password=None, retry_with_new_cookie=True
):
    """Scrape content from a single page."""
    global global_cookies
    cookies = cookies or global_cookies

    if is_document_url(url):
        return download_document(url, cookies)

    try:
        session = requests.Session()

        if cookies:
            for key, value in cookies.items():
                session.cookies.set(key, value)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "https://gcoe.civilservice.gov.uk/",
        }

        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch {url}. Status code: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Check if we're on a login page
        if (
            soup.find(string=lambda text: "Sign in" in text if text else False)
            and soup.find("form")
        ) or "sign-in" in response.url:
            print(
                f"WARNING: Redirected to login page for {url}. Authentication may have failed."
            )

            # If we have credentials and this is our first retry, get a new cookie and try again
            if retry_with_new_cookie and username and password:
                print("Attempting to refresh cookie and retry...")
                new_cookies = get_fresh_cookies_with_selenium(username, password)

                if new_cookies:
                    print("Successfully obtained new cookies. Retrying request...")
                    # Update the global cookies
                    global_cookies.update(new_cookies)
                    # Retry the request with new cookies, but don't allow another retry to prevent infinite loops
                    return request_page_content(
                        url,
                        new_cookies,
                        username,
                        password,
                        retry_with_new_cookie=False,
                    )
                else:
                    print("Failed to obtain new cookies.")

            return None

        return soup
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None


def extract_links(url, cookies=None, username=None, password=None):
    """Extract all links from a page."""
    if is_document_url(url):
        print(f"Skipping link extraction for document: {url}")
        return []

    soup = request_page_content(url, cookies, username, password)
    if not soup:
        return []

    if isinstance(soup, dict):
        print(
            f"Received document data instead of HTML for {url}, skipping link extraction"
        )
        return []

    links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(url, href)

        if is_same_domain(full_url, url) and "#" not in full_url:
            links.add(full_url)

    return links


def find_links_to_depth(
    base_url,
    max_depth=5,
    cookies=None,
    excluded_domains=None,
    username=None,
    password=None,
):
    """Find all unique links up to a specified depth."""
    if excluded_domains is None:
        excluded_domains = []

    all_links = set()
    current_depth_links = {base_url}

    print("Starting with 1 link at depth 0")

    for depth in range(max_depth):
        next_depth_links = set()

        print(f"\nProcessing {len(current_depth_links)} links at depth {depth}")

        for i, link in enumerate(current_depth_links):
            print(f"  Processing link {i+1}/{len(current_depth_links)}: {link}")

            if is_document_url(link):
                print(f"Adding document to links but not crawling it: {link}")
                all_links.add(link)
                continue

            new_links = extract_links(link, cookies, username, password)

            if not new_links and global_cookies != cookies:
                print("Authentication refreshed, retrying link extraction")
                new_links = extract_links(link, global_cookies, username, password)

            new_links = {
                link
                for link in new_links
                if link not in excluded_domains and link not in all_links
            }

            next_depth_links.update(new_links)
            all_links.update(new_links)

            time.sleep(0.1)

        current_depth_links = next_depth_links

        print(f"Found {len(next_depth_links)} new unique links at depth {depth+1}")
        print(f"Total unique links so far: {len(all_links)}")

        output_file = f"scraper/gcoe_scrape/links_depth_{depth}.json"

        with open(output_file, "w") as f:
            json.dump(list(all_links), f, indent=4)
        print("All current links saved to scraper/gcoe_scrape/gcoe_links.json")

        if not current_depth_links:
            print(f"No more links to process. Stopping at depth {depth+1}")
            break

    all_links.add(base_url)

    return all_links


def extract_page_content(url, page_data):
    """Extract content from a page or document."""
    if is_document_url(url) and isinstance(page_data, dict):
        return {
            "url": url,
            "title": page_data.get("filename", "No title"),
            "date": "",
            "content": page_data.get("text_content", ""),
            "document_type": "pdf"
            if url.lower().endswith(".pdf")
            else "docx"
            if url.lower().endswith(".docx")
            else "unknown",
        }

    if page_data is None:
        return None

    title_element = (
        page_data.select_one("h1.entry-title")
        or page_data.select_one("h1")
        or page_data.title
    )
    title = title_element.text.strip() if title_element else "No title"

    date_element = page_data.select_one(".posted-on") or page_data.select_one(
        ".entry-date"
    )
    date = date_element.text.strip() if date_element else ""

    content_element = (
        page_data.select_one(".entry-content")
        or page_data.select_one("article")
        or page_data.select_one("main")
    )

    if content_element:
        for script in content_element(["script", "style"]):
            script.extract()

        content = content_element.get_text(separator="\n").strip()
        content = "\n".join(
            line.strip() for line in content.split("\n") if line.strip()
        )
    else:
        content = ""

    return {
        "url": url,
        "title": title,
        "date": date,
        "content": content,
        "document_type": "html",
    }


def get_llm_summary(markdown):
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes text.",
            },
            {"role": "user", "content": markdown},
        ],
    )
    return response.choices[0].message.content


def get_llm_keywords(markdown):
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that extracts keywords from text. These keywords are for a human to search against so make them simple. Return a comma separated list of up to 10 keywords.",
            },
            {"role": "user", "content": markdown},
        ],
    )
    output = response.choices[0].message.content

    # Clean up the output
    output = output.replace("- ", "")
    output = output.replace("  ", " ")
    output = output.replace("\n", " ")

    # Handle potential formatting issues
    keyword_list = [keyword.strip() for keyword in output.split(",") if keyword.strip()]

    # Add error handling to ensure we always return a list
    if not keyword_list:
        print("Warning: No keywords extracted, using fallback")
        # Extract some basic words as fallback
        words = " ".join(markdown.split()[:100]).split()
        unique_words = list(set([w.lower() for w in words if len(w) > 4]))[:10]
        keyword_list = unique_words

    return keyword_list


def process_batch_with_llm(items, batch_size=10):
    """Process items in batches to get summaries and keywords efficiently."""
    all_processed_items = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        print(
            f"Processing batch {i//batch_size + 1}/{(len(items) + batch_size - 1)//batch_size}"
        )

        processed_batch = []
        for item in batch:
            processed_item = {
                "source": item["url"],
                "title": item["title"],
                "markdown": item["content"],
            }
            processed_batch.append(processed_item)

        for idx, item in enumerate(batch):
            processed_batch[idx]["summary"] = get_llm_summary(item["content"])

        for idx, item in enumerate(batch):
            processed_batch[idx]["keywords"] = get_llm_keywords(item["content"])

        all_processed_items.extend(processed_batch)

    with open("scraper/gcoe_scrape/gcoe_wordpress_data_cleaned.json", "w") as f:
        json.dump(all_processed_items, f, indent=4)
    print("All items saved to scraper/gcoe_scrape/gcoe_wordpress_data_cleaned.json")

    return all_processed_items


def scrape_wordpress_site(
    base_url,
    output_file="wordpress_data.json",
    excluded_domains=None,
    max_depth=5,
    max_pages=None,
    cookies=None,
    username=None,
    password=None,
):
    """
    Scrape content from a WordPress site by following links
    """
    global global_cookies
    global_cookies = cookies or {}

    # print(f"Finding all links up to depth {max_depth}...")
    # all_links = find_links_to_depth(
    #     base_url, max_depth, global_cookies, excluded_domains, username, password
    # )
    with open("scraper/gcoe_scrape/links_depth_4.json", "r", encoding="utf-8") as f:
        all_links = json.load(f)

    print(f"We have found: {len(list(all_links))} links")

    links_to_scrape = list(all_links)

    if max_pages and len(links_to_scrape) > max_pages:
        print(f"Limiting to {max_pages} pages out of {len(links_to_scrape)} found")
        links_to_scrape = links_to_scrape[:max_pages]

    print(f"\nBeginning content scraping for {len(links_to_scrape)} pages...")

    scraped_data = []
    for i, link in enumerate(links_to_scrape):
        print(f"Scraping page {i+1}/{len(links_to_scrape)}: {link}")
        page_data = request_page_content(link, global_cookies, username, password)

        if global_cookies != cookies:
            cookies = global_cookies

        if page_data:
            extracted_page_data = extract_page_content(link, page_data)
            if extracted_page_data:
                scraped_data.append(extracted_page_data)
                print(f"  Title: {extracted_page_data['title'][:50]}...")

        time.sleep(0.1)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(scraped_data, f, ensure_ascii=False, indent=2)

    print(f"Scraped {len(scraped_data)} pages. Data saved to {output_file}")
    return scraped_data


if __name__ == "__main__":
    word_press_site = "https://gcoe.civilservice.gov.uk/"

    username = os.getenv("GCOE_USERNAME")
    password = os.getenv("GCOE_PASSWORD")

    if not username or not password:
        print("WARNING: Username or password not set in environment variables.")
        print(
            "Set GCOE_USERNAME and GCOE_PASSWORD environment variables for automatic cookie refresh."
        )
    else:
        print(f"Using credentials for user: {username}")

    excluded_domains = []
    try:
        with open("scraper/excluded_gcoe_domains.json", "r") as f:
            excluded_domains = list(json.load(f)["excluded_domains"])
        print(f"Loaded {len(excluded_domains)} excluded domains")
    except Exception as e:
        print(f"Could not load excluded domains: {e}")

    output_file = "scraper/gcoe_scrape/gcoe_wordpress_data.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    scraped_data = scrape_wordpress_site(
        word_press_site,
        output_file,
        excluded_domains,
        max_depth=5,
        max_pages=1000,
        cookies={},
        username=username,
        password=password,
    )

    grants_gcoe_data = process_batch_with_llm(scraped_data, batch_size=50)
