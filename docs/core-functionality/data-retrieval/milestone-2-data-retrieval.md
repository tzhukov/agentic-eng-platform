# Milestone 2: Data & Retrieval (Backend)

## Overview
Goal: Implement the semantic search capability using Qdrant for document retrieval (RAG).

## Work Performed
- [x] Initialize Python environment (venv + pip).
- [x] Configure Qdrant collection for internal documentation.
- [x] Implement ingestion pipeline (chunking + embedding).
- [x] Develop `RetrieveDocs` tool for LangGraph (using `query_points`).

## Proof of Completion
- [x] `requirements.txt` generated.
- [x] Qdrant collection `internal_docs` created.
- [x] Successful execution of `src/agent/ingest.py` (15 points upserted).
- [x] Successful execution of `src/agent/retriever.py` with relevant results for the query "How can I become an AI engineer as a backend developer?".
- [x] Qdrant exposed via LoadBalancer IP `172.18.255.200`.
