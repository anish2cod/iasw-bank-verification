"""Document Processor Agent - OCR, field extraction, and integrity checks."""

import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from backend.services.llm_service import get_llm_service, LLMService
from backend.config import OCR_PROVIDER, TESSERACT_LANG

logger = logging.getLogger(__name__)

# --- Optional dependency flags ---
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract/Pillow not available")

try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("pdf2image not available")

try:
    from PIL import ImageChops
    ELA_AVAILABLE = True
except ImportError:
    ELA_AVAILABLE = False

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False
    logger.warning("pyzbar not available (libzbar0 missing). QR detection via LLM only.")

# Gemini Vision prompt for full document analysis
_VISION_PROMPT = """You are a document analyst for a bank. Analyze this legal document image and extract information.

Return ONLY a valid JSON object with exactly these fields (use null if not found, true/false for booleans):
{
  "bride_name": "full name of the woman/applicant before marriage",
  "groom_name": "full name of the man/husband",
  "marriage_date": "date of marriage",
  "registration_number": "official certificate/registration number",
  "place_of_marriage": "location where marriage took place",
  "officiating_authority": "registrar/officiant name or title",
  "document_language": "primary language of document (e.g. English, Hindi, Tamil)",
  "document_type": "MARRIAGE_CERTIFICATE, COURT_ORDER, GOVERNMENT_ID, or UNKNOWN",
  "has_official_seal": false,
  "has_signature": false,
  "has_qr_or_barcode": false,
  "document_quality": "good, fair, or poor",
  "tampering_indicators": [],
  "raw_text_excerpt": "first 300 characters of visible text in the document"
}

If this is a handwritten document, still extract all readable fields.
If the document is in a non-English language, translate the field values to English.
Look carefully for official seals, stamps, signatures, QR codes, and barcodes.
Return ONLY the JSON object, no explanation."""


