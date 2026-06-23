#!/usr/bin/env python
"""
PreToolUse gate for code generation/editing tools.
Enforces policy BEFORE tool use: generated code MUST be free of dusty code (comments, TODOs, dead/legacy) AND no hardcoded values ('no it hard code').
Asks for confirmation on code-gen tools; post-review will block violations.
"""
import sys
import json
from pathlib import Path

def load_input():
    try:
        data = json.loads(sys.stdin.read().strip() or "{}")
        return data
    except:
        return {}

def main():
    data = load_input()
    tool_name = data.get("tool", {}).get("name", "") or data.get("toolName", "") or "unknown"
    hook_event = data.get("hookEventName", "PreToolUse")
    
    print(f"PreToolUse gate for code generation: reviewing intent for tool '{tool_name}'", file=sys.stderr)
    
    # List of code generation/editing tools that trigger review policy
    code_gen_tools = ["create_file", "replace_string_in_file", "multi_replace_string_in_file", 
                     "edit_notebook_file", "run_in_terminal", "vscode_renameSymbol"]
    
    is_code_gen = any(t in tool_name.lower() for t in code_gen_tools) or "edit" in tool_name.lower() or "create" in tool_name.lower()
    
    output = {
        "hookSpecificOutput": {
            "hookEventName": hook_event,
            "permissionDecision": "allow" if not is_code_gen else "ask",
            "permissionDecisionReason": "Automated review enforced: code must have ZERO dusty code (all types: comments/TODOs/dead-code) and NO hardcoded values ('no it hard code'). PostToolUse review will validate and block violations if needed."
        }
    }
    
    if is_code_gen:
        output["systemMessage"] = "⚠️ Code generation/editing tool detected. Policy reminder: AFTER generation, automated review will run. Generated code MUST NOT be dusty (no legacy comments, TODOs, dead code) and MUST NOT contain any hardcoded secrets/values. Review will FAIL violations."
    
    print(json.dumps(output))
    # Exit 0 to continue (with ask if needed for code gen)
    sys.exit(0)

if __name__ == "__main__":
    main()
