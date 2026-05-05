"""LangGraph Orchestrator - Coordinates the AI verification pipeline."""

import logging
import time
from typing import Dict, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass, asdict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agents.validation_agent import ValidationAgent
from backend.agents.document_processor import DocumentProcessorAgent
from backend.agents.confidence_scorer import ConfidenceScorerAgent
from backend.agents.summary_generator import SummaryGeneratorAgent
from backend.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """State passed between workflow nodes."""
    # Input
    request_id: str
    customer_id: str
    old_name: str
    new_name: str
    document_path: Optional[str]
    document_type: str

    # Validation results
    validation_result: Optional[Dict[str, Any]]
    is_valid: bool

    # Document processing results
    extraction_result: Optional[Dict[str, Any]]
    extracted_fields: Optional[Dict[str, Any]]

    # Scoring results
    scoring_result: Optional[Dict[str, Any]]

    # Summary
    summary_result: Optional[Dict[str, Any]]

    # Final output
    recommendation: str
    status: str
    error: Optional[str]
    processing_time_ms: int


class WorkflowOrchestrator:
    """
    LangGraph-based orchestrator for the verification workflow.

    Pipeline:
    1. Validate customer in RPS
    2. Process document (OCR + extraction)
    3. Calculate confidence scores
    4. Generate summary
    5. Return recommendation
    """

    def __init__(self, llm_provider: str = None):
        self.validation_agent = ValidationAgent()
        self.document_processor = DocumentProcessorAgent(llm_provider)
        self.confidence_scorer = ConfidenceScorerAgent(llm_provider)
        self.summary_generator = SummaryGeneratorAgent(llm_provider)
        # Injected per run() call to report intermediate pipeline stages
        self._status_callback = None

        # Build the graph
        self.graph = self._build_graph()
        self.checkpointer = MemorySaver()
        self.app = self.graph.compile(checkpointer=self.checkpointer)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("validate", self._validate_node)
        workflow.add_node("process_document", self._process_document_node)
        workflow.add_node("calculate_scores", self._calculate_scores_node)
        workflow.add_node("generate_summary", self._generate_summary_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # Set entry point
        workflow.set_entry_point("validate")

        # Add conditional edges
        workflow.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {
                "continue": "process_document",
                "error": "handle_error",
            }
        )

        workflow.add_conditional_edges(
            "process_document",
            self._route_after_processing,
            {
                "continue": "calculate_scores",
                "error": "handle_error",
            }
        )

        workflow.add_edge("calculate_scores", "generate_summary")
        workflow.add_edge("generate_summary", END)
        workflow.add_edge("handle_error", END)

        return workflow

    async def _emit_status(self, status: str):
        """Call the status callback if set."""
        if self._status_callback:
            try:
                await self._status_callback(status)
            except Exception as e:
                logger.warning(f"Status callback failed: {e}")

    async def _validate_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Validation node - checks customer in RPS."""
        await self._emit_status("VALIDATING")
        logger.info(f"Orchestrator: Running validation for {state['request_id']}")

        try:
            result = await self.validation_agent.validate(
                customer_id=state["customer_id"],
                old_name=state["old_name"],
                new_name=state["new_name"],
            )

            return {
                "validation_result": {
                    "is_valid": result.is_valid,
                    "customer_exists": result.customer_exists,
                    "name_matches": result.name_matches,
                    "account_active": result.account_active,
                    "errors": result.errors,
                    "warnings": result.warnings,
                },
                "is_valid": result.is_valid,
            }
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                "validation_result": None,
                "is_valid": False,
                "error": f"Validation error: {str(e)}",
            }

    async def _process_document_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Document processing node - OCR and field extraction."""
        await self._emit_status("PROCESSING_DOCUMENTS")
        logger.info(f"Orchestrator: Processing document for {state['request_id']}")

        document_path = state.get("document_path")
        if not document_path:
            # No document - use validation only
            return {
                "extraction_result": {
                    "success": True,
                    "raw_text": "",
                    "extracted_fields": {},
                    "document_type": "NONE",
                    "confidence": 0.0,
                    "processing_time_ms": 0,
                    "warnings": ["No document provided"],
                },
                "extracted_fields": {},
            }

        try:
            result = await self.document_processor.process_document(
                file_path=document_path,
                document_type=state.get("document_type", "MARRIAGE_CERTIFICATE"),
            )

            # Log document processing
            audit_service.log_document_processed(
                request_id=state["request_id"],
                document_id=document_path,
                extracted_fields=result.extracted_fields,
                processing_time_ms=result.processing_time_ms,
            )

            return {
                "extraction_result": {
                    "success": result.success,
                    "raw_text": result.raw_text[:500],  # Truncate for state
                    "extracted_fields": result.extracted_fields,
                    "document_type": result.document_type,
                    "confidence": result.confidence,
                    "processing_time_ms": result.processing_time_ms,
                    "errors": result.errors,
                    "warnings": result.warnings,
                },
                "extracted_fields": result.extracted_fields,
            }
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                "extraction_result": None,
                "extracted_fields": {},
                "error": f"Document processing error: {str(e)}",
            }

    async def _calculate_scores_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Scoring node - calculate confidence scores."""
        await self._emit_status("SCORING")
        logger.info(f"Orchestrator: Calculating scores for {state['request_id']}")

        extraction = state.get("extraction_result", {})
        extracted_fields = state.get("extracted_fields", {})

        try:
            result = await self.confidence_scorer.calculate_scores(
                request_old_name=state["old_name"],
                request_new_name=state["new_name"],
                extracted_fields=extracted_fields,
                extraction_confidence=extraction.get("confidence", 0),
                forgery_indicators=extraction.get("warnings", []),
            )

            return {
                "scoring_result": {
                    "name_match_score": result.name_match_score,
                    "authenticity_score": result.authenticity_score,
                    "forgery_check": result.forgery_check,
                    "overall_score": result.overall_score,
                    "recommendation": result.recommendation,
                    "details": result.details,
                },
                "recommendation": result.recommendation,
            }
        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            return {
                "scoring_result": None,
                "recommendation": "MANUAL_REVIEW",
                "error": f"Scoring error: {str(e)}",
            }

    async def _generate_summary_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Summary node - generate human-readable summary."""
        logger.info(f"Orchestrator: Generating summary for {state['request_id']}")

        try:
            result = await self.summary_generator.generate_summary(
                request_data={
                    "customer_id": state["customer_id"],
                    "old_name": state["old_name"],
                    "new_name": state["new_name"],
                },
                extracted_fields=state.get("extracted_fields", {}),
                scoring_result=state.get("scoring_result", {}),
                validation_result=state.get("validation_result", {}),
            )

            # Determine final status
            recommendation = state.get("recommendation", "MANUAL_REVIEW")
            if recommendation in ["APPROVE", "MANUAL_REVIEW"]:
                status = "AI_VERIFIED_PENDING_HUMAN"
            else:
                status = "AI_FLAGGED_PENDING_HUMAN"

            # Log AI verification
            audit_service.log_ai_verification(
                request_id=state["request_id"],
                recommendation=recommendation,
                confidence_scores=state.get("scoring_result", {}),
                summary=result.summary,
            )

            return {
                "summary_result": {
                    "summary": result.summary,
                    "recommendation_text": result.recommendation_text,
                    "key_findings": result.key_findings,
                    "risks": result.risks,
                    "processing_notes": result.processing_notes,
                },
                "status": status,
            }
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return {
                "summary_result": None,
                "status": "AI_FLAGGED_PENDING_HUMAN",
                "error": f"Summary error: {str(e)}",
            }

    async def _handle_error_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Error handling node."""
        logger.error(f"Orchestrator: Error state for {state['request_id']}: {state.get('error')}")

        return {
            "status": "ERROR",
            "recommendation": "MANUAL_REVIEW",
        }

    def _route_after_validation(self, state: WorkflowState) -> str:
        """Route after validation node."""
        if state.get("error"):
            return "error"
        # Continue even if validation fails - let human review
        return "continue"

    def _route_after_processing(self, state: WorkflowState) -> str:
        """Route after document processing."""
        if state.get("error") and not state.get("extracted_fields"):
            return "error"
        return "continue"

    async def run(
        self,
        request_id: str,
        customer_id: str,
        old_name: str,
        new_name: str,
        document_path: Optional[str] = None,
        document_type: str = "MARRIAGE_CERTIFICATE",
        status_callback=None,
    ) -> Dict[str, Any]:
        """
        Run the complete verification workflow.

        Args:
            request_id: Unique request identifier
            customer_id: Customer ID
            old_name: Current name
            new_name: New requested name
            document_path: Path to uploaded document
            document_type: Type of document

        Returns:
            Complete workflow result
        """
        start_time = time.time()
        self._status_callback = status_callback
        logger.info(f"Orchestrator: Starting workflow for {request_id}")

        # Initial state
        initial_state: WorkflowState = {
            "request_id": request_id,
            "customer_id": customer_id,
            "old_name": old_name,
            "new_name": new_name,
            "document_path": document_path,
            "document_type": document_type,
            "validation_result": None,
            "is_valid": False,
            "extraction_result": None,
            "extracted_fields": None,
            "scoring_result": None,
            "summary_result": None,
            "recommendation": "MANUAL_REVIEW",
            "status": "PROCESSING",
            "error": None,
            "processing_time_ms": 0,
        }

        # Run the workflow
        config = {"configurable": {"thread_id": request_id}}

        try:
            final_state = await self.app.ainvoke(initial_state, config)

            # Calculate total processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            final_state["processing_time_ms"] = processing_time_ms

            logger.info(
                f"Orchestrator: Workflow complete for {request_id}. "
                f"Status: {final_state['status']}, Time: {processing_time_ms}ms"
            )

            return final_state

        except Exception as e:
            logger.error(f"Orchestrator: Workflow failed for {request_id}: {e}")
            return {
                **initial_state,
                "status": "ERROR",
                "error": str(e),
                "processing_time_ms": int((time.time() - start_time) * 1000),
            }


# Factory function for easy use
async def run_workflow(
    request_id: str,
    customer_id: str,
    old_name: str,
    new_name: str,
    document_path: Optional[str] = None,
    document_type: str = "MARRIAGE_CERTIFICATE",
    llm_provider: str = None,
    status_callback=None,
) -> Dict[str, Any]:
    """Convenience wrapper. status_callback(status_str) is awaited at each pipeline stage."""
    orchestrator = WorkflowOrchestrator(llm_provider=llm_provider)
    return await orchestrator.run(
        request_id=request_id,
        customer_id=customer_id,
        old_name=old_name,
        new_name=new_name,
        document_path=document_path,
        document_type=document_type,
        status_callback=status_callback,
    )
