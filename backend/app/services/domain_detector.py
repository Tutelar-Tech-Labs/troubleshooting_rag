from typing import Literal


def detect_domain(text: str) -> Literal["globalprotect", "panorama_config", "prisma", "ipsec"]:
    """
    Simple keyword-based domain detection for PAN-OS operations.
    """
    if not text:
        return "globalprotect"

    lower_text = text.lower()

    panorama_keywords = [
        "commit",
        "commit failed",
        "commit validation",
        "validation error",
        "cannot delete",
        "object in use",
        "reference from",
        "panorama",
        "commit error",
        "validation failed",
    ]

    prisma_keywords = [
        "prisma",
        "cloud_services",
        "remote network",
        "remote-network",
        "multi-tenant",
        "onboarding",
    ]

    ipsec_keywords = [
        "ipsec",
        "ike gateway",
        "tunnel configuration",
        "vpn tunnel",
    ]

    if any(k in lower_text for k in panorama_keywords):
        return "panorama_config"

    if any(k in lower_text for k in prisma_keywords):
        return "prisma"

    if any(k in lower_text for k in ipsec_keywords):
        return "ipsec"

    return "globalprotect"

