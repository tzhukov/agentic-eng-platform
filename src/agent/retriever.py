import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "172.18.255.200")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "internal_docs"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

class Retriever:
    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    def retrieve(self, query: str, top_k: int = 3):
        """Search for relevant document chunks in Qdrant."""
        query_vector = self.model.encode(query).tolist()
        
        search_result = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k
        ).points
        
        results = []
        for res in search_result:
            results.append({
                "text": res.payload["text"],
                "source": res.payload["source"],
                "score": res.score
            })
        return results

if __name__ == "__main__":
    # Quick verification
    retriever = Retriever()
    test_query = "How can I become an AI engineer as a backend developer?"
    print(f"Query: {test_query}")
    matches = retriever.retrieve(test_query)
    for i, match in enumerate(matches):
        print(f"\nMatch {i+1} (Score: {match['score']:.4f}, Source: {match['source']}):")
        print(f"{match['text'][:200]}...")
