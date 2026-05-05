"""Summary Generator Agent - Creates human-readable verification summaries."""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from backend.services.llm_service import get_llm_service, LLMService

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    """Result of summary generation."""
    summary: str
    recommendation_text: str
    key_findings: list
    risks: list
    processing_notes: list


class SummaryGeneratorAgent:
    """
    Agent responsible for generating human-readable summaries.

    Produces:
    - Executive summary
    - Key findings
    - Identified risks
    - Recommendation with rationale
    """

    def __init__(self, llm_provider: str = None):
        self.llm_service: LLMService = get_llm_service(llm_provider)
        self.llm_available = True  # Always attempt; async_generate handles unavailability

    async def generate_summary(
        self,
        request_data: Dict[str, Any],
        extracted_fields: Dict[str, Any],
        scoring_result: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> SummaryResult:
        """
        Generate a comprehensive verification summary.

        Args:
            request_data: Original request information
            extracted_fields: Fields extracted from document
            scoring_result: Confidence scores
            validation_result: RPS validation results

        Returns:
            SummaryResult with formatted summary
        """
        logger.info("SummaryGenerator: Generating verification summary")

        # Collect key findings
        key_findings = self._collect_key_findings(
            request_data, extracted_fields, scoring_result, validation_result
        )

        # Identify risks
        risks = self._identify_risks(
            scoring_result, validation_result
        )

        # Generate recommendation text
        recommendation_text = self._format_recommendation(
            scoring_result.get("recommendation", "MANUAL_REVIEW"),
            scoring_result
        )

        # Generate summary
        if self.llm_available:
            summary = await self._generate_llm_summary(
                request_data, extracted_fields, scoring_result,
                validation_result, key_findings, risks
            )
        else:
            summary = self._generate_template_summary(
                request_data, extracted_fields, scoring_result,
                validation_result, key_findings, risks
            )

        # Processing notes
        processing_notes = []
        if not self.llm_available:
            processing_notes.append("Summary generated using template (LLM unavailable)")
        else:
            processing_notes.append(f"Summary generated using {self.llm_service.get_provider_name()}")

        return SummaryResult(
            summary=summary,
            recommendation_text=recommendation_text,
            key_findings=key_findings,
            risks=risks,
            processing_notes=processing_notes
        )

    def _collect_key_findings(
        self,
        request_data: Dict[str, Any],
        extracted_fields: Dict[str, Any],
        scoring_result: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> list:
        """Collect key findings from verification."""
        findings = []

        # Customer validation
        if validation_result.get("customer_exists"):
            findings.append(
                f"✓ Customer {request_data.get('customer_id')} verified in RPS"
            )
        else:
            findings.append(
                f"✗ Customer {request_data.get('customer_id')} NOT FOUND in RPS"
            )

        # Name match
        if validation_result.get("name_matches"):
            findings.append("✓ Current name matches RPS records")
        else:
            findings.append("✗ Name mismatch with RPS records")

        # Document extraction
        if extracted_fields.get("bride_name"):
            findings.append(
                f"✓ Document shows bride name: {extracted_fields['bride_name']}"
            )
        if extracted_fields.get("married_name"):
            findings.append(
                f"✓ Document shows married name: {extracted_fields['married_name']}"
            )
        if extracted_fields.get("marriage_date"):
            findings.append(
                f"✓ Marriage date: {extracted_fields['marriage_date']}"
            )

        # Confidence scores
        name_match = scoring_result.get("name_match_score", 0)
        if name_match >= 0.9:
            findings.append(f"✓ High name match confidence: {name_match:.0%}")
        elif name_match >= 0.7:
            findings.append(f"~ Moderate name match confidence: {name_match:.0%}")
        else:
            findings.append(f"✗ Low name match confidence: {name_match:.0%}")

        # Forgery check
        forgery = scoring_result.get("forgery_check", "UNKNOWN")
        if forgery == "PASS":
            findings.append("✓ No forgery indicators detected")
        elif forgery == "UNCERTAIN":
            findings.append("~ Some document anomalies detected")
        else:
            findings.append("✗ Potential forgery indicators found")

        return findings

    def _identify_risks(
        self,
        scoring_result: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> list:
        """Identify risks and warnings."""
        risks = []

        # From validation
        for warning in validation_result.get("warnings", []):
            risks.append(f"⚠ {warning}")
        for error in validation_result.get("errors", []):
            risks.append(f"⛔ {error}")

        # From scoring
        if scoring_result.get("name_match_score", 0) < 0.7:
            risks.append("⚠ Low name match - verify manually")

        if scoring_result.get("authenticity_score", 0) < 0.5:
            risks.append("⚠ Low document authenticity score")

        if scoring_result.get("forgery_check") == "UNCERTAIN":
            risks.append("⚠ Document requires additional verification")

        # Scoring details
        details = scoring_result.get("details", {})
        if details.get("forgery_indicators_count", 0) > 0:
            count = details["forgery_indicators_count"]
            risks.append(f"⚠ {count} forgery indicator(s) flagged")

        return risks

    def _format_recommendation(
        self,
        recommendation: str,
        scoring_result: Dict[str, Any]
    ) -> str:
        """Format recommendation with rationale."""
        overall = scoring_result.get("overall_score", 0)

        if recommendation == "APPROVE":
            return (
                f"RECOMMENDATION: APPROVE\n"
                f"Overall confidence score: {overall:.0%}\n"
                f"All verification checks passed. Document appears authentic "
                f"and names match the request."
            )
        elif recommendation == "REJECT":
            forgery = scoring_result.get("forgery_check")
            if forgery == "FAIL":
                return (
                    f"RECOMMENDATION: REJECT\n"
                    f"Overall confidence score: {overall:.0%}\n"
                    f"Document failed forgery checks. Manual verification of "
                    f"original documents required."
                )
            else:
                return (
                    f"RECOMMENDATION: REJECT\n"
                    f"Overall confidence score: {overall:.0%}\n"
                    f"Verification confidence below acceptable threshold. "
                    f"Request new documentation or escalate."
                )
        else:
            return (
                f"RECOMMENDATION: MANUAL REVIEW REQUIRED\n"
                f"Overall confidence score: {overall:.0%}\n"
                f"Some verification checks need human verification. "
                f"Please review the findings and risks carefully."
            )

    async def _generate_llm_summary(
        self,
        request_data: Dict[str, Any],
        extracted_fields: Dict[str, Any],
        scoring_result: Dict[str, Any],
        validation_result: Dict[str, Any],
        key_findings: list,
        risks: list
    ) -> str:
        """Generate summary using LLM (Ollama or Gemini)."""
        try:
            prompt = f"""Generate a concise verification summary for a bank name change request.

REQUEST:
- Customer ID: {request_data.get('customer_id')}
- Old Name: {request_data.get('old_name')}
- New Name: {request_data.get('new_name')}

DOCUMENT EXTRACTION:
- Bride Name: {extracted_fields.get('bride_name', 'Not found')}
- Married Name: {extracted_fields.get('married_name', 'Not found')}
- Marriage Date: {extracted_fields.get('marriage_date', 'Not found')}

CONFIDENCE SCORES:
- Name Match: {scoring_result.get('name_match_score', 0):.0%}
- Authenticity: {scoring_result.get('authenticity_score', 0):.0%}
- Forgery Check: {scoring_result.get('forgery_check', 'UNKNOWN')}
- Overall: {scoring_result.get('overall_score', 0):.0%}

RECOMMENDATION: {scoring_result.get('recommendation', 'MANUAL_REVIEW')}

Write a 2-3 sentence professional summary for a bank checker to review. Be factual and concise."""

            response = await self.llm_service.async_generate(prompt, temperature=0.3)

            if response:
                return response.strip()
            else:
                logger.warning("LLM returned empty response, using template")
                return self._generate_template_summary(
                    request_data, extracted_fields, scoring_result,
                    validation_result, key_findings, risks
                )

        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return self._generate_template_summary(
                request_data, extracted_fields, scoring_result,
                validation_result, key_findings, risks
            )

    def _generate_template_summary(
        self,
        request_data: Dict[str, Any],
        extracted_fields: Dict[str, Any],
        scoring_result: Dict[str, Any],
        validation_result: Dict[str, Any],
        key_findings: list,
        risks: list
    ) -> str:
        """Generate template-based summary (fallback)."""
        customer_id = request_data.get("customer_id", "Unknown")
        old_name = request_data.get("old_name", "Unknown")
        new_name = request_data.get("new_name", "Unknown")

        recommendation = scoring_result.get("recommendation", "MANUAL_REVIEW")
        overall = scoring_result.get("overall_score", 0)
        name_match = scoring_result.get("name_match_score", 0)
        forgery = scoring_result.get("forgery_check", "UNKNOWN")

        # Build summary
        summary_parts = []

        # Opening
        summary_parts.append(
            f"Name change request for customer {customer_id}: "
            f"'{old_name}' to '{new_name}'."
        )

        # Document findings
        bride_name = extracted_fields.get("bride_name")
        married_name = extracted_fields.get("married_name")

        if bride_name and married_name:
            summary_parts.append(
                f"Marriage certificate shows bride '{bride_name}' "
                f"with married name '{married_name}'."
            )
        elif bride_name:
            summary_parts.append(
                f"Marriage certificate shows bride name '{bride_name}'."
            )

        # Scores summary
        if recommendation == "APPROVE":
            summary_parts.append(
                f"Verification passed with {overall:.0%} confidence. "
                f"Name match: {name_match:.0%}. Forgery check: {forgery}."
            )
        elif recommendation == "REJECT":
            summary_parts.append(
                f"Verification FAILED with {overall:.0%} confidence. "
                f"Name match: {name_match:.0%}. Forgery check: {forgery}."
            )
        else:
            summary_parts.append(
                f"Verification requires manual review. Confidence: {overall:.0%}. "
                f"Name match: {name_match:.0%}. Forgery check: {forgery}."
            )

        # Add risk count if any
        if risks:
            summary_parts.append(f"({len(risks)} risk item(s) flagged)")

        return " ".join(summary_parts)
