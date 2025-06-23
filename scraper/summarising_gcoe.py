import json
from openai import AzureOpenAI
import os

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-12-01-preview",
)


def get_summary(markdown):
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


def get_keywords(markdown):
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
    output = output.replace("- ", "")
    output = output.replace("  ", "")
    output = output.replace("\n")
    keyword_list = output.split(",")
    return keyword_list


def process_batch(items, batch_size=10):
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
            processed_batch[idx]["summary"] = get_summary(item["content"])

        for idx, item in enumerate(batch):
            processed_batch[idx]["keywords"] = get_keywords(item["content"])

        all_processed_items.extend(processed_batch)

    return all_processed_items


# Load data
with open("scraper/gcoe_scrape/gcoe_wordpress_data_cleaned.json", "r") as f:
    data = json.load(f)

# # Process data in batches
# grants_gcoe_data = process_batch(data, batch_size=10)

# # Save processed data
# with open("scraper/gcoe_scrape/gcoe_wordpress_data_cleaned.json", "w") as f:
#     json.dump(grants_gcoe_data, f, indent=4)

# for item in data:
#     item["keywords"] = [re.sub("\d. ", "", keyword) for keyword in item["keywords"]]
#     item["keywords"] = [re.sub("\d", "", keyword) for keyword in item["keywords"]]

# with open("scraper/gcoe_scrape/gcoe_wordpress_data_cleaned.json", "w") as f:
#       json.dump(data, f, indent=4)

scraped_data = []
for item in data:
    scraped_data.append(
        {
            "source": item["source"],
            "title": item["title"],
        }
    )

with open("scraper/gcoe_scrape/gcoe_wordpress_data_cleaned_titles.json", "w") as f:
    json.dump(scraped_data, f, indent=4)
