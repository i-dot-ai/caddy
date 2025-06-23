"""
This is an example script on how to use the Caddy API.
This performs test queries against a Caddy index and uses an LLM to evaluate the relevance
of the search results. You will want to change the queries and index based on your needs.

The script:
1. Makes test queries to the Caddy search API
2. Uses Azure OpenAI to evaluate if the top 3 results are relevant to each query
3. Prints the results and LLM judgements
"""

import argparse
import json
import os

import requests
from openai import AzureOpenAI

url = str(os.getenv("CADDY_URL")) + "/search"
api_key = os.getenv("CADDY_API_KEY")

queries_dict = {
    "test_query_1": "What has the centre of excellence done with Redbox",
    "test_query_2": "What is the difference between the basic, short-form and long-form Model Grant Funding Agreements.",
    "test_query_3": "Summarise the 10 Minimum Requirements",
    "test_query_4": "What is CGAP, and does my scheme need to attend?",
    "test_query_5": "What is GGiS, and how do I access it?",
    "test_query_6": "What are the six operating model components of the Grants Functional Blueprint?",
}

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-12-01-preview",
)

SYSTEM_PROMPT = """
You are an expert assistant that makes a judgement whether a result can be used to answer the question.

You will see the top three results from a search api and read them fully to see if they could be used to answer the query being raised.

You must respond with a json output with an argument and then bool answer.
{{
    "argument": "the query can be answered fully as the second response makes reference to the scheme raised by the query",
    "answer": True
}}

Results:
{search_results}

Query:
{query}
"""


def llm_judges_whether_top_result_is_relevant(results, query, client, prompt):
    # Format the prompt with the search results and query
    formatted_prompt = prompt.format(
        search_results=json.dumps(results[:3], indent=2), query=query
    )

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": formatted_prompt,
            },
            {
                "role": "user",
                "content": "Please analyze these search results and determine if they answer the query.",
            },
        ],
    )

    response_content = response.choices[0].message.content

    # Try to parse the response as JSON
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        print(f"Warning: Could not parse LLM response as JSON: {response_content}")
        # Return a default response
        return {"argument": "Error parsing LLM response", "answer": False}


def question_caddy_api(query, index, api_key):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "x-external-access-token": api_key,
    }
    payload = {"query": query, "index_name": index}

    print(f"Asking Caddy to search for: {query} in index: {index}")

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        return json.dumps(data, indent=2)
    else:
        print(f"Error: {response.status_code} - {response.text}")


def run(index_name):
    responses = []
    llm_judgements = []

    for query in queries_dict:
        search_results = question_caddy_api(
            query=queries_dict[query], index=index_name, api_key=api_key
        )
        search_result_json = json.loads(search_results)
        responses.append(search_result_json)
        llm_judgements.append(
            llm_judges_whether_top_result_is_relevant(
                results=search_result_json[:3],
                query=queries_dict[query],
                client=client,
                prompt=SYSTEM_PROMPT,
            )
        )
        print(
            "Top 3 caddy search results:", json.dumps(search_result_json[:3], indent=2)
        )
        print("Has Caddy found relevant material:", llm_judgements[-1]["answer"])
        print(f"LLM argument: {llm_judgements[-1]['argument']}")

    print(
        f"LLM judgements: {[llm_judgement['answer'] for llm_judgement in llm_judgements]}"
    )


def main():
    parser = argparse.ArgumentParser(description="Test Caddy search API")
    parser.add_argument(
        "--index", type=str, default="grants", help="Caddy index name to search against"
    )
    args = parser.parse_args()

    index_name = args.index
    run(index_name)


if __name__ == "__main__":
    main()