@dataclass
class ExtractionResult:
    success: bool
    raw_text: str
    extracted_fields: Dict[str, Any]
    document_type: str
    confidence: float
    processing_time_ms: int
    ocr_provider: str = "unknown"
    integrity_checks: Dict[str, Any] = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class DocumentProcessorAgent:
    """
    Multi-provider document processor.

    Pipeline:
    1. Load image (handle PDF, TIFF, JPEG, PNG)
    2. OCR + field extraction (Gemini Vision preferred; Tesseract fallback)
    3. Integrity checks: ELA forgery, EXIF metadata, QR/barcode
    4. Return structured ExtractionResult
    """

    def __init__(self, llm_provider: str = None):
        self.llm: LLMService = get_llm_service(llm_provider)
        self.ocr_provider = OCR_PROVIDER

    async def process_document(
        self,
        file_path: str,
        document_type: str = "MARRIAGE_CERTIFICATE",
    ) -> ExtractionResult:
        start = time.time()
        errors: list = []
        warnings: list = []
        path = Path(file_path)

        if not path.exists():
            return ExtractionResult(
                success=False, raw_text="", extracted_fields={},
                document_type=document_type, confidence=0.0,
                processing_time_ms=0, errors=[f"File not found: {file_path}"],
            )

        logger.info(f"DocumentProcessor: Processing {path.name} via {self.ocr_provider}")

        # --- Step 1: Get PIL Image ---
        pil_image = await self._load_as_image(path)

        # --- Step 2: Extract fields ---
        extracted_fields: Dict[str, Any] = {}
        used_provider = "none"

        if self.ocr_provider == "gemini_vision" and self.llm.has_vision() and pil_image:
            extracted_fields, used_provider = await self._extract_gemini_vision(pil_image, document_type)
        else:
            # Tesseract OCR → LLM field extraction
            raw_text = await self._tesseract_ocr(path, pil_image)
            if not raw_text:
                raw_text = self._mock_text(document_type)
                warnings.append("Using mock text - OCR not available or failed")

            if self.llm.is_available():
                extracted_fields = await self._extract_fields_llm(raw_text, document_type)
                used_provider = f"tesseract+{self.llm.get_provider_name()}"
            else:
                extracted_fields = self._extract_fields_regex(raw_text, document_type)
                used_provider = "tesseract+regex"
                warnings.append("LLM not available - using regex extraction")

            extracted_fields["raw_text"] = raw_text[:500]

        # --- Step 3: Integrity checks ---
        integrity = {}
        if pil_image:
            integrity["ela"] = self._run_ela(pil_image)
            integrity["exif"] = self._check_exif(path)
            integrity["qr_barcode"] = self._detect_qr(pil_image)

            # Build forgery warnings from integrity
            if integrity["ela"].get("suspicious"):
                warnings.append("FORGERY_INDICATOR: ELA detected possible image manipulation")
            if integrity["exif"].get("suspicious"):
                for flag in integrity["exif"].get("flags", []):
                    warnings.append(f"FORGERY_INDICATOR: EXIF - {flag}")

        # Gemini Vision already returns tampering_indicators in extracted_fields
        for indicator in extracted_fields.pop("tampering_indicators", []):
            if indicator:
                warnings.append(f"FORGERY_INDICATOR: {indicator}")

        # Add basic forgery checks on extracted text
        warnings.extend(self._check_text_forgery(extracted_fields))

        # --- Step 4: Compute confidence ---
        detected_type = extracted_fields.pop("document_type", None) or document_type
        confidence = self._compute_confidence(extracted_fields, detected_type, integrity)

        ms = int((time.time() - start) * 1000)
        logger.info(f"DocumentProcessor: done in {ms}ms via {used_provider}, conf={confidence:.2f}")

        return ExtractionResult(
            success=True,
            raw_text=extracted_fields.get("raw_text", ""),
            extracted_fields=extracted_fields,
            document_type=detected_type,
            confidence=confidence,
            processing_time_ms=ms,
            ocr_provider=used_provider,
            integrity_checks=integrity,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #
    # Image loading                                                        #
    # ------------------------------------------------------------------ #

    async def _load_as_image(self, path: Path):
        """Convert file to PIL Image. Returns None on failure."""
        try:
            from PIL import Image
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                if not PDF_SUPPORT:
                    return None
                import asyncio
                pages = await asyncio.to_thread(convert_from_path, str(path), first_page=1, last_page=1)
                return pages[0] if pages else None
            elif suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif"}:
                return Image.open(path)
        except Exception as e:
            logger.error(f"Image load failed: {e}")
        return None

    # ------------------------------------------------------------------ #
    # Gemini Vision OCR (primary - handles handwriting + multilingual)     #
    # ------------------------------------------------------------------ #

    async def _extract_gemini_vision(self, image, document_type: str):
        """Send image to Gemini Vision for full extraction + integrity in one call."""
        try:
            raw = await self.llm.async_generate_vision(_VISION_PROMPT, image)
            if not raw:
                raise ValueError("Empty vision response")

            fields = self._parse_json_response(raw)

            # Promote raw_text_excerpt to raw_text key
            fields["raw_text"] = fields.pop("raw_text_excerpt", "")

            logger.info(f"Gemini Vision extracted: {list(k for k, v in fields.items() if v and k != 'raw_text')}")
            return fields, "gemini_vision"

        except Exception as e:
            logger.error(f"Gemini Vision extraction failed: {e}")
            # Fall back to text LLM
            warnings_temp = []
            raw_text = await self._tesseract_ocr_fallback()
            if self.llm.is_available():
                fields = await self._extract_fields_llm(raw_text, document_type)
                return fields, f"vision_fallback+{self.llm.get_provider_name()}"
            return {"raw_text": raw_text}, "vision_fallback+regex"

    async def _tesseract_ocr_fallback(self) -> str:
        return ""

    # ------------------------------------------------------------------ #
    # Tesseract OCR (typed text, multi-lang via lang config)              #
    # ------------------------------------------------------------------ #

    async def _tesseract_ocr(self, path: Path, pil_image=None) -> str:
        if not OCR_AVAILABLE:
            return ""
        try:
            import asyncio
            img = pil_image or Image.open(path)
            text = await asyncio.to_thread(
                pytesseract.image_to_string, img, lang=TESSERACT_LANG
            )
            return text.strip()
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return ""

    # ------------------------------------------------------------------ #
    # LLM text-based field extraction                                     #
    # ------------------------------------------------------------------ #

    async def _extract_fields_llm(self, text: str, document_type: str) -> Dict[str, Any]:
        prompt = f"""Extract information from this marriage certificate or legal document text.
Return ONLY valid JSON with these fields (null if not found):
{{
  "bride_name": null,
  "groom_name": null,
  "marriage_date": null,
  "registration_number": null,
  "place_of_marriage": null,
  "officiating_authority": null,
  "document_language": "English",
  "has_official_seal": false,
  "has_signature": false,
  "has_qr_or_barcode": false,
  "document_quality": "fair",
  "tampering_indicators": []
}}

Document text:
{text[:3000]}

Return ONLY the JSON object."""

        try:
            response = await self.llm.async_generate(prompt, temperature=0.0)
            if response:
                return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"LLM field extraction failed: {e}")

        return self._extract_fields_regex(text, document_type)

    def _extract_fields_regex(self, text: str, document_type: str) -> Dict[str, Any]:
        """Regex fallback for field extraction."""
        fields: Dict[str, Any] = {}

        if document_type == "MARRIAGE_CERTIFICATE":
            patterns = {
                "bride_name": [
                    r"(?:bride|wife|name of bride)[\s:]+([A-Za-z\s\.]+?)(?:\n|,|$)",
                ],
                "groom_name": [
                    r"(?:groom|husband|name of groom)[\s:]+([A-Za-z\s\.]+?)(?:\n|,|$)",
                ],
                "marriage_date": [
                    r"(?:date of marriage|married on|marriage date)[\s:]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
                    r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})",
                ],
                "registration_number": [
                    r"(?:registration|certificate)\s*(?:no|number)?[\s.:]+([A-Z0-9/\-]+)",
                ],
            }
            for field_name, pats in patterns.items():
                for pat in pats:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        fields[field_name] = m.group(1).strip()
                        break

        return fields

    # ------------------------------------------------------------------ #
    # Integrity checks                                                     #
    # ------------------------------------------------------------------ #

    def _run_ela(self, image) -> Dict[str, Any]:
        """Error Level Analysis - detects JPEG editing by comparing compression artifacts."""
        if not ELA_AVAILABLE:
            return {"available": False}
        try:
            img_rgb = image.convert("RGB")
            # Thumbnail for speed
            img_rgb.thumbnail((800, 800))

            buf = io.BytesIO()
            img_rgb.save(buf, "JPEG", quality=90)
            buf.seek(0)
            from PIL import Image as PILImage
            compressed = PILImage.open(buf).convert("RGB")

            diff = ImageChops.difference(img_rgb, compressed)
            pixels = list(diff.getdata())

            # Sample up to 20k pixels for speed
            step = max(1, len(pixels) // 20000)
            sample = pixels[::step]

            values = []
            for px in sample:
                if isinstance(px, tuple):
                    values.extend(px)
                else:
                    values.append(px)

            if not values:
                return {"suspicious": False}

            mean_err = sum(values) / len(values)
            max_err = max(values)
            suspicious = mean_err > 12 or max_err > 90

            return {
                "mean_error": round(mean_err, 2),
                "max_error": int(max_err),
                "suspicious": suspicious,
            }
        except Exception as e:
            logger.debug(f"ELA error: {e}")
            return {"suspicious": False, "error": str(e)}

    def _check_exif(self, path: Path) -> Dict[str, Any]:
        """EXIF metadata analysis for editing software traces."""
        if not OCR_AVAILABLE:
            return {"available": False}
        suspicious_software = {"photoshop", "gimp", "pixelmator", "lightroom", "illustrator", "canva", "paint.net"}
        try:
            from PIL import Image
            img = Image.open(path)
            exif_raw = getattr(img, "_getexif", lambda: None)()
            if not exif_raw:
                return {"has_exif": False, "suspicious": False}

            SOFTWARE_TAG, DATETIME_TAG, DATETIME_ORIG_TAG = 305, 306, 36867
            flags = []
            software = str(exif_raw.get(SOFTWARE_TAG, "")).lower()
            if any(sw in software for sw in suspicious_software):
                flags.append(f"Edited with image software: {exif_raw.get(SOFTWARE_TAG)}")

            dt_mod = exif_raw.get(DATETIME_TAG)
            dt_orig = exif_raw.get(DATETIME_ORIG_TAG)
            if dt_mod and dt_orig and dt_mod != dt_orig:
                flags.append("File modification date differs from original capture date")

            return {
                "has_exif": True,
                "suspicious": bool(flags),
                "software": exif_raw.get(SOFTWARE_TAG, ""),
                "flags": flags,
            }
        except Exception as e:
            return {"has_exif": False, "suspicious": False}

    def _detect_qr(self, image) -> Dict[str, Any]:
        """Detect QR codes / barcodes using pyzbar (if libzbar0 is present)."""
        if not PYZBAR_AVAILABLE:
            return {"found": False, "note": "pyzbar unavailable - use Gemini Vision for QR detection"}
        try:
            codes = pyzbar_decode(image)
            if codes:
                decoded = [{"type": c.type, "data": c.data.decode("utf-8", errors="ignore")} for c in codes]
                return {"found": True, "count": len(decoded), "codes": decoded}
            return {"found": False, "count": 0}
        except Exception as e:
            return {"found": False, "error": str(e)}

    def _check_text_forgery(self, fields: Dict[str, Any]) -> list:
        """Heuristic text-based forgery checks."""
        indicators = []
        raw = fields.get("raw_text", "")

        if raw and len(raw) < 30:
            indicators.append("FORGERY_INDICATOR: Extremely short document text")

        unusual = sum(1 for c in raw if ord(c) > 127 and not c.isalpha())
        if raw and unusual > len(raw) * 0.15:
            indicators.append("FORGERY_INDICATOR: High ratio of unusual characters")

        return indicators

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract JSON object from LLM response text."""
        # Strip markdown code blocks if present
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        text = text.rstrip("```").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object within the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse JSON from LLM response")
        return {}

    def _compute_confidence(
        self, fields: Dict[str, Any], document_type: str, integrity: Dict[str, Any]
    ) -> float:
        score = 0.0

        # Key field presence
        key_fields = ["bride_name", "groom_name", "marriage_date"]
        found = sum(1 for f in key_fields if fields.get(f))
        score += (found / len(key_fields)) * 0.5

        # Registration number bonus
        if fields.get("registration_number"):
            score += 0.1

        # Integrity bonuses
        if fields.get("has_official_seal"):
            score += 0.1
        if fields.get("has_signature"):
            score += 0.05
        if fields.get("has_qr_or_barcode") or integrity.get("qr_barcode", {}).get("found"):
            score += 0.1

        # Quality bonus
        quality = fields.get("document_quality", "fair")
        if quality == "good":
            score += 0.05

        # Integrity penalties
        if integrity.get("ela", {}).get("suspicious"):
            score -= 0.15
        if integrity.get("exif", {}).get("suspicious"):
            score -= 0.1

        return round(min(max(score, 0.0), 1.0), 3)

    def _mock_text(self, document_type: str) -> str:
        if document_type == "MARRIAGE_CERTIFICATE":
            return (
                "CERTIFICATE OF MARRIAGE\n"
                "Registration Number: MC-2024-001234\n"
                "Bride: Priya Sharma\nGroom: Rahul Mehta\n"
                "Date of Marriage: 15th January 2024\n"
                "Place: Mumbai, Maharashtra\n"
                "Registrar of Marriages, Mumbai District"
            )
        return "Document text not available"
