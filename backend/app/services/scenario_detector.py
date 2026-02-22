from typing import Dict, Any, List, Optional

def detect_scenario(filtered_log: str, detected_issue: str) -> Optional[Dict[str, Any]]:
    """
    Scenario Intelligence Layer: Identifies specific operational scenarios based on log keywords.
    Priority: 
    1. hip_missing
    2. ipv6
    3. saml_browser
    4. enforcement_block
    """
    log_lower = filtered_log.lower()
    
    # 1. HIP / Content Filter Missing
    hip_keywords = [
        "content filter",
        "hip check failed",
        "hip report missing",
        "hip report not received",
        "host info missing",
        "host information not received",
        "host info timeout",
        "endpoint not compliant",
        "compliance failed",
        "missing required component",
        "hip failure",
        "no host information",
        "mac content filter"
    ]
    if any(k in log_lower for k in hip_keywords):
        return {
            "scenario": "hip_missing",
            "detected_issue": "Endpoint compliance failure: required Content Filter/HIP component missing.",
            "root_cause": "Required Content Filter is not installed or not detected by HIP.",
            "user_impact": "User cannot access network resources due to HIP enforcement.",
            "steps": [
                "Verify Content Filter installation on the endpoint.",
                "Reinstall or update Content Filter if missing.",
                "Confirm HIP report is generated successfully.",
                "Reconnect GlobalProtect."
            ],
            "faiss_query": "GlobalProtect HIP content filter"
        }

    # 2. IPv6 Issue
    ipv6_keywords = [
        "ipv6",
        "ipv6 address",
        "ipv6 route"
    ]
    if any(k in log_lower for k in ipv6_keywords):
        return {
            "scenario": "ipv6",
            "detected_issue": "GlobalProtect connectivity failure due to IPv6 configuration.",
            "root_cause": "GlobalProtect tunnel does not support IPv6 traffic properly.",
            "user_impact": "Internet does not work when GlobalProtect is connected with IPv6 enabled.",
            "steps": [
                "Open network adapter settings.",
                "Disable IPv6.",
                "Reconnect GlobalProtect.",
                "Verify internet connectivity."
            ],
            "faiss_query": "GlobalProtect IPv6 connectivity"
        }

    # 3. Embedded Browser / SAML Failure
    saml_keywords = [
        "saml", 
        "browser", 
        "webview", 
        "cannot load login"
    ]
    if any(k in log_lower for k in saml_keywords):
        return {
            "scenario": "saml_browser",
            "detected_issue": "GlobalProtect SAML authentication failure due to embedded browser connectivity issue.",
            "root_cause": "Embedded browser cannot reach Identity Provider due to network restrictions.",
            "user_impact": "User cannot complete login.",
            "steps": [
                "Verify endpoint internet access.",
                "Check firewall or proxy restrictions.",
                "Allow access to IdP URLs.",
                "Retry authentication."
            ],
            "faiss_query": "GlobalProtect SAML embedded browser"
        }

    # 4. Enforcement Block (True Policy Block)
    enforcement_keywords = [
        "enforcer block port", 
        "application blocked", 
        "policy deny"
    ]
    if any(k in log_lower for k in enforcement_keywords):
        return {
            "scenario": "enforcement_block",
            "detected_issue": "GlobalProtect endpoint enforcement policy is blocking application traffic.",
            "root_cause": "Endpoint enforcement or HIP policy is restricting network access.",
            "user_impact": "Applications or browser traffic may fail.",
            "steps": [
                "Review enforcement policy on firewall.",
                "Verify HIP profile compliance.",
                "Adjust policy if required.",
                "Reconnect GlobalProtect."
            ],
            "faiss_query": "GlobalProtect endpoint enforcement block"
        }

    return None
