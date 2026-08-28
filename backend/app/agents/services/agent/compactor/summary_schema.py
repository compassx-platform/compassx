"""Structured Summary Schema and Prompt Builder for Agent Watermark Compaction (Spec D4, D5, D6)."""

from __future__ import annotations

import json
from typing import Any

STRUCTURED_SUMMARY_SCHEMA = """## Conversation Context & Progress Summary

### 1. Primary User Goal / Intent
- [High-level objective, initial request, and core problem being solved]

### 2. Catalog Objects Touched
- [List all database tables, views, schemas, catalogs, notebooks, dashboards, or volumes accessed, using fully qualified names e.g. catalog.schema.table]

### 3. Queries Run & Key Findings
- [Distilled findings, key numerical metrics, record counts, and insights from tool executions — do NOT include raw table dumps or unparsed JSON]

### 4. Files, Notebooks & Assets Created/Modified
- [Specific file paths, notebook names, saved configurations, or generated code modules]

### 5. Decisions Locked During Conversation
- [Agreed architecture, algorithms, filter constraints, confirmed parameters, and user approvals]

### 6. Errors Encountered & Resolution
- [Any tool execution failures, schema mismatches, syntax errors, and how they were resolved or worked around]

### 7. Current Task State & Pending Next Steps
- [Current milestone reached, active stage, and remaining tasks to complete]"""


SUMMARY_SYSTEM_PROMPT = f"""You are a precise, analytical conversational memory compactor for an advanced AI agent platform.

Your task is to summarize and condense past conversational turns into a single comprehensive, structured memory document.
You must strictly follow the fixed schema below.

### MANDATORY RULES:
1. **Strict Schema Adherence**: Output ONLY markdown conforming to the 7 sections shown below. Do not add or remove top-level sections.
2. **Distill Tool Results (Crucial)**: Extract facts, numbers, schema column names, and findings from tool results. NEVER dump raw data sets, thousands of query rows, or raw JSON payloads.
3. **Fold Previous Summary**: If an existing summary from earlier compaction cycles is provided, merge and fold its information into the new summary so nothing critical is lost.
4. **Preserve Exact Identifiers**: Retain exact table names (catalog.schema.table), column names, notebook paths, variable names, and error messages.
5. **Concise & Factual**: Write in tight, information-dense bullet points. Avoid pleasantries, preamble, or conversational filler.

### STRUCTURED SCHEMA TO FOLLOW:
{STRUCTURED_SUMMARY_SCHEMA}
"""


def build_compaction_user_prompt(
    existing_summary: str | None,
    turns_to_compact: list[dict[str, Any]],
) -> str:
    """Build the user prompt for the summarizer LLM call.

    Formats the previous summary (if present) and the chronological raw turns to be compacted.
    """
    parts: list[str] = []

    if existing_summary and existing_summary.strip():
        parts.append("### EXISTING SUMMARY FROM PREVIOUS COMPACTION CYCLE:\n")
        parts.append(existing_summary.strip())
        parts.append("\n\n---\n")

    parts.append("### RAW CONVERSATION TURNS TO FOLD AND COMPACT:\n")

    for idx, turn in enumerate(turns_to_compact, 1):
        parts.append(f"\n--- Turn {idx} ---")
        user_msg = turn.get("user_message")
        if user_msg:
            parts.append(f"\n[User]: {user_msg}")

        tool_calls = turn.get("tool_calls", [])
        if tool_calls:
            parts.append("\n[Tool Executions]:")
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args")
                result = tc.get("result")
                error = tc.get("error")
                ok = tc.get("ok", True)

                args_str = json.dumps(args) if isinstance(args, (dict, list)) else str(args or "")
                # Truncate overly long raw result string to avoid prompt bloating in the summarizer itself
                if isinstance(result, (dict, list)):
                    res_str = json.dumps(result)
                else:
                    res_str = str(result or "")

                if len(res_str) > 2000:
                    res_str = res_str[:2000] + "... [truncated raw tool output]"

                parts.append(f"  • Call: {name}(args={args_str[:400]})")
                if ok and result is not None:
                    parts.append(f"    Result: {res_str}")
                if error:
                    parts.append(f"    Error: {str(error)[:600]}")

        assistant_msg = turn.get("assistant_message")
        if assistant_msg:
            parts.append(f"\n[Assistant Response]: {assistant_msg}")

    parts.append(
        "\n\n---\n"
        "Now, generate the updated, unified structured summary folding all above information into the 7-section schema."
    )

    return "\n".join(parts)
