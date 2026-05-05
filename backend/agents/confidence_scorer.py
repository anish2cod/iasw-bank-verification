"""Confidence Scorer Agent - Calculates verification confidence scores."""

import logging
import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from backend.services.llm_service import get_llm_service, LLMService

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

try:
    import Levenshtein
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False


@dataclass
class ScoringResult:
    name_match_score: float
    authenticity_score: float
    forgery_check: str        # PASS / UNCERTAIN / FAIL
    overall_score: float
    recommendation: str       # APPROVE / MANUAL_REVIEW / REJECT
    details: Dict[str, Any] = field(default_factory=dict)


class ConfidenceScorerAgent:
    """
    Confidence scoring with LLM-assisted name relationship analysis.

    Key insight: marriage certificates do NOT contain the bride's new married
    name. Instead we derive it from:
      - Old name match: does extracted bride_name match the request's old_name?
      - Name relationship: is the requested new_name plausible given the
        bride's old name + groom's name?  (first-name preserved + surname
        inherited from groom, or other common patterns)
    """

    def __init__(self, llm_provider: str = None):
        self.llm: LLMService = get_llm_service(llm_provider)
        self.thresholds = {
            "auto_approve": 0.90,
            "manual_review": 0.70,
            "auto_reject": 0.40,
        }

    async def calculate_scores(
        self,
        request_old_name: str,
        request_new_name: str,
        extracted_fields: Dict[str, Any],
        extraction_confidence: float,
        forgery_indicators: list = None,
    ) -> ScoringResult:

        logger.info("ConfidenceScorer: calculating scores")

        name_score, name_details = await self._score_name(
            request_old_name, request_new_name, extracted_fields
        )

        auth_score = self._score_authenticity(extracted_fields, extraction_confidence)
        forgery_check, forgery_score = self._check_forgery(forgery_indicators or [])
        overall = self._overall(name_score, auth_score, forgery_score)
        recommendation = self._recommendation(overall, forgery_check)

        logger.info(
            f"ConfidenceScorer: name={name_score:.2f} auth={auth_score:.2f} "
            f"forgery={forgery_check} overall={overall:.2f} → {recommendation}"
        )

        return ScoringResult(
            name_match_score=round(name_score, 3),
            authenticity_score=round(auth_score, 3),
            forgery_check=forgery_check,
            overall_score=round(overall, 3),
            recommendation=recommendation,
            details={
                "name_details": name_details,
                "extraction_confidence": extraction_confidence,
                "forgery_indicator_count": len(forgery_indicators or []),
                "thresholds": self.thresholds,
            },
        )

    # ------------------------------------------------------------------ #
    # Name scoring                                                         #
    # ------------------------------------------------------------------ #

    async def _score_name(
        self,
        old_name: str,
        new_name: str,
        fields: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Two-component score:
          A) Identity verification  – does extracted bride_name match old_name?
          B) Name-change plausibility – is new_name consistent with
             old_name + groom_name (structural) and confirmed by LLM?
        """
        details: Dict[str, Any] = {
            "request_old_name": old_name,
            "request_new_name": new_name,
        }

        extracted_bride = (fields.get("bride_name") or "").strip()
        extracted_groom = (fields.get("groom_name") or "").strip()

        details["extracted_bride"] = extracted_bride
        details["extracted_groom"] = extracted_groom

        scores = []

        # --- A) Identity: old_name ↔ extracted_bride_name ---
        if extracted_bride:
            identity_score = self._fuzzy(old_name, extracted_bride)
            details["identity_score"] = identity_score
            scores.append(("identity", identity_score, 0.5))
        else:
            details["identity_score"] = None
            details["note_identity"] = "bride_name not found in document"

        # --- B) New name plausibility ---
        if extracted_groom:
            # Heuristic: structural name analysis
            heuristic = self._heuristic_name_relationship(old_name, new_name, extracted_groom)
            details["heuristic_relationship"] = heuristic

            # LLM semantic judgment (returns None on failure)
            llm_score = None
            if self.llm.is_available():
                llm_score = await self._llm_name_relationship(old_name, new_name, extracted_groom)
            details["llm_relationship"] = llm_score

            # If LLM unavailable/failed, use only heuristic at full weight
            if llm_score is not None:
                relationship = heuristic * 0.5 + llm_score * 0.5
            else:
                relationship = heuristic

            details["combined_relationship"] = relationship
            scores.append(("relationship", relationship, 0.5))
        else:
            # No groom name extracted — only heuristic based on name tokens
            fallback = self._token_overlap_score(old_name, new_name)
            details["fallback_token_overlap"] = fallback
            details["note_relationship"] = "groom_name not found; using token overlap"
            scores.append(("fallback", fallback * 0.7, 0.5))

        if not scores:
            return 0.5, {**details, "note": "No comparable fields found"}

        # Weighted average (all weights currently equal; adjust above if needed)
        total_weight = sum(w for _, _, w in scores)
        final = sum(s * w for _, s, w in scores) / total_weight
        return final, details

    def _heuristic_name_relationship(
        self, old_name: str, new_name: str, groom_name: str
    ) -> float:
        """
        Structural name-change plausibility check.

        Rules (typical South-Asian marriage naming patterns):
        - First name should be preserved (Priya Sharma → Priya Mehta  ✓)
        - New surname should appear somewhere in groom's name tokens
        - Handles: adopting surname, adopting first+surname, hyphenation

        Returns 0.0–1.0.
        """
        old_parts = [t for t in old_name.lower().split() if t]
        new_parts = [t for t in new_name.lower().split() if t]
        groom_parts = [t for t in groom_name.lower().split() if t]

        if not old_parts or not new_parts or not groom_parts:
            return 0.3  # Neutral if nothing to compare

        score = 0.0

        # Check 1: First name preserved (weight 0.4)
        first_sim = self._fuzzy(old_parts[0], new_parts[0])
        score += first_sim * 0.4

        # Check 2: New last name appears in groom's tokens (weight 0.5)
        new_last = new_parts[-1]
        best_groom_match = max(self._fuzzy(new_last, g) for g in groom_parts)
        score += best_groom_match * 0.5

        # Check 3: New name length is reasonable (not wildly different) (weight 0.1)
        length_ratio = min(len(new_parts), len(old_parts)) / max(len(new_parts), len(old_parts))
        score += length_ratio * 0.1

        return round(min(score, 1.0), 3)

    async def _llm_name_relationship(
        self, old_name: str, new_name: str, groom_name: str
    ) -> Optional[float]:
        """
        Ask the LLM to assess whether new_name is a plausible married name
        given old_name and groom_name.  Returns 0.0–1.0.
        """
        prompt = f"""You are verifying a marriage name change for a bank.

