"""
Flow Utilities

Pure Python helper functions for Windmill flows.
These functions have NO external dependencies (no wmill, no psycopg2).
"""

from typing import Dict, Any, Optional


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token.
    Used as fallback when actual token counts aren't available.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count (minimum 1)
    """
    return max(len(text) // 4, 1)


def check_previous_steps(
    context_payload: dict,
    llm_result: Optional[dict] = None,
    send_result: Optional[dict] = None
) -> Optional[Dict[str, Any]]:
    """
    Common validation for checking if previous steps succeeded.

    Args:
        context_payload: Result from Step 1
        llm_result: Result from Step 2 (optional)
        send_result: Result from Step 3 (optional)

    Returns:
        None if all checks pass, or error dict if any step failed
    """
    # Check Step 1
    if not context_payload.get("proceed", False):
        reason = context_payload.get("reason", "Unknown error")
        print(f"Step 1 failed: {reason}")
        return {"success": False, "error": f"Cannot proceed - Step 1 failed: {reason}"}

    # Check Step 2 (if provided)
    if llm_result is not None and "error" in llm_result:
        error = llm_result.get("error", "Unknown error")
        print(f"Step 2 failed: {error}")
        return {"success": False, "error": f"Cannot proceed - Step 2 failed: {error}"}

    # Check Step 3 (if provided)
    if send_result is not None and not send_result.get("success", False):
        error = send_result.get("error", "Message not delivered")
        print(f"Step 3 failed: {error}")
        return {"success": False, "error": f"Cannot proceed - Step 3 failed: {error}"}

    return None  # All checks passed
