# core/transformer.py
import logging
from .config import Settings
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

audit_logger = logging.getLogger("audit")

try:
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    PII_ENGINE_ENABLED = True
    print("INFO: PII Purifier Engine initialized successfully.")
except Exception as e:
    PII_ENGINE_ENABLED = False
    print(f"WARNING: PII Purifier Engine failed to initialize: {e}. DLP will be limited.")

def purify_response_body(client_role: str, body: bytes, settings: Settings) -> bytes:
    """
    Uses a PII engine to find and redact sensitive data based on the pii_scan_policy.
    """
    body_str = body.decode('utf-8', errors='ignore')
    
    if not PII_ENGINE_ENABLED:
        return body

    entities_to_redact = []
    for policy in settings.pii_scan_policy:
        if policy.role == "*" or client_role == policy.role:
            entities_to_redact.extend(policy.redact_entities)
            break

    if not entities_to_redact:
        return body
        
    analyzer_results = analyzer.analyze(
        text=body_str,
        entities=entities_to_redact,
        language='en'
    )
    
    anonymized_result = anonymizer.anonymize(
        text=body_str,
        analyzer_results=analyzer_results,
        operators={"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})}
    )
    
    if anonymized_result.text != body_str:
        audit_logger.warning(
            f"AUDIT - PII_REDACTED: Purifier Engine redacted sensitive data for role '{client_role}'."
        )

    return anonymized_result.text.encode('utf-8')