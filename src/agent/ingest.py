import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import glob

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "internal_docs"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

def main():
    # 1. Initialize Clients
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    
    # 2. Create Collection (if it doesn't exist)
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not exists:
        print(f"Creating collection: {COLLECTION_NAME}")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=384, # all-MiniLM-L6-v2 vector size
                distance=models.Distance.COSINE
            ),
        )
    else:
        print(f"Collection {COLLECTION_NAME} already exists.")

    # 3. Read and Chunk Documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )

    doc_paths = glob.glob("docs/*.md")
    points = []
    point_id = 0

    for path in doc_paths:
        print(f"Processing: {path}")
        with open(path, "r") as f:
            content = f.read()
            chunks = text_splitter.split_text(content)
            
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = model.encode(chunk).tolist()
                
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "text": chunk,
                            "source": path,
                            "chunk_id": i
                        }
                    )
                )
                point_id += 1

    # 4. Upsert into Qdrant
    if points:
        print(f"Upserting {len(points)} points into Qdrant...")
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print("Ingestion complete.")
    else:
        print("No documents found to ingest.")

if __name__ == "__main__":
    main()
