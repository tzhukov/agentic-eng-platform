import logging
import os
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.agent.graph import app as agent_app
from src.agent.metrics import register_litellm_callback
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

# Initialize LiteLLM cost tracking callback
register_litellm_callback()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics
REQUESTS = Counter("http_requests_total", "Total requests", ["method", "endpoint", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request duration", ["method", "endpoint"])

app = FastAPI(title="Self-Correction Support Agent API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_metrics(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    with LATENCY.labels(method=method, endpoint=endpoint).time():
        response = await call_next(request)
        REQUESTS.labels(method=method, endpoint=endpoint, status=response.status_code).inc()
    return response

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
        final_state = agent_app.invoke(inputs)
        
        result = final_state.get("execution_result", "Unknown")
        stdout = final_state.get("stdout", "")
        generated_code = final_state.get("generated_code", "")

        return QueryResponse(result=result, stdout=stdout, code=generated_code)

    except Exception as e:
        logger.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.get("/debug/fail")
async def debug_fail():
    """Simulates a 500 error for SLO testing."""
    logger.error("DEBUG: Explicit failure requested via /debug/fail")
    raise HTTPException(status_code=500, detail="Debug failure")

@app.get("/debug/slow")
async def debug_slow(delay: float = 10.0):
    """Simulates a slow response for SLO testing."""
    import asyncio
    logger.info(f"DEBUG: Sleeping for {delay}s via /debug/slow")
    await asyncio.sleep(delay)
    return {"status": "slow", "delay": delay}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Serve static files for SPA
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/{rest_of_path:path}")
async def serve_spa(rest_of_path: str = ""):
    return FileResponse(os.path.join(static_dir, "index.html"))
