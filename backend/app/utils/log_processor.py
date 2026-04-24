import re
from datetime import datetime
from typing import Dict, List, Any

def parse_timestamp(line):
    """
    Parse timestamp from real GP log lines.
    Real format examples:
      04/05/26 13:54:35:372   -> MM/DD/YY HH:MM:SS:mmm
      08/20 15:30:45          -> MM/DD HH:MM:SS
    """
    # Try full format with year: MM/DD/YY HH:MM:SS
    match = re.search(r'(\d{2}/\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})', line)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%m/%d/%y %H:%M:%S")
        except:
            pass
    
    # Fallback: MM/DD HH:MM:SS (no year)
    match = re.search(r'(\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})', line)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%m/%d %H:%M:%S")
        except:
            pass
    return None


def _normalize_user_time(time_str):
    """
    Accept flexible user input formats and normalize to datetime.
    Handles: MM/DD/YY HH:MM:SS:mmm, MM/DD/YY HH:MM:SS, MM/DD/YY HH:MM,
             MM/DD HH:MM:SS, MM/DD HH:MM
    """
    time_str = time_str.strip()
    
    # Strip milliseconds if present (e.g. "04/06/26 11:31:12:364" -> "04/06/26 11:31:12")
    # Pattern: anything ending in :NNN (3-digit ms) after seconds
    ms_match = re.match(r'^(.+:\d{2}):(\d{3})$', time_str)
    if ms_match:
        time_str = ms_match.group(1)
        print(f"[TIME FILTER] Stripped milliseconds: '{time_str}'")
    
    # Auto-append :00 if seconds missing
    # MM/DD/YY HH:MM -> MM/DD/YY HH:MM:00
    if re.match(r'^\d{2}/\d{2}/\d{2} \d{2}:\d{2}$', time_str):
        time_str = time_str + ":00"
    # MM/DD HH:MM -> MM/DD HH:MM:00
    elif re.match(r'^\d{2}/\d{2} \d{2}:\d{2}$', time_str):
        time_str = time_str + ":00"
    
    # Try all known formats
    formats = [
        "%m/%d/%y %H:%M:%S",
        "%m/%d %H:%M:%S",
        "%d/%m %H:%M:%S",
        "%d/%m/%y %H:%M:%S",
    ]
    
    for fmt in formats:
        try:
            result = datetime.strptime(time_str, fmt)
            print(f"[TIME FILTER] Parsed '{time_str}' with format '{fmt}' -> {result}")
            return result
        except:
            continue
    
    return None


def filter_logs_by_time(log_text: str, start: str, end: str) -> str:
    if not log_text or not start or not end:
        return log_text
    
    start_dt = _normalize_user_time(start)
    end_dt = _normalize_user_time(end)
    
    if not start_dt or not end_dt:
        print(f"[TIME FILTER FAIL] Could not parse: start='{start}' end='{end}'")
        print(f"[TIME FILTER FAIL] Accepted formats: MM/DD HH:MM:SS, MM/DD HH:MM, MM/DD/YY HH:MM:SS")
        return log_text

    print(f"[TIME FILTER] Parsed: {start_dt} to {end_dt}")

    filtered = []
    for line in log_text.splitlines():
        ts = parse_timestamp(line)
        if ts is None:
            # Keep non-timestamped lines (headers, separators) 
            continue
        # Compare only month/day/time (ignore year mismatches if user didn't provide year)
        ts_compare = ts.replace(year=start_dt.year)
        if start_dt <= ts_compare <= end_dt:
            filtered.append(line)

    if not filtered:
        print(f"[TIME FILTER WARNING] Filter yielded 0 lines! Check your time range.")
        return ""
    
    print(f"[TIME FILTER] Reduced to {len(filtered)} lines")
    return "\n".join(filtered)


