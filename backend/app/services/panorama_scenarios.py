from typing import Dict, Any, Optional


def detect_panorama_scenario(text: str) -> Optional[Dict[str, Any]]:
    """
    Detect well-known Panorama commit / validation scenarios.
    """
    if not text:
        return None

    lower_text = text.lower()

    dependency_keywords = [
        "cannot delete",
        "reference from",
        "object in use",
        "still referenced",
        "validation error",
        "validation failed",
    ]

    if any(k in lower_text for k in dependency_keywords):
        return {
            "scenario": "panorama_commit_dependency",
            "detected_issue": "Panorama commit validation failure due to configuration dependency.",
            "root_cause": "The object (such as an IPsec tunnel or IKE gateway) is still referenced in another Panorama configuration component.",
            "user_impact": "Configuration changes cannot be committed until dependencies are removed.",
            "steps": [
                "Review the full commit validation error and note the reference path.",
                "Locate where the object is used in Panorama templates, device groups, or Remote Network configuration.",
                "Remove, update, or rename the referenced object so it no longer conflicts.",
                "Retry the commit operation from Panorama.",
            ],
            "faiss_query": "Panorama commit validation reference dependency",
        }

    return None

