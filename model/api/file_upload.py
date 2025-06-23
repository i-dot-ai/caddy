import concurrent.futures
import json
import mimetypes
import os
import tempfile
from logging import getLogger
from uuid import UUID

import requests
import tqdm

logger = getLogger(__file__)


class FileUpload:
    """uploads files one-at-a-time to caddy from a local dir.
    This can upload json files containing scraped documents to upload, or individual files from a directory"""

    def __init__(
        self,
        token: str,
        collection_name: str,
        directory,
        url,
        delete_existing_collection=True,
        batch_size=1,
        collection_description=None,
        jwt=None,
    ):
        self.token = token
        self.collection_name = collection_name
        self.collection_description = collection_description or collection_name
        self.directory = directory
        self.url = url
        self.batch_size = batch_size
        self.delete_existing_collection = delete_existing_collection
        self.jwt = jwt
        self.temp_dir = None

    def create_temp_files_from_json(self, json_file_path):
        """Creates temporary files for upload from a JSON file"""
        with open(json_file_path, "r", encoding="utf-8") as f:
            documents = json.load(f)

        print(
            f"Found {len(documents)} documents in JSON file: {os.path.basename(json_file_path)}"
        )

        file_names = []

        for i, doc in enumerate(documents):
            content = doc.get("markdown", "")
            title = doc.get("title", f"Document_{i}")
            source = doc.get("source", "")
            # Handle additional fields from your scraped data
            markdown_length = doc.get("markdown_length", 0)
            linked_urls = doc.get("linked_urls", [])

            # Skip empty content
            if not content.strip():
                print(f"Skipping document {i} with title '{title}' - empty content")
                continue

            safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip()
            safe_title = safe_title[:50]
            if not safe_title:
                safe_title = f"Document_{i}"

            # Include file path to make filenames unique across multiple JSON files
            json_basename = os.path.splitext(os.path.basename(json_file_path))[0]
            file_name = f"{json_basename}_{i}_{safe_title}.md"

            file_path = os.path.join(self.temp_dir.name, file_name)
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    if source:
                        f.write(f"<!-- Source: {source} -->\n")
                    if markdown_length:
                        f.write(f"<!-- Markdown Length: {markdown_length} -->\n")
                    if linked_urls:
                        f.write(f"<!-- Linked URLs: {', '.join(linked_urls)} -->\n")
                    f.write("\n")
                    f.write(content)
                file_names.append(file_name)
            except (IOError, OSError) as e:
                print(
                    f"Error creating file for document {i} with title '{title}': {str(e)}"
                )

        return file_names

    def fetch_files(self):
        """fetch files from the directory, or from json files if they exist"""
        files_to_process = os.listdir(self.directory)
        if not files_to_process:
            raise ValueError("No files found in directory")

        # Check if we have JSON files to process
        json_files = [f for f in files_to_process if f.endswith(".json")]

        if json_files:
            print(f"Found {len(json_files)} JSON files to process")
            self.temp_dir = tempfile.TemporaryDirectory()
            all_file_names = []

            for json_file in json_files:
                json_file_path = os.path.join(self.directory, json_file)
                file_names = self.create_temp_files_from_json(json_file_path)
                all_file_names.extend(file_names)

            print(
                f"Created {len(all_file_names)} total files for upload from {len(json_files)} JSON files"
            )
            self.directory = self.temp_dir.name
            return all_file_names
        else:
            # Handle regular files
            return files_to_process

    def upload_file_batch(self, collection_id, file_batch):
        """Upload a batch of files concurrently"""
        headers = {"x-external-access-token": self.token, "accept": "application/json"}
        if self.jwt:
            headers["Authorization"] = self.jwt
        failures = []

        def upload_single_file(file_name):
            try:
                file_path = os.path.join(self.directory, file_name)
                with open(file_path, "rb") as file:
                    mime_type, _ = mimetypes.guess_type(file_path)
                    files = {"file": (file_name, file, mime_type)}
                    response = requests.post(
                        f"{self.url}/collections/{collection_id}/resources",
                        files=files,
                        headers=headers,
                    )
                    if response.status_code != 201:
                        return file_name, response.content
                    return None
            except Exception as e:
                return file_name, str(e)

        # Upload files in the batch concurrently
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(file_batch), 10)
        ) as executor:
            future_to_file = {
                executor.submit(upload_single_file, file_name): file_name
                for file_name in file_batch
            }

            for future in concurrent.futures.as_completed(future_to_file):
                result = future.result()
                if result is not None:
                    failures.append(result)

        return failures

    def run(self) -> UUID:
        """Upload documents to caddy collection"""
        logger.info("Running document upload")
        headers = {"x-external-access-token": self.token, "accept": "application/json"}
        if self.jwt:
            headers["Authorization"] = self.jwt
        # Check for existing collection with the same name
        response = requests.get(f"{self.url}/collections", headers=headers)

        # Output initial request here so we can diagnose connection issues
        logger.info(f"Initial upload file response is {response.json()}")

        try:
            collection_id = next(
                x["id"]
                for x in response.json()["collections"]
                if x["name"] == self.collection_name
            )
        except StopIteration:
            collection_id = None

        if collection_id and self.delete_existing_collection:
            requests.delete(
                f"{self.url}/collections/{collection_id}", headers=headers
            ).raise_for_status()

        if not collection_id:
            response = requests.post(
                f"{self.url}/collections",
                json={
                    "name": self.collection_name,
                    "description": "grants and evaluations",
                },
                headers=headers,
            )
            response.raise_for_status()
            collection_id = response.json()["id"]

        files_to_process = self.fetch_files()
        total_failures = []

        print(
            f"Processing {len(files_to_process)} files in batches of {self.batch_size}..."
        )

        # Process files in batches
        for i in tqdm.tqdm(
            range(0, len(files_to_process), self.batch_size), desc="Processing batches"
        ):
            batch = files_to_process[i : i + self.batch_size]
            batch_failures = self.upload_file_batch(collection_id, batch)
            total_failures.extend(batch_failures)

            if batch_failures:
                print(
                    f"Batch {i//self.batch_size + 1} had {len(batch_failures)} failures"
                )

        failure_count = len(total_failures)

        # Print detailed failure information
        if total_failures:
            print(f"\nTotal failures: {failure_count}")
            for file_name, error in total_failures:
                print(f"Error for {file_name}: {error}")

        if self.temp_dir:
            self.temp_dir.cleanup()

        resources = requests.get(
            f"{self.url}/collections/{collection_id}/resources", headers=headers
        )
        resources.raise_for_status()

        expected_number_of_resources = len(files_to_process) - failure_count
        actual_number_of_resources = resources.json()["total"]

        if actual_number_of_resources != expected_number_of_resources:
            raise ValueError(
                f"found {actual_number_of_resources} resources, expected {expected_number_of_resources}"
            )

        return UUID(collection_id)
