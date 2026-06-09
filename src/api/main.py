import logging
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.agent.graph import app as agent_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Self-Correction Support Agent API")

# Configure CORS for the Web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    result: str
    stdout: str
    code: str

@app.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    try:
        inputs = {"query": request.query, "retry_count": 0}

        # Invoke the agent to get the full final state
        final_state = agent_app.invoke(inputs)

        # Log the final state for debugging
        logger.info(f"Final state: {final_state}")

        # Extract results from final state
        result = final_state.get("execution_result", "Unknown")
        stdout = final_state.get("stdout", "")
        generated_code = final_state.get("generated_code", "")
        error_logs = final_state.get("error_logs", "")

        if result == "Error":
            logger.error(f"Agent execution failed: {error_logs}")

        return QueryResponse(result=result, stdout=stdout, code=generated_code)

    except Exception as e:
        logger.exception("Agent execution failed with exception")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/healthz")
async def health():
    return {"status": "ok"}

# Serve static files for SPA (Frontend)
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
logger.info(f"Serving static files from: {static_dir}")

# Mount the static directory at the root
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/{rest_of_path:path}")
async def serve_spa(rest_of_path: str):
    # This acts as a fallback for SPA routing
    return FileResponse(os.path.join(static_dir, "index.html"))