def detect_gp_stages(pangps_text, pangpa_text=""):
    """
    Detect GP connection stages from real log markers.
    Returns structured stage analysis for LLM reasoning.
    """
    combined = (pangps_text or "") + "\n" + (pangpa_text or "")
    lower = combined.lower()
    
    # Real GP connection stages in order
    stage_markers = [
        ("portal_processing", ["portal processing start", "portal process start"]),
        ("portal_prelogin", ["portal pre-login start", "portal prelogin start", "prelogin to portal"]),
        ("portal_login", ["portal login start", "login to portal", "portal login"]),
        ("network_discover", ["network discover start", "network discovery", "discover available network"]),
        ("gateway_prelogin", ["gateway pre-login start", "gateway prelogin start", "prelogin to gateway"]),
        ("gateway_login", ["gateway login start", "login to gateway", "gateway login"]),
        ("tunnel_creation", ["tunnel creation start", "create tunnel", "tunnel connection", "ipsec connection"]),
        ("tunnel_connected", ["tunnel established", "tunnel connected", "connected to gateway", "agent connected"]),
    ]
    
    # Failure indicators
    failure_markers = [
        "failed", "error", "timeout", "connection refused", "socket error",
        "ssl error", "certificate", "authentication failed", "denied",
        "service stopped", "crash", "aborted", "unreachable"
    ]
    
    # Detect which stages are present
    stages_found = []
    for stage_name, markers in stage_markers:
        for marker in markers:
            if marker in lower:
                stages_found.append(stage_name)
                break
    
    # Detect failure lines
    failure_lines = []
    for line in combined.splitlines():
        line_lower = line.lower().strip()
        if any(f in line_lower for f in failure_markers):
            failure_lines.append(line.strip())
    
    # Determine failure point
    failure_stage = None
    last_success = None
    failure_category = "unknown"
    
    # Work backwards: last stage found without "connected/success" after it = failure point
    stage_order = ["portal_processing", "portal_prelogin", "portal_login", 
                   "network_discover", "gateway_prelogin", "gateway_login", 
                   "tunnel_creation", "tunnel_connected"]
    
    for stage in reversed(stage_order):
        if stage in stages_found:
            if stage == "tunnel_connected":
                last_success = "tunnel_connected"
                continue
            # Check if this is where failure occurred
            if last_success is None:
                failure_stage = stage
            else:
                last_success = stage
    
    # If all stages found and tunnel_connected present → no failure
    if "tunnel_connected" in stages_found and failure_stage is None:
        last_success = "tunnel_connected"
    
    # Determine failure category for FAISS alignment
    if failure_stage:
        if "portal" in failure_stage:
            failure_category = "portal_connectivity"
        elif "gateway_login" in failure_stage or "gateway_prelogin" in failure_stage:
            failure_category = "authentication"
        elif "tunnel" in failure_stage:
            failure_category = "network_ssl"
        elif "network_discover" in failure_stage:
            failure_category = "network_discovery"
    
    # Build human-readable flow
    flow_lines = []
    for stage in stage_order:
        if stage in stages_found:
            if stage == failure_stage:
                flow_lines.append(f"{stage} → FAILURE")
            elif stage == "tunnel_connected":
                flow_lines.append(f"{stage} → connected")
            else:
                flow_lines.append(f"{stage} → success")
    
    stage_flow = "\n".join(flow_lines) if flow_lines else "No GP stages detected in logs"
    
    result = {
        "stages_found": stages_found,
        "stage_flow": stage_flow,
        "failure_stage": failure_stage,
        "last_success": last_success,
        "failure_category": failure_category,
        "failure_lines": failure_lines[-10:],  # Last 10 failure lines
    }
    
    print(f"[GP STAGES] Found: {stages_found}")
    print(f"[GP STAGES] Failure stage: {failure_stage}")
    print(f"[GP STAGES] Category: {failure_category}")
    
    return result


def correlate_logs(pangps_text, pangpa_text):
    issue = []
    
    # Detect auth issues
    if "authentication failed" in pangps_text.lower() or "invalid credentials" in pangpa_text.lower():
        issue.append("Authentication failure between service (pangps) and agent (pangpa)")
    
    # Detect tunnel issues
    if "tunnel down" in pangps_text.lower() or "connection lost" in pangpa_text.lower():
        issue.append("Tunnel instability detected between pangps and pangpa")
    
    # Detect service crash
    if "service stopped" in pangps_text.lower():
        issue.append("GlobalProtect service (pangps) crashed or stopped unexpectedly")
    
    # Detect reconnect loops
    if "reconnecting" in pangpa_text.lower():
        issue.append("Agent (pangpa) stuck in reconnect loop")

    if not issue:
        return "No major correlated issue detected"

    return " | ".join(issue)


