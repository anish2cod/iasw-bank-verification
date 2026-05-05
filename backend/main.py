"""FastAPI main application for IASW - Intelligent Account Servicing Workflow."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS, API_PREFIX, LLM_PROVIDER
from backend.models.database import init_db
from backend.routers import intake_router, checker_router, status_router
from backend.services.llm_service import llm_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("IASW Backend starting up...")
    init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("IASW Backend shutting down...")


# Create FastAPI app
app = FastAPI(
    title="IASW - Intelligent Account Servicing Workflow",
    description="""
    AI-powered account servicing workflow with Human-in-the-Loop approval.

    ## Features
    - **Intake**: Submit name change requests with supporting documents
    - **AI Verification**: Automated document processing and confidence scoring
    - **Checker Dashboard**: Human review and approval workflow
    - **Audit Trail**: Complete logging of all actions

    ## Workflow
    1. Staff submits request via Intake API
    2. AI processes document and generates verification scores
    3. Request queued for human review (HITL)
    4. Checker approves/rejects
    5. Approved changes update core banking (RPS)
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(intake_router, prefix=API_PREFIX)
app.include_router(checker_router, prefix=API_PREFIX)
app.include_router(status_router, prefix=API_PREFIX)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "IASW - Intelligent Account Servicing Workflow",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "api_prefix": API_PREFIX,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get(f"{API_PREFIX}/llm/status")
async def llm_status():
    """Get LLM provider status."""
    return llm_service.get_status()


@app.get(f"{API_PREFIX}/llm/test")
async def llm_test():
    """Test LLM with a simple prompt."""
    response = llm_service.generate("Say 'Hello from IASW!' in exactly those words.")
    return {
        "provider": llm_service.get_provider_name(),
        "response": response,
        "available": llm_service.is_available(),
    }


@app.get(f"{API_PREFIX}/info")
async def api_info():
    """Get API information and available endpoints."""
    return {
        "api_version": "v1",
        "endpoints": {
            "intake": {
                "submit": f"{API_PREFIX}/intake/submit",
                "submit_json": f"{API_PREFIX}/intake/submit-json",
            },
            "checker": {
                "pending": f"{API_PREFIX}/checker/pending",
                "request_detail": f"{API_PREFIX}/checker/request/{{request_id}}",
                "action": f"{API_PREFIX}/checker/request/{{request_id}}/action",
                "stats": f"{API_PREFIX}/checker/stats",
            },
            "status": {
                "request": f"{API_PREFIX}/status/request/{{request_id}}",
                "customer": f"{API_PREFIX}/status/customer/{{customer_id}}",
                "audit": f"{API_PREFIX}/status/audit/{{request_id}}",
                "all": f"{API_PREFIX}/status/all",
                "rps_customer": f"{API_PREFIX}/status/rps/customer/{{customer_id}}",
                "rps_history": f"{API_PREFIX}/status/rps/history/{{customer_id}}",
            },
        },
        "supported_document_types": [
            "MARRIAGE_CERTIFICATE",
            "COURT_ORDER",
            "GOVERNMENT_ID",
        ],
        "request_statuses": [
            "SUBMITTED",
            "VALIDATING",
            "PROCESSING_DOCUMENTS",
            "SCORING",
            "AI_VERIFIED_PENDING_HUMAN",
            "AI_FLAGGED_PENDING_HUMAN",
            "APPROVED",
            "REJECTED",
            "ERROR",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
