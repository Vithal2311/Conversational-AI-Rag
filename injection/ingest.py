"""Read S3 guides, chunk and embed them, then upload to Pinecone."""

import hashlib
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from workflow_logging import logged_step, logger
from injection.chunking import split_into_chunks
from injection.document_metadata import extract_document_metadata

DOMAIN_NAMESPACE = {
    "Human Resources": "hr",
    "Finance": "finance",
    "IT Support": "it",
}


@logged_step
def main():
    import boto3
    from botocore.config import Config
    from dotenv import load_dotenv
    from pinecone import Pinecone

    from injection.embedding import embed_chunks

    load_dotenv(PROJECT_ROOT / ".env")
    required = (
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME",
        "OPENAI_API_KEY", "PINECONE_API_KEY", "PINECONE_INDEX_NAME",
    )
    for name in required:
        if not os.getenv(name):
            raise ValueError(f"Missing {name} in .env")

    bucket = os.environ["S3_BUCKET_NAME"]
    s3 = boto3.client(
        "s3",
        region_name=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"),
        config=Config(connect_timeout=10, read_timeout=30,
                      retries={"total_max_attempts": 2}),
    )
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    description = pc.describe_index(os.environ["PINECONE_INDEX_NAME"])
    if description.dimension != 1536 or description.metric != "cosine":
        raise ValueError("Use a dense index with 1536 dimensions and cosine metric.")
    if not description.status["ready"]:
        raise RuntimeError("Pinecone index is not ready. Try again shortly.")
    index = pc.Index(host=description.host)

    file_count = vector_count = 0
    pages = s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=os.getenv("S3_PREFIX", "")
    )
    for page in pages:
        for item in page.get("Contents", []):
            filename = item["Key"]
            if not filename.lower().endswith(".txt"):
                continue
            logger.info("s3 document read started document_number=%d", file_count + 1)
            body = s3.get_object(Bucket=bucket, Key=filename)["Body"]
            try:
                text = body.read().decode("utf-8-sig")
            finally:
                body.close()

            # Parse once; every chunk inherits its document's header values.
            document_metadata = extract_document_metadata(text)
            owner = document_metadata["owner"]
            if owner not in DOMAIN_NAMESPACE:
                raise ValueError(f"No Pinecone namespace configured for owner: {owner!r}")
            namespace = DOMAIN_NAMESPACE[owner]
            chunks = split_into_chunks(text, chunk_size=200, overlap=40)
            file_id = hashlib.sha256(
                f"{bucket}/{filename}".encode("utf-8")
            ).hexdigest()
            logger.info("document chunked namespace=%s chunk_count=%d", namespace, len(chunks))

            for start in range(0, len(chunks), 32):
                batch = chunks[start:start + 32]
                logger.info("embedding batch started chunk_count=%d", len(batch))
                embeddings = embed_chunks(batch)
                if len(embeddings) != len(batch):
                    raise RuntimeError("Embedding count does not match chunks.")
                vectors = []
                for offset, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                    if len(embedding) != 1536:
                        raise ValueError("Expected 1536-dimensional embedding.")
                    chunk_number = start + offset + 1
                    vectors.append({
                        "id": f"{file_id}-{chunk_number}",
                        "values": embedding,
                        "metadata": {
                            "text": chunk,
                            "document_id": document_metadata["document_id"],
                            "title": document_metadata["title"],
                            "version": document_metadata["version"],
                            "effective_date": document_metadata["effective_date"],
                            "owner": document_metadata["owner"],
                            "audience": document_metadata["audience"],
                        },
                    })
                logger.info("pinecone upsert started namespace=%s vector_count=%d", namespace, len(vectors))
                index.upsert(vectors=vectors, namespace=namespace)
                logger.info("pinecone upsert completed namespace=%s vector_count=%d", namespace, len(vectors))
                vector_count += len(vectors)
            file_count += 1

    logger.info("ingestion completed file_count=%d vector_count=%d", file_count, vector_count)


if __name__ == "__main__":
    main()

