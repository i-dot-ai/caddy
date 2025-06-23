import boto3
import json
import os
import PyPDF2
from pathlib import Path
from typing import List
from openai import AzureOpenAI
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def upload_to_s3(file_path: str, bucket: str, s3_key: str) -> str:
    """
    Upload a file to S3 bucket and return the S3 URL

    Args:
        file_path: Local path to the file
        bucket: S3 bucket name
        s3_key: S3 object key (path in bucket)

    Returns:
        str: S3 URL of the uploaded file
    """
    s3_client = boto3.client("s3")
    try:
        s3_client.upload_file(file_path, bucket, s3_key)
        s3_url = f"s3://{bucket}/{s3_key}"
        print(f"Successfully uploaded {file_path} to {s3_url}")
        return s3_url
    except ClientError as e:
        print(f"Error uploading file to S3: {e}")
        return ""


def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt template from the prompts directory

    Args:
        prompt_name: Name of the prompt file without extension

    Returns:
        str: The prompt template
    """
    prompt_path = Path(__file__).parent / "prompts" / f"{prompt_name}.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")


def generate_summary(content: str, client: AzureOpenAI) -> tuple[str, List[str]]:
    """
    Generate a summary and keywords using OpenAI
    Args:
        content: The text content to summarize
        client: OpenAI client instance

    Returns:
        tuple: (summary, keywords list)
    """
    prompt_template = load_prompt("summary_prompt")
    prompt = prompt_template.format(
        content=content[:4000],
    )  # Limiting content length for API

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_MINI_DEPLOYMENT_NAME"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        result = json.loads(response.choices[0].message.content)
        return result["summary"], result["keywords"]
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "", []


def get_openai_client():
    """
    Get Azure OpenAI client using environment variables
    """
    return AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION"),
    )


def process_pdf_directory(pdf_dir: str, output_file: str, s3_bucket: str) -> None:
    """Process all PDFs into a single JSON file and upload PDFs to S3."""
    Path(pdf_dir).parent.mkdir(parents=True, exist_ok=True)

    # Initialize OpenAI client
    client = get_openai_client()

    documents = []

    # Process each PDF file
    for filename in os.listdir(pdf_dir):
        pdf_path = Path(pdf_dir) / filename
        print(f"Processing {filename}...")

        # Upload PDF to S3
        s3_key = f"pdfs/{filename}"
        s3_url = upload_to_s3(str(pdf_path), s3_bucket, s3_key)

        if not s3_url:
            continue

        # Read PDF content
        content = read_pdf(pdf_path)

        # Generate summary and keywords using OpenAI
        summary, keywords = generate_summary(content, client)

        # Create document in required format
        document = {
            "source": s3_url,
            "markdown": content,
            "title": filename.replace(".pdf", ""),
            "keywords": keywords,
            "summary": summary,
        }

        documents.append(document)
        print(f"Processed {filename}")

    # Save all documents to a single JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    # Upload the combined JSON file to S3
    upload_to_s3(output_file, s3_bucket, "combined_documents.json")


def read_pdf(file_path):
    try:
        with Path(file_path).open("rb") as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        return text
    except PyPDF2.errors.PdfReadError as e:
        print(f"Error reading PDF {file_path}: {e}")
        return ""


if __name__ == "__main__":
    # Update these paths as needed
    PDF_DIRECTORY = "scraper/folder/pdfs"
    OUTPUT_FILE = "scraper/folder/output.json"
    S3_BUCKET = ""  # Replace with your S3 bucket name

    process_pdf_directory(PDF_DIRECTORY, OUTPUT_FILE, S3_BUCKET)
