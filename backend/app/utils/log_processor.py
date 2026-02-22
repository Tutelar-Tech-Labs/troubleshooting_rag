import re

def extract_key_lines(log_text: str, max_lines: int = 100, max_chars: int = 10000) -> str:
    """
    Improved log processing pipeline:
    1. Remove timestamp + process prefix
    2. Filter by relevant keywords
    3. Remove duplicate lines
    4. Limit total size for LLM context
    """
    keywords = [ 
        "error", "fail", "failed", "timeout", "blocked", 
        "deny", "disconnect", "certificate", "auth", 
        "authentication", "portal", "gateway", "policy", "enforcer" 
    ] 
    
    keyword_pattern = re.compile("|".join(keywords), re.IGNORECASE) 
    # Pattern to match GlobalProtect log prefix: P1234-T5678 02/13/2026 01:17:32:456
    prefix_pattern = re.compile(r'^P\d+-T\d+\s+\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}:\d+\s+') 

    lines = log_text.splitlines() 
    relevant_lines = [] 
    seen = set() 

    for line in lines: 
        # Remove timestamp + prefix 
        clean_line = prefix_pattern.sub('', line) 

        if keyword_pattern.search(clean_line): 
            if clean_line not in seen: 
                relevant_lines.append(clean_line.strip()) 
                seen.add(clean_line) 

            if len(relevant_lines) >= max_lines: 
                break 

    # Fallback if nothing found: take last 50 lines without prefix
    if not relevant_lines: 
        for line in lines[-50:]:
            clean_line = prefix_pattern.sub('', line).strip()
            if clean_line:
                relevant_lines.append(clean_line)

    result = "\n".join(relevant_lines) 

    # Size limit 
    if len(result) > max_chars: 
        half = max_chars // 2 
        result = result[:half] + "\n... [TRUNCATED] ...\n" + result[-half:] 

    print(f"--- DEBUG FILTERED LOG (First 500 chars) ---\n{result[:500]}\n--- END DEBUG ---") 

    return result
