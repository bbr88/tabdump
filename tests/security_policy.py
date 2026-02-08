"""Security policy registry used by tests.

Each policy is mapped to threat-model IDs, attack surface, and an actionable
control statement. Tests reference these policies via @pytest.mark.policy("SEC-xxx").
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class SecurityPolicy:
    policy_id: str
    threat_ids: Tuple[str, ...]
    attack_surface: str
    statement: str


POLICIES: Dict[str, SecurityPolicy] = {
    "SEC-001": SecurityPolicy(
        policy_id="SEC-001",
        threat_ids=("TM-005",),
        attack_surface="Vault file ingestion provenance",
        statement="Postprocess rejects dumps without tabdump_id provenance.",
    ),
    "SEC-002": SecurityPolicy(
        policy_id="SEC-002",
        threat_ids=("TM-001",),
        attack_surface="LLM outbound classification boundary",
        statement="Sensitive/auth/local/internal URLs are excluded from LLM payloads.",
    ),
    "SEC-003": SecurityPolicy(
        policy_id="SEC-003",
        threat_ids=("TM-001",),
        attack_surface="LLM payload shaping",
        statement="LLM-bound title and URL content is redacted per configured defaults.",
    ),
    "SEC-004": SecurityPolicy(
        policy_id="SEC-004",
        threat_ids=("TM-002",),
        attack_surface="API key resolution chain",
        statement="Key resolution is Keychain first with OPENAI_API_KEY as fallback only.",
    ),
    "SEC-005": SecurityPolicy(
        policy_id="SEC-005",
        threat_ids=("TM-004",),
        attack_surface="Rendered markdown integrity",
        statement="Renderer escapes title markdown controls and safely encodes link URLs.",
    ),
    "SEC-006": SecurityPolicy(
        policy_id="SEC-006",
        threat_ids=("TM-004",),
        attack_surface="Markdown link parsing",
        statement="Parser handles nested/escaped links and rejects malformed lines.",
    ),
    "SEC-007": SecurityPolicy(
        policy_id="SEC-007",
        threat_ids=("TM-003",),
        attack_surface="Runtime execution path integrity",
        statement="Monitor fails on group/world-writable critical runtime files.",
    ),
    "SEC-008": SecurityPolicy(
        policy_id="SEC-008",
        threat_ids=("TM-007",),
        attack_surface="Installer supply-chain gate",
        statement="Installer verifies runtime manifest checksums and aborts on mismatch.",
    ),
    "SEC-009": SecurityPolicy(
        policy_id="SEC-009",
        threat_ids=("TM-003",),
        attack_surface="Install-time file permission hardening",
        statement="Installer enforces restrictive umask and file/dir permissions.",
    ),
}


POLICY_IDS = tuple(POLICIES.keys())
