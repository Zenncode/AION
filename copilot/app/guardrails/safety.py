"""
AION Copilot — Safety Guardrails
==================================
Blocks SQL injection patterns, PII extraction, and sensitive data access.
"""

import logging
import re
from typing import Dict, List, Tuple

from app.core.config import settings

logger = logging.getLogger("aion-copilot.guardrails")


class SafetyGuardrail:
    """Multi-layer safety guard for user queries."""

    # --- SQL Injection Patterns ---
    SQL_INJECTION_PATTERNS = [
        # Classic injection
        r"(?:;\s*(?:DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE)\b)",
        r"(?:UNION\s+(?:ALL\s+)?SELECT)",
        r"(?:--\s*$|/\*.*?\*/)",
        # Comment-based injection
        r"(?:;\s*--)",
        r"(?:'\s*(?:OR|AND)\s+['\d])",
        # Stacked queries
        r"(?:;\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP))",
        # Time-based blind
        r"(?:SLEEP\s*\(|BENCHMARK\s*\(|WAITFOR\s+DELAY)",
        # File access
        r"(?:LOAD_FILE\s*\(|INTO\s+(?:OUT|DUMP)FILE)",
        # Information schema probing
        r"(?:information_schema|pg_catalog|pg_tables|sys\.)",
        # System commands
        r"(?:xp_cmdshell|sp_executesql|OPENROWSET)",
    ]

    # --- PII Patterns ---
    PII_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone_us": r"(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "phone_intl": r"\+\d{1,3}[-.\s]?\d{4,14}",
        "ssn": r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
        "credit_card": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
        "nhs_number": r"\b\d{3}\s?\d{3}\s?\d{4}\b",
        "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b",
    }

    # --- Sensitive Query Patterns ---
    SENSITIVE_QUERY_PATTERNS = [
        # Direct PII extraction attempts
        r"(?:show|display|list|get|find|search)\s+(?:all\s+)?(?:email|phone|ssn|password|credit|card)",
        r"(?:customer|user|employee)\s+(?:email|phone|address|ssn|password)",
        # Credential access
        r"(?:password|secret|token|api.?key|credential)\s*(?:=|:|is)",
        # Data exfiltration patterns
        r"(?:export|download|dump|extract)\s+(?:all|every|full)\s+(?:data|table|database)",
        # Administrative access
        r"(?:grant|revoke|admin|root|superuser)\s+(?:access|permission|role)",
    ]

    # --- Blocked Terms (PII fields in schema) ---
    BLOCKED_FIELD_NAMES = {
        "password", "passwd", "secret", "token", "api_key", "apikey",
        "ssn", "social_security", "credit_card", "card_number",
        "bank_account", "routing_number", "tax_id",
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self.sql_injection_re = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in self.SQL_INJECTION_PATTERNS
        ]
        self.pii_re = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PII_PATTERNS.items()
        }
        self.sensitive_query_re = [
            re.compile(p, re.IGNORECASE)
            for p in self.SENSITIVE_QUERY_PATTERNS
        ]

    def check(self, query: str) -> Tuple[bool, List[Dict]]:
        """
        Run all guardrail checks on a user query.

        Returns:
            (is_safe, flags) where flags is a list of violation dicts
        """
        if not settings.guardrail_enabled:
            return True, []

        flags = []

        # 1. SQL injection check
        if settings.sql_injection_block:
            sql_flags = self._check_sql_injection(query)
            flags.extend(sql_flags)

        # 2. PII detection
        if settings.pii_detection_enabled:
            pii_flags = self._check_pii(query)
            flags.extend(pii_flags)

        # 3. Sensitive query patterns
        sensitive_flags = self._check_sensitive_patterns(query)
        flags.extend(sensitive_flags)

        # 4. Blocked field names
        field_flags = self._check_blocked_fields(query)
        flags.extend(field_flags)

        is_safe = len(flags) == 0

        if not is_safe:
            logger.warning(
                "Guardrail BLOCKED query: flags=%s, query=%.100s",
                [f["type"] for f in flags], query,
            )
        else:
            logger.debug("Guardrail PASSED query: %.100s", query)

        return is_safe, flags

    def _check_sql_injection(self, query: str) -> List[Dict]:
        """Detect SQL injection patterns."""
        flags = []
        for i, pattern in enumerate(self.sql_injection_re):
            match = pattern.search(query)
            if match:
                flags.append({
                    "type": "sql_injection",
                    "severity": "high",
                    "pattern": self.SQL_INJECTION_PATTERNS[i][:60],
                    "matched": match.group(0)[:100],
                    "message": "Potential SQL injection detected",
                })
        return flags

    def _check_pii(self, query: str) -> List[Dict]:
        """Detect PII in user queries."""
        flags = []
        for pii_type, pattern in self.pii_re.items():
            match = pattern.search(query)
            if match:
                flags.append({
                    "type": "pii_detected",
                    "severity": "high",
                    "pii_type": pii_type,
                    "matched": match.group(0)[:50],
                    "message": f"PII detected: {pii_type}",
                })
        return flags

    def _check_sensitive_patterns(self, query: str) -> List[Dict]:
        """Detect queries targeting sensitive data."""
        flags = []
        for i, pattern in enumerate(self.sensitive_query_re):
            match = pattern.search(query)
            if match:
                flags.append({
                    "type": "sensitive_query",
                    "severity": "medium",
                    "pattern": self.SENSITIVE_QUERY_PATTERNS[i][:60],
                    "matched": match.group(0)[:100],
                    "message": "Query targets sensitive data",
                })
        return flags

    def _check_blocked_fields(self, query: str) -> List[Dict]:
        """Check if query references blocked field names."""
        flags = []
        query_lower = query.lower()
        for field in self.BLOCKED_FIELD_NAMES:
            if field in query_lower:
                flags.append({
                    "type": "blocked_field",
                    "severity": "medium",
                    "field": field,
                    "message": f"Query references blocked field: {field}",
                })
        return flags

    def validate_sql_output(self, sql: str) -> Tuple[bool, List[Dict]]:
        """
        Validate LLM-generated SQL before execution.
        Blocks dangerous operations even if the LLM generates them.
        """
        flags = []
        sql_upper = sql.upper().strip()

        # Block non-SELECT statements
        dangerous_starts = ("DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
                           "CREATE", "TRUNCATE", "GRANT", "REVOKE")
        if any(sql_upper.startswith(kw) for kw in dangerous_starts):
            flags.append({
                "type": "dangerous_sql",
                "severity": "critical",
                "message": "LLM generated non-SELECT SQL — blocked",
            })

        # Block system tables
        system_tables = ["information_schema", "pg_catalog", "pg_tables",
                        "sys.", "mysql.", "master."]
        for table in system_tables:
            if table in sql.lower():
                flags.append({
                    "type": "system_table_access",
                    "severity": "high",
                    "message": f"SQL references system table: {table}",
                })

        # Block multiple statements
        if sql.count(";") > 1:
            flags.append({
                "type": "multiple_statements",
                "severity": "high",
                "message": "SQL contains multiple statements",
            })

        return len(flags) == 0, flags
