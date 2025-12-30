import wmill
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any


def main(
    context_payload: dict,  # From Step 1
    llm_result: dict,  # From Step 2
    webhook_event_id: int = None,  # From flow input (if tracked)
    db_resource: str = "f/development/business_layer_db_postgreSQL",
) -> Dict[str, Any]:
    """
    Step 3_3: Usage Logging
    
    Tracks token usage and message counts for billing/analytics.
    Updates the usage_summary table for quick limit checks.
    """

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
        # Rough estimation: ~4 chars per token
        user_message = llm_result.get("user_message", "")
        reply_text = llm_result.get("reply_text", "")
        tokens_input = max(len(user_message) // 4, 10)
        tokens_output = max(len(reply_text) // 4, 10)
    
    tokens_total = tokens_input + tokens_output
    
    # Cost estimation (simplified, should be updated with actual pricing TBD)
    cost_per_1k_tokens = _get_cost_per_1k_tokens(provider, model_name)
    estimated_cost = (tokens_total / 1000.0) * cost_per_1k_tokens

    # Setup DB connection
    raw_config = wmill.get_resource(db_resource)
    db_params = {
        "host": raw_config.get("host"),
        "port": raw_config.get("port"),
        "user": raw_config.get("user"),
        "password": raw_config.get("password"),
        "dbname": raw_config.get("dbname"),
        "sslmode": "disable",
    }

    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Insert usage log
        insert_usage = """
            INSERT INTO usage_logs (
                organization_id,
                chatbot_id,
                contact_id,
                webhook_event_id,
                message_count,
                tokens_input,
                tokens_output,
                tokens_total,
                model_name,
                provider,
                estimated_cost_usd,
                date_bucket
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE
            )
            RETURNING id
        """
        
        cur.execute(
            insert_usage,
            (
                org_id,
                chatbot_id,
                contact_id,
                webhook_event_id,
                1,  # message_count
                tokens_input,
                tokens_output,
                tokens_total,
                model_name,
                provider,
                estimated_cost,
            ),
        )
        
        usage_log_id = cur.fetchone()["id"]

        # 2. Update usage summary (for quick limit checks)
        update_summary = """
            INSERT INTO usage_summary (
                organization_id,
                current_period_messages,
                current_period_tokens,
                period_start,
                period_end,
                last_updated_at
            )
            SELECT 
                %s,
                1,
                %s,
                billing_period_start,
                billing_period_end,
                NOW()
            FROM organizations
            WHERE id = %s
            ON CONFLICT (organization_id) 
            DO UPDATE SET
                current_period_messages = usage_summary.current_period_messages + 1,
                current_period_tokens = usage_summary.current_period_tokens + %s,
                last_updated_at = NOW()
        """
        
        cur.execute(update_summary, (org_id, tokens_total, org_id, tokens_total))

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
        if conn:
            conn.rollback()
        return {
            "success": False,
            "error": str(e),
            "tokens_used": tokens_total,  # Still report even if logging failed
        }
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals():
            conn.close()


def _get_cost_per_1k_tokens(provider: str, model: str) -> float:
    """
    Returns estimated cost per 1000 tokens.
    
    These are simplified rates - in production, you'd want:
    - Separate input/output pricing
    - Cached pricing from a config table
    - Regular updates as pricing changes
    """
    
    # Pricing as of Dec 2024 (approximate)
    pricing = {
        "openai": {
            "gpt-4o": 0.005,
            "gpt-4o-mini": 0.0002,
            "gpt-4-turbo": 0.01,
            "gpt-3.5-turbo": 0.0015,
        },
        "google": {
            "gemini-3-flash-preview": 0.00025,
        },
        "anthropic": {
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003,
            "claude-3-haiku": 0.00025,
        },
    }
    
    provider_lower = provider.lower()
    model_lower = model.lower()
    
    # Try exact match first
    if provider_lower in pricing:
        for model_key, cost in pricing[provider_lower].items():
            if model_key in model_lower:
                return cost
    
    # Fallback: conservative estimate
    return 0.001  # $1 per million tokens


def estimate_tokens_from_text(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token.
    This is a simplified heuristic - in production, use tiktoken or similar.
    """
    return max(len(text) // 4, 1)