from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from app.schemas.analysis import AdvancedAnalysisPackage, AnalysisRequest, SanitizedSource


class AnalysisSanitizationError(ValueError):
    pass


@dataclass(frozen=True)
class SanitizedPackage:
    package: AdvancedAnalysisPackage
    canonical_json: str
    sha256: str


class AnalysisSanitizer:
    MAX_BYTES = 64 * 1024
    FORBIDDEN_KEYS = re.compile(r"(?i)(name|client|customer|company|address|location|phone|email|crm|database|jwt|cookie|token|secret|password|path|note)")
    EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
    PHONE = re.compile(r"(?<!\w)(?:\+?\d[\s().-]*){7,15}(?!\w)")
    ADDRESS = re.compile(r"(?i)\b(?:ul\.?|ulica|al\.?|aleja|os\.?|plac)\s+[\wąćęłńóśźż.-]+(?:\s+[\wąćęłńóśźż.-]+){0,3}\s+\d+[a-z]?\b")
    SECRET = re.compile(r"(?i)\b(?:bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}|eyJ[a-z0-9_-]{12,}|(?:password|api_?key|access_?token|client_?secret)\s*[:=])")
    WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:\\[^\r\n]+")
    UNIX_PATH = re.compile(r"(?<!\w)/(?:home|var|srv|opt|data|mnt|run|tmp)/[^\s,;]+")
    PRIVATE_URL = re.compile(r"(?i)\bhttps?://(?:localhost|127\.0\.0\.1|10\.\d{1,3}(?:\.\d{1,3}){2}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|[^\s/]+\.internal)(?:[^\s]*)")
    LABELED_IDENTITY = re.compile(r"(?i)\b(?:klient|customer|imi[eę]|nazwisko|firma|company)\s*[:=]\s*[^,;\n]{2,100}")
    INTERNAL_ID = re.compile(r"(?i)\b(?:client|customer|crm|database|document|work_item)_?id\s*[:=#]?\s*[a-z0-9-]+")
    COORDINATES = re.compile(r"(?<!\d)-?\d{1,3}\.\d{4,}\s*[,;/]\s*-?\d{1,3}\.\d{4,}(?!\d)")
    PERSON_NAME = re.compile(
        r"\b(?!(?:Moduł|Norma|Wzór|Tabela|Ciśnienie|Temperatura)\b)"
        r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}\b"
    )
    COMPANY = re.compile(r"(?i)\b[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż&.-]*(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż&.-]*){0,4}\s+(?:sp\.?\s*z\.?\s*o\.?o\.?|s\.?a\.?|ltd\.?|llc|gmbh)\b")
    FREEFORM_NOTE = re.compile(r"(?i)\b(?:notatka\s+klienta|customer\s+note|uwagi\s+klienta)\s*[:=]\s*[^\n]{2,500}")

    def sanitize(self, request: AnalysisRequest) -> SanitizedPackage:
        if request.sensitivity == "restricted_never_external":
            raise AnalysisSanitizationError("analysis_restricted_externalization")
        self._validate_keys(request.structured_inputs)
        sources = []
        for source in request.source_refs:
            text = self._clean(source.excerpt, request.sensitivity)
            sources.append(SanitizedSource(source_ref=source.source_ref, source_sha256=source.checksum_sha256,
                                           technical_excerpt=text, page=source.page))
        problem = self._clean(request.problem_statement, request.sensitivity)
        inputs = self._sanitize_inputs(request.structured_inputs, request.sensitivity)
        package = AdvancedAnalysisPackage(
            analysis_id=request.analysis_id, analysis_type=request.analysis_type,
            problem=problem, sources=sources,
            tables=inputs.get("tables", []), formulas=[self._clean(value, request.sensitivity) for value in request.formulas],
            variables=inputs.get("variables", {}), values=inputs.get("values", {}),
            units={self._clean(str(key), request.sensitivity): self._clean(value, request.sensitivity)
                   for key, value in request.units.items()},
            constraints=[self._clean(value, request.sensitivity) for value in request.constraints],
            standards=inputs.get("standards", []), claims=inputs.get("claims", []),
            requested_output=self._clean(str(inputs.get("requested_output") or "Zwróć zweryfikowany wynik techniczny."), request.sensitivity),
            validation_requirements=[self._clean(str(value), request.sensitivity)
                                     for value in list(inputs.get("validation_requirements") or [])],
        )
        canonical = json.dumps(package.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(canonical.encode("utf-8")) > self.MAX_BYTES:
            raise AnalysisSanitizationError("analysis_package_too_large")
        self._assert_clean(canonical)
        return SanitizedPackage(package, canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest())

    def _validate_keys(self, value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if self.FORBIDDEN_KEYS.search(str(key)):
                    raise AnalysisSanitizationError("analysis_sanitization_unknown_sensitive_field")
                self._validate_keys(nested)
        elif isinstance(value, list):
            for nested in value: self._validate_keys(nested)

    def _sanitize_inputs(self, value: dict, sensitivity: str) -> dict:
        allowed = {"tables", "variables", "values", "standards", "claims",
                   "requested_output", "validation_requirements"}
        return {key: self._sanitize_value(nested, sensitivity) for key, nested in value.items() if key in allowed}

    def _sanitize_value(self, value: object, sensitivity: str) -> object:
        if isinstance(value, str):
            return self._clean(value, sensitivity)
        if isinstance(value, list):
            return [self._sanitize_value(item, sensitivity) for item in value]
        if isinstance(value, dict):
            sanitized = {}
            for key, item in value.items():
                clean_key = self._clean(str(key), sensitivity)
                if clean_key in sanitized:
                    raise AnalysisSanitizationError("analysis_sanitization_key_collision")
                sanitized[clean_key] = self._sanitize_value(item, sensitivity)
            return sanitized
        return value

    def _clean(self, value: str, sensitivity: str) -> str:
        text = " ".join(value.split())
        text = self.EMAIL.sub("[USUNIĘTO_EMAIL]", text)
        text = self.PHONE.sub("[USUNIĘTO_TELEFON]", text)
        text = self.ADDRESS.sub("[USUNIĘTO_ADRES]", text)
        text = self.WINDOWS_PATH.sub("[USUNIĘTO_SCIEZKE]", text)
        text = self.UNIX_PATH.sub("[USUNIĘTO_SCIEZKE]", text)
        text = self.PRIVATE_URL.sub("[USUNIĘTO_PRYWATNY_URL]", text)
        text = self.LABELED_IDENTITY.sub("[USUNIĘTO_TOZSAMOSC]", text)
        text = self.INTERNAL_ID.sub("[USUNIĘTO_ID]", text)
        text = self.COORDINATES.sub("[USUNIĘTO_LOKALIZACJE]", text)
        text = self.FREEFORM_NOTE.sub("[USUNIĘTO_NOTATKE]", text)
        text = self.PERSON_NAME.sub("[USUNIĘTO_OSOBE]", text)
        text = self.COMPANY.sub("[USUNIĘTO_FIRME]", text)
        if self.SECRET.search(text):
            raise AnalysisSanitizationError("analysis_sanitization_secret_detected")
        self._assert_clean(text)
        return text

    def _assert_clean(self, value: str) -> None:
        if (self.EMAIL.search(value) or self.ADDRESS.search(value) or self.SECRET.search(value)
                or self.WINDOWS_PATH.search(value) or self.UNIX_PATH.search(value)
                or self.PRIVATE_URL.search(value)):
            raise AnalysisSanitizationError("analysis_sanitization_failed")
