import os
import sqlite3
from pathlib import Path
from typing import Final

import openai
import polars as pl
from dotenv import load_dotenv

from classes import SWEBenchEntry

load_dotenv(override=True)

SWEBENCH_DB_PATH: Final[Path] = Path('../swebench_entries.db')
OPENAI_CLIENT = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))


def fetch_unused_issue() -> SWEBenchEntry:
    # Select a random issue with the USED flag set to False
    conn = sqlite3.connect(SWEBENCH_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        '''
            SELECT * FROM swebench_entries ORDER BY RANDOM() LIMIT 1
            '''
        )

    issue = cursor.fetchone()

    columns = [description[0] for description in cursor.description]

    conn.commit()
    conn.close()

    issue = dict(zip(columns, issue))

    return SWEBenchEntry.model_validate(issue)


def obfuscate(swebench_entry: SWEBenchEntry) -> str:
    """Rephrases the problem statement in a way that is still very clear but makes it hard to know what the original problem statement was."""
    print(f"Obfuscating issue {swebench_entry.instance_id}...")
    response = OPENAI_CLIENT.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a program that rephrases problem statements in a way that is still very clear but makes it hard to know what the original problem statement was."},
            {"role": "user", "content": f"Please rephrase the following problem statement:\n\n{swebench_entry.problem_statement}"}
        ]
    )
    print(f"Finished obfuscating issue {swebench_entry.instance_id}")
    return response.choices[0].message.content


def pull_all_swebench_entries():
    print(f"Pulling all SWEBench entries to {SWEBENCH_DB_PATH}")
    # Define the splits
    splits = {
        'train': 'data/train-*.parquet',
        'dev': 'data/dev-00000-of-00001.parquet',
        'test': 'data/test-00000-of-00001.parquet',
        'validation': 'data/validation-00000-of-00001.parquet'
    }

    # Create a SQLite database
    conn = sqlite3.connect(SWEBENCH_DB_PATH)
    cursor = conn.cursor()

    # Create the table
    cursor.execute(
        '''
            CREATE TABLE IF NOT EXISTS swebench_entries (
                instance_id TEXT PRIMARY KEY,
                text TEXT,
                repo TEXT,
                base_commit TEXT,
                problem_statement TEXT,
                hints_text TEXT,
                created_at TEXT,
                patch TEXT,
                test_patch TEXT,
                version TEXT,
                FAIL_TO_PASS TEXT,
                PASS_TO_PASS TEXT,
                environment_setup_commit TEXT
            )
           '''
        )

    # Read and insert data from each split
    for split, path in splits.items():
        df = pl.read_parquet(f'hf://datasets/princeton-nlp/SWE-bench_oracle/{path}')

        for row in df.iter_rows(named=True):
            cursor.execute(
                '''
                            INSERT OR REPLACE INTO swebench_entries VALUES (
                                :instance_id, :text, :repo, :base_commit, :problem_statement,
                                :hints_text, :created_at, :patch, :test_patch, :version,
                                :FAIL_TO_PASS, :PASS_TO_PASS, :environment_setup_commit
                            )
                            ''', row
                )

    # Commit changes and close connection
    conn.commit()
    conn.close()

    print(f"All SWEBench entries have been pulled and stored in {SWEBENCH_DB_PATH}")


import requests
import boto3
import os
from urllib.parse import urlparse
from botocore.exceptions import NoCredentialsError, ClientError


def upload_repo_at_given_commit(repo_url, commit_hash, bucket_name):
    """
    Fetches the codebase of a GitHub repository at a specific commit and uploads it to an S3 bucket.

    Parameters:
    - repo_url (str): The URL of the GitHub repository.
    - commit_hash (str): The commit hash to fetch.
    - bucket_name (str): The name of the S3 bucket to upload to.
    - s3_object_key (str, optional): The S3 object key (file name). Defaults to the archive name.

    Returns:
    - None
    """

    # Parse the repository owner and name from the URL
    parsed_url = urlparse(repo_url)
    path_parts = parsed_url.path.strip('/').split('/')
    if len(path_parts) < 2:
        raise ValueError("Invalid repository URL.")
    owner, repo = path_parts[:2]

    # Construct the download URL
    archive_name = f"{owner}-{repo}-{commit_hash}.zip"
    download_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{commit_hash}"

    # Set up headers for authentication if token is provided
    headers = {}

    # Download the archive
    print(f"Downloading archive from {download_url}...")
    response = requests.get(download_url, headers=headers, stream=True)
    if response.status_code == 200:
        with open(archive_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Archive downloaded successfully as {archive_name}.")
    else:
        raise Exception(f"Failed to download archive: {response.status_code} {response.reason}")

    # Upload to S3
    s3_client = boto3.client('s3')

    try:
        print(f"Uploading {archive_name} to s3://{bucket_name}/{archive_name}...")
        s3_client.upload_file(archive_name, bucket_name, archive_name)
        print("Upload completed successfully.")
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {archive_name} was not found.")
    except NoCredentialsError:
        raise NoCredentialsError("AWS credentials not available.")
    except ClientError as e:
        raise Exception(f"Failed to upload to S3: {e}")

    # Clean up the downloaded archive
    os.remove(archive_name)
    print(f"Cleaned up local file {archive_name}.")


def fetch_all_repos():
    # Fetch all repositories from the database
    conn = sqlite3.connect(SWEBENCH_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        '''
            SELECT repo, base_commit FROM swebench_entries
            '''
        )

    for repo, base_commit in cursor.fetchall():
        repo_url = f"https://github.com/{repo}"
        upload_repo_at_given_commit(repo_url, base_commit, "codeatcommits")

    conn.close()