def detect_resolution(pangps, pangpa):
    last_pangps = "\n".join(pangps.splitlines()[-50:])
    last_pangpa = "\n".join(pangpa.splitlines()[-50:])

    text = (last_pangps + last_pangpa).lower()

    # Success indicators
    success_patterns = [
        "connected",
        "tunnel established",
        "agent connected",
        "login successful"
    ]

    # Failure indicators
    failure_patterns = [
        "authentication failed",
        "tunnel down",
        "connection failed",
        "service stopped"
    ]

    success = any(p in text for p in success_patterns)
    failure = any(p in text for p in failure_patterns)

    if success and not failure:
        return "resolved"
    elif failure and not success:
        return "active"
    elif success and failure:
        return "resolved"  # recovered case
    else:
        return "unknown"


def extract_error_history(*logs):
    errors = []

    keywords = ["error", "failed", "warning", "critical"]

    for log in logs:
        if not log:
            continue

        for line in log.splitlines():
            line_lower = line.lower()
            if any(k in line_lower for k in keywords):
                errors.append(line.strip())

    return errors


def create_time_chunks(pangps, pangpa, window_size=50):
    pangps_lines = pangps.splitlines()
    pangpa_lines = pangpa.splitlines()
    
    chunks = []

    for i in range(0, len(pangps_lines), window_size):
        p1 = pangps_lines[i:i+window_size]
        p2 = pangpa_lines[i:i+window_size]

        chunk = "\n".join(p1) + "\n---\n" + "\n".join(p2)
        chunks.append(chunk)

    return chunks

def create_additional_chunks(event, system):
    chunks = []
    if event and event.strip():
        chunks.append(event)
    if system and system.strip():
        chunks.append(system)
    return chunks


def smart_prioritize_chunks(chunks, max_for_llm=10):
    """
    Two-level chunk usage:
    Level 1: All chunks → used for FAISS retrieval
    Level 2: Top relevant (error-focused) chunks → used for LLM
    """
    error_keywords = ["error", "failed", "disconnect", "authentication", 
                      "timeout", "tunnel down", "connection failed", "critical",
                      "service stopped", "blocked", "denied"]
    
    scored = []
    for i, chunk in enumerate(chunks):
        lower = chunk.lower()
        score = sum(1 for kw in error_keywords if kw in lower)
        scored.append((score, i, chunk))
    
    # Sort by score descending (most error-heavy first)
    scored.sort(key=lambda x: x[0], reverse=True)
    
    prioritized = [item[2] for item in scored[:max_for_llm]]
    return prioritized


def intelligent_fallback(previous_errors):
    """
    When correlation returns 'No major correlated issue detected',
    generate a meaningful issue from error history.
    """
    if not previous_errors:
        return "Log analysis completed — no critical errors detected in the analyzed time window"
    
    # Count error patterns
    patterns = {}
    pattern_keywords = [
        ("authentication", "Repeated authentication failures detected"),
        ("tunnel", "Multiple tunnel disconnections observed"),
        ("connection", "System experienced intermittent connection issues"),
        ("timeout", "Multiple timeout events detected"),
        ("certificate", "Certificate validation errors detected"),
        ("service stopped", "GlobalProtect service interruptions detected"),
        ("failed", "Multiple failure events detected in logs"),
        ("error", "System errors detected requiring investigation")
    ]
    
    for err in previous_errors:
        lower = err.lower()
        for keyword, description in pattern_keywords:
            if keyword in lower:
                patterns[description] = patterns.get(description, 0) + 1
    
    if patterns:
        # Return the most frequent pattern
        top_issue = max(patterns, key=patterns.get)
        count = patterns[top_issue]
        return f"{top_issue} ({count} occurrences)"
    
    # Last resort: use most recent error
    return f"Issue detected: {previous_errors[-1][:150]}"


