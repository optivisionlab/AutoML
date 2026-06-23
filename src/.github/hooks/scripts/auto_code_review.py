#!/usr/bin/env python
"""
Automated Code Review Hook (PostToolUse).
Enforces AFTER code generation:
- NO dusty code: excessive comments, TODO/FIXME/HACK, commented-out funcs, dead code patterns (ALL types per feedback).
- NO hardcoded values/secrets ('no it hard code' policy) including keys, tokens, passwords, JWTs etc.
Also flags hashing. Blocks violations (exit 2). Scans all relevant source files. Optional ruff integration.
Reads JSON from stdin (hook context), outputs structured decision for Copilot hook system.
"""
import sys
import json
import re
import subprocess
from pathlib import Path

def load_hook_input():
    try:
        input_data = sys.stdin.read().strip()
        if input_data:
            return json.loads(input_data)
        return {"hookEventName": "PostToolUse", "tool": "unknown"}
    except:
        return {"hookEventName": "PostToolUse", "tool": "unknown"}

def is_dusty_code(content: str) -> list[str]:
    issues = []
    # Detect excessive comments (dusty legacy code) - per "all of the above"
    comment_lines = len(re.findall(r'^\s*#.*$', content, re.MULTILINE))
    if comment_lines > 15:
        issues.append(f"Excessive comments ({comment_lines} lines) - potential dusty/legacy code")
    # Large multi-line strings or commented sections
    if re.search(r'(""".*?"""|'''.*?''')', content, re.DOTALL | re.MULTILINE) and len(content.splitlines()) > 30:
        issues.append("Large multi-line comment/docstring block - may be dusty code")
    # Unresolved TODOs, FIXME, XXX, HACK (all dusty indicators)
    if re.search(r'(TODO|FIXME|XXX|HACK|deprecated):?', content, re.IGNORECASE):
        issues.append("Unresolved TODO/FIXME/XXX/HACK - indicates dusty code that needs cleanup")
    # Commented-out functional code (common dusty pattern)
    if re.search(r'^\s*#\s*(def |class |if |for |while |import |[a-z_]+\s*=|print\()', content, re.MULTILINE):
        issues.append("Commented-out functional code detected (dusty code)")
    # Simple dead/unused code indicators
    if re.search(r'return[^;]*?\n\s+pass\b|^\s*pass\s*#\s*TODO', content, re.DOTALL | re.MULTILINE):
        issues.append("Potential dead code (e.g. return followed by pass)")
    return issues

def has_hardcoded(content: str) -> list[str]:
    """Detect hardcoded secrets, keys, passwords, tokens etc. ('no it hard code' policy).
    Also flags hashing if used for code obfuscation.
    """
    issues = []
    hardcoded_patterns = [
        r'(password|passwd|pwd|secret|api[_-]?key|token|auth|private_key)\s*[:=]\s*["\'](?![^"\']*\{)[^"\']{8,32}["\']',
        r'\b(eyJ[A-Za-z0-9_-]{20,})\b',  # JWT tokens
        r'\b[A-Za-z0-9+/]{20,}={0,2}\b(?=.*[A-Z0-9]{4,})',  # base64-like secrets
        r'http[s]?://[^\s"\'`]{5,}@',  # URLs with embedded creds
        r'(localhost|0\.0\.0\.0|127\.0\.0\.1).*(password|key|token|secret)', 
        r'hard[-_]?code|hardcoded'
    ]
    for pattern in hardcoded_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append(f"Hardcoded value/secret detected matching '{pattern.split('(')[0]}' - violates 'no hard code' policy")
    # Flag hashing functions (as original concern)
    if re.search(r'(hashlib|hash\(|md5|sha1|sha256|bcrypt|argon2)', content, re.IGNORECASE):
        issues.append("Hashing/crypto function detected - avoid unless for legitimate non-hardcoded use")
    return issues

def review_file(file_path: Path) -> dict:
    if not file_path.exists() or file_path.name.startswith('.'):
        return {"issues": [], "passed": True, "file": str(file_path)}
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        dusty_issues = is_dusty_code(content)
        hardcode_issues = has_hardcoded(content)
        all_issues = dusty_issues + hardcode_issues
        passed = len(all_issues) == 0
        if not passed and 'backend' in str(file_path):
            # Try to run Black or ruff check if available for deeper analysis (dusty/dead code)
            try:
                subprocess.run(['ruff', 'check', '--select', 'F401,F841,ERA'], capture_output=True, timeout=5)  # unused, commented
            except:
                pass  # ruff optional
        return {
            "issues": all_issues,
            "passed": passed,
            "file": str(file_path)
        }
    except Exception as e:
        return {"issues": [f"Review error: {str(e)}"], "passed": False, "file": str(file_path)}

def get_changed_files():
    try:
        # Get recently modified files or git diff
        result = subprocess.run(['git', 'diff', '--name-only', 'HEAD'], 
                              capture_output=True, text=True, cwd=Path.cwd(), timeout=10)
        files = [Path(f.strip()) for f in result.stdout.strip().split('\n') if f.strip()]
        if not files:
            # Fallback to common source files
            files = list(Path.cwd().rglob("*.py"))[:5]  # limit
        return files
    except:
        return list(Path.cwd().rglob("*.py"))[:3]  # fallback

def main():
    hook_input = load_hook_input()
    print("Running automated code review after generation...", file=sys.stderr)
    
    changed_files = get_changed_files()
    reviews = []
    has_violations = False
    
    for fpath in changed_files:
        if fpath.suffix in ('.py', '.js', '.ts', '.yaml', '.json', '.md', '.html', '.css') or any(p in str(fpath) for p in ['src', 'backend', 'frontend']):
            # Apply to all source files as per user feedback
            review = review_file(fpath)
            reviews.append(review)
            if not review.get("passed", True):
                has_violations = True
    
    decision = {
        "continue": not has_violations,
        "hookSpecificOutput": {
            "hookEventName": hook_input.get("hookEventName", "PostToolUse"),
            "reviewSummary": {
                "filesReviewed": len([r for r in reviews if 'file' in r]),
                "violationsFound": len([r for r in reviews if not r.get("passed", True)]),
                "rulesEnforced": ["no-dusty-code (comments, TODOs, dead-code, legacy blocks)", "no-hardcoded-values (secrets, keys, per 'no it hard code')"]
            }
        }
    }
    
    if has_violations:
        decision["stopReason"] = "Code review FAILED: dusty code or hardcoded values detected. The code must be clean with no dusty elements and no hard-coded secrets. Fix and retry."
        print(json.dumps(decision), file=sys.stdout)
        sys.exit(2)  # blocking error per policy
    else:
        decision["systemMessage"] = "✅ Automated code review PASSED after generation: No dusty code or hardcoded values found. Code is clean, fresh, and compliant with the rules."
        print(json.dumps(decision))
        sys.exit(0)

if __name__ == "__main__":
    main()
