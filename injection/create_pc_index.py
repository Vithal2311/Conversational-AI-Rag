import os
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec



env_path = Path(__file__).resolve().parents[1] / ".env"
print("Looking for:", env_path)
print("File exists:", env_path.is_file())
load_dotenv(env_path)

api_key = os.getenv("PINECONE_API_KEY")
if not api_key:
    raise ValueError("Add PINECONE_API_KEY to your .env file.")

pc = Pinecone(api_key=api_key)
index_name = "company-doc-openai"

if index_name in pc.list_indexes().names():
    print(f"Index already exists: {index_name}")
else:
    pc.create_index(
        name=index_name,
        vector_type="dense",
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1",
        ),
    )
    print(f"Index creation requested: {index_name}")