Bride's pre-marriage name: "{old_name}"
Groom's name: "{groom_name}"
Requested new name: "{new_name}"

Common legal name change patterns after marriage:
1. Bride takes husband's surname → "Priya Sharma" + "Rahul Mehta" = "Priya Mehta" (very common)
2. Bride takes husband's first name as surname → "Priya Sharma" + "Rahul Mehta" = "Priya Rahul"
3. Hyphenated surname → "Priya Sharma-Mehta"
4. Regional variations (e.g., Tamil, Telugu, Bengali naming customs)
5. Complete adoption of husband's family name

Question: Is "{new_name}" a plausible and legitimate married name for someone named "{old_name}" who married "{groom_name}"?

Rate from 0.0 (clearly invalid) to 1.0 (clearly valid):
- 0.9–1.0 = Strong match (e.g., shares husband's surname)
- 0.7–0.8 = Plausible (e.g., takes husband's first name as surname)
- 0.4–0.6 = Uncertain (e.g., partial overlap, regional custom)
- 0.0–0.3 = Unlikely match

Return ONLY a decimal number like 0.85"""

        try:
            response = await self.llm.async_generate(prompt, temperature=0.0)
            if response:
                nums = re.findall(r"(?:0?\.\d+|1\.0|1|0)", response.strip())
                if nums:
                    return min(float(nums[0]), 1.0)
        except Exception as e:
            logger.error(f"LLM name relationship failed: {e}")
        return None  # None signals failure; caller falls back to heuristic-only

    def _token_overlap_score(self, old_name: str, new_name: str) -> float:
        """Fallback: token Jaccard similarity between old and new names."""
        old_t = set(old_name.lower().split())
        new_t = set(new_name.lower().split())
        if not old_t or not new_t:
            return 0.0
        return len(old_t & new_t) / len(old_t | new_t)

    # ------------------------------------------------------------------ #
    # Authenticity scoring                                                 #
    # ------------------------------------------------------------------ #

    def _score_authenticity(
        self, fields: Dict[str, Any], extraction_confidence: float
    ) -> float:
        score = extraction_confidence * 0.3  # Base from extraction quality

        # Expected fields
        key_fields = ["bride_name", "groom_name", "marriage_date"]
        found = sum(1 for f in key_fields if fields.get(f))
        score += (found / len(key_fields)) * 0.3

        # Integrity bonuses
        if fields.get("registration_number"):
            score += 0.1
        if fields.get("has_official_seal"):
            score += 0.12
        if fields.get("has_signature"):
            score += 0.06
        if fields.get("has_qr_or_barcode"):
            score += 0.12

        # Quality
        quality = fields.get("document_quality", "fair")
        if quality == "good":
            score += 0.05

        return round(min(score, 1.0), 3)

    # ------------------------------------------------------------------ #
    # Forgery check                                                        #
    # ------------------------------------------------------------------ #

    def _check_forgery(self, indicators: list) -> Tuple[str, float]:
        serious = sum(1 for i in indicators if "FORGERY_INDICATOR" in str(i))
        minor = len(indicators) - serious

        if serious >= 2:
            return "FAIL", 0.1
        if serious == 1:
            return "UNCERTAIN", 0.4
        if minor >= 3:
            return "UNCERTAIN", 0.6
        return "PASS", 1.0

    # ------------------------------------------------------------------ #
    # Overall score + recommendation                                       #
    # ------------------------------------------------------------------ #

    def _overall(self, name: float, auth: float, forgery: float) -> float:
        return round(name * 0.5 + auth * 0.3 + forgery * 0.2, 3)

    def _recommendation(self, overall: float, forgery: str) -> str:
        if forgery == "FAIL":
            return "REJECT"
        if overall >= self.thresholds["auto_approve"]:
            return "APPROVE"
        if overall >= self.thresholds["manual_review"]:
            return "MANUAL_REVIEW"
        return "REJECT"

    # ------------------------------------------------------------------ #
    # Fuzzy string matching                                                #
    # ------------------------------------------------------------------ #

    def _fuzzy(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        a, b = a.lower().strip(), b.lower().strip()
        if a == b:
            return 1.0
        if RAPIDFUZZ_AVAILABLE:
            return fuzz.token_sort_ratio(a, b) / 100.0
        if LEVENSHTEIN_AVAILABLE:
            return Levenshtein.ratio(a, b)
        # Basic fallback
        s1, s2 = set(a.split()), set(b.split())
        if not s1 or not s2:
            return 0.0
        return 2 * len(s1 & s2) / (len(s1) + len(s2))
