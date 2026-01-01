import wmill  # Required for get_db_connection to access Windmill resources
from typing import Dict, Any
from f.development.utils.db_utils import get_db_connection
from f.development.utils.flow_utils import check_previous_steps, estimate_tokens


def main(
    context_payload: dict,  # From Step 1
    llm_result: dict,  # From Step 2
    send_result: dict,  # From Step 3 (Meta API response)
    webhook_event_id: int = None,  # From flow input (if tracked)
    db_resource: str = "f/development/business_layer_db_postgreSQL",
) -> Dict[str, Any]:
    """
    Step 5: Usage Logging

    ONLY logs usage if Meta API successfully delivered the message.
    Tracks token usage and message counts for billing/analytics.
    Updates the usage_summary table for quick limit checks.
    """

    # Check if previous steps succeeded
    step_error = check_previous_steps(context_payload, llm_result, send_result)
    if step_error:
        print("Skipping usage logging")
        return step_error

    # Extract data from previous steps
    org_id = context_payload["chatbot"]["organization_id"]
    chatbot_id = context_payload["chatbot"]["id"]
    contact_id = context_payload["user"]["id"]
    
    # Get usage info from LLM result
    usage_info = llm_result.get("usage_info", {})
    model_name = usage_info.get("model", context_payload["chatbot"].get("model_name", "unknown"))
    provider = usage_info.get("provider", "unknown")
    
    # Token counts - try to get from LLM response metadata
    # If not available, estimate based on content length
    tokens_input = usage_info.get("tokens_input", 0)
    tokens_output = usage_info.get("tokens_output", 0)
    
    # Fallback: rough estimation if not provided
    if tokens_input == 0 and tokens_output == 0:
        user_message = llm_result.get("user_message", "")
        reply_text = llm_result.get("reply_text", "")
        tokens_input = max(estimate_tokens(user_message), 10)
        tokens_output = max(estimate_tokens(reply_text), 10)

    tokens_total = tokens_input + tokens_output

    # Cost estimation
    cost_per_1k_tokens = _get_cost_per_1k_tokens(provider, model_name)
    estimated_cost = (tokens_total / 1000.0) * cost_per_1k_tokens

    try:
        with get_db_connection(db_resource) as (conn, cur):
            # 1. Insert usage log
            cur.execute(
                """
                INSERT INTO usage_logs (
                    organization_id, chatbot_id, contact_id, webhook_event_id,
                    message_count, tokens_input, tokens_output, tokens_total,
                    model_name, provider, estimated_cost_usd, date_bucket
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)
                RETURNING id
                """,
                (org_id, chatbot_id, contact_id, webhook_event_id, 1,
                 tokens_input, tokens_output, tokens_total, model_name,
                 provider, estimated_cost),
            )
            usage_log_id = cur.fetchone()["id"]

            # 2. Update usage summary (for quick limit checks)
            cur.execute(
                """
                INSERT INTO usage_summary (
                    organization_id, current_period_messages, current_period_tokens,
                    period_start, period_end, last_updated_at
                )
                SELECT %s, 1, %s, billing_period_start, billing_period_end, NOW()
                FROM organizations WHERE id = %s
                ON CONFLICT (organization_id)
                DO UPDATE SET
                    current_period_messages = usage_summary.current_period_messages + 1,
                    current_period_tokens = usage_summary.current_period_tokens + %s,
                    last_updated_at = NOW()
                """,
                (org_id, tokens_total, org_id, tokens_total)
            )

            conn.commit()

            return {
                "success": True,
                "usage_log_id": usage_log_id,
                "tokens_used": tokens_total,
                "estimated_cost": float(estimated_cost),
                "message_count": 1,
            }

    except Exception as e:
        print(f"Usage Logging Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "tokens_used": tokens_total,
        }


def _get_cost_per_1k_tokens(provider: str, model: str) -> float:
    """
    Returns estimated cost per 1000 tokens.
    
    These are simplified rates - in production, you'd want:
    - Separate input/output pricing
    - Cached pricing from a config table
    - Regular updates as pricing changes
    """
    
    # Pricing as of Dec 2025
    # refer to https://openai.com/api/pricing/ and https://ai.google.dev/gemini-api/docs/pricing
    # IMPORTANT: Order from most specific to least specific to avoid substring matching issues
    # e.g., "gpt-4o-mini" must come before "gpt-4o" to avoid incorrect matches
    pricing = {
        "openai": {
            "gpt-5-mini": 0.00025,
        },
        "google": {
            "gemini-3-flash-preview": 0.00005,
            "gemini-2.5-flash": 0.00003,
            "gemini-2.5-flash-lite": 0.00001,
        }
    }

    provider_lower = provider.lower()
    model_lower = model.lower()

    # Match using substring - order matters! More specific models first
    if provider_lower in pricing:
        for model_key, cost in pricing[provider_lower].items():
            if model_key in model_lower:
                return cost
    
    # Fallback: conservative estimate
    return 0.001  # $1 per million tokens