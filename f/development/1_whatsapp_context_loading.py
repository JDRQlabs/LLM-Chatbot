import wmill
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional


def main(
    whatsapp_phone_id: str,
    user_phone: str,
    message_id: str,  # NEW: WhatsApp message ID for idempotency
    user_name: str = "Unknown",
    db_resource: str = "f/development/business_layer_db_postgreSQL",
) -> Dict[str, Any]:
    """
    Step 1: Context Loading + Idempotency Check + Usage Limits
    
    This step:
    1. Checks for duplicate messages (idempotency)
    2. Validates tenant usage limits
    3. Loads chatbot configuration
    4. Fetches user context and history
    5. Loads enabled tools/integrations
    """

    # Setup DB Connection
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
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return {
            "proceed": False,
            "reason": f"DB Connection Failed: {str(e)}",
            "notify_admin": True,
        }

    try:
        # ============================================================
        # STEP 1A: LOOK UP WEBHOOK EVENT
        # ============================================================
        # The webhook_events record is created by Express (webhook-server)
        # before triggering Windmill. We just need to look it up here.
        # This avoids duplicate idempotency checks and race conditions.
        webhook_lookup = """
            SELECT id, status, processed_at
            FROM webhook_events
            WHERE whatsapp_message_id = %s
        """
        cur.execute(webhook_lookup, (message_id,))
        existing_event = cur.fetchone()

        if existing_event:
            status = existing_event["status"]
            webhook_event_id = existing_event["id"]

            # If already completed, skip (shouldn't happen but handle gracefully)
            if status == "completed":
                print(f"Message already processed: {message_id}")
                return {
                    "proceed": False,
                    "reason": "Already Processed",
                    "webhook_event_id": webhook_event_id,
                }
        else:
            # No existing record - Express should have created it
            # Create one as fallback (for backwards compatibility / manual testing)
            print(f"Warning: No webhook_events record found for {message_id}, creating one")
            create_event = """
                INSERT INTO webhook_events (
                    whatsapp_message_id,
                    phone_number_id,
                    status,
                    received_at
                ) VALUES (%s, %s, 'processing', NOW())
                ON CONFLICT (whatsapp_message_id) DO UPDATE SET status = 'processing'
                RETURNING id
            """
            cur.execute(create_event, (message_id, whatsapp_phone_id))
            webhook_event_id = cur.fetchone()["id"]
            conn.commit()

        # ============================================================
        # STEP 1B: FETCH CHATBOT + ORGANIZATION
        # ============================================================
        bot_query = """
            SELECT
                c.id,
                c.organization_id,
                c.name,
                c.system_prompt,
                c.persona,
                c.model_name,
                c.temperature,
                c.rag_enabled,
                c.whatsapp_access_token,
                c.is_active,
                c.fallback_message_error,
                c.fallback_message_limit,
                -- Organization info
                o.name as org_name,
                o.plan_tier,
                o.is_active as org_is_active,
                o.message_limit_monthly,
                o.token_limit_monthly,
                o.billing_period_start,
                o.billing_period_end
            FROM chatbots c
            JOIN organizations o ON c.organization_id = o.id
            WHERE c.whatsapp_phone_number_id = %s
        """
        cur.execute(bot_query, (whatsapp_phone_id,))
        bot = cur.fetchone()

        if not bot:
            print(f"No chatbot found for WhatsApp ID: {whatsapp_phone_id}")
            _mark_webhook_failed(cur, webhook_event_id, "Chatbot not found")
            conn.commit()
            return {
                "proceed": False,
                "reason": "Chatbot not found",
                "notify_admin": True,
            }

        # Check if org/chatbot is active
        if not bot["org_is_active"] or not bot["is_active"]:
            print(f"Chatbot or Organization is inactive")
            _mark_webhook_failed(cur, webhook_event_id, "Service inactive")
            conn.commit()
            return {
                "proceed": False,
                "reason": "Service Inactive",
                "notify_admin": True,
            }

        chatbot_id = bot["id"]
        org_id = bot["organization_id"]

        # Update webhook event with chatbot_id
        cur.execute(
            "UPDATE webhook_events SET chatbot_id = %s WHERE id = %s",
            (chatbot_id, webhook_event_id)
        )
        conn.commit()

        # ============================================================
        # STEP 1C: CHECK USAGE LIMITS
        # ============================================================
        usage_check_result = _check_usage_limits(
            cur, 
            org_id, 
            bot["message_limit_monthly"], 
            bot["token_limit_monthly"],
            bot["billing_period_start"],
            bot["billing_period_end"]
        )

        if not usage_check_result["has_quota"]:
            print(f"Organization {org_id} has exceeded usage limits")
            _mark_webhook_failed(cur, webhook_event_id, "Usage limit exceeded")
            conn.commit()
            
            return {
                "proceed": False,
                "reason": "Usage Limit Exceeded",
                "notify_admin": True,  # Send notification to org owner
                "usage_info": usage_check_result,
                "chatbot": {
                    "id": chatbot_id,
                    "organization_id": org_id,
                    "wa_token": bot["whatsapp_access_token"],
                },
            }

        # ============================================================
        # STEP 1D: UPSERT CONTACT
        # ============================================================
        contact_upsert = """
            INSERT INTO contacts (chatbot_id, phone_number, name, last_message_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (chatbot_id, phone_number) 
            DO UPDATE SET 
                name = EXCLUDED.name, 
                last_message_at = NOW()
            RETURNING id, conversation_mode, variables, tags
        """
        cur.execute(contact_upsert, (chatbot_id, user_phone, user_name))
        contact = cur.fetchone()
        conn.commit()

        # Check for manual mode (human takeover)
        if contact["conversation_mode"] == "manual":
            print(f"User {user_phone} is in MANUAL mode")
            _mark_webhook_completed(cur, webhook_event_id)
            conn.commit()
            return {
                "proceed": False,
                "reason": "Manual Mode - Human Agent Required",
            }

        # ============================================================
        # STEP 1E: FETCH ACTIVE TOOLS/INTEGRATIONS
        # ============================================================
        tools_query = """
            SELECT 
                oi.id as integration_id,
                oi.provider, 
                oi.name, 
                oi.config, 
                oi.credentials,
                ci.settings_override,
                ci.is_enabled
            FROM chatbot_integrations ci
            JOIN org_integrations oi ON ci.integration_id = oi.id
            WHERE ci.chatbot_id = %s 
              AND ci.is_enabled = TRUE
              AND oi.is_active = TRUE
        """
        cur.execute(tools_query, (chatbot_id,))
        tools_rows = cur.fetchall()

        active_tools = []
        for t in tools_rows:
            base_config = t["config"] or {}
            override = t["settings_override"] or {}
            merged_config = {**base_config, **override}

            active_tools.append(
                {
                    "integration_id": t["integration_id"],
                    "provider": t["provider"],
                    "name": t["name"],
                    "config": merged_config,
                    "credentials": t["credentials"],
                }
            )

        # ============================================================
        # STEP 1F: FETCH CHAT HISTORY
        # ============================================================
        history_query = """
            SELECT role, content, tool_calls, tool_results, created_at
            FROM messages 
            WHERE contact_id = %s 
            ORDER BY created_at DESC 
            LIMIT 20
        """
        cur.execute(history_query, (contact["id"],))
        history_rows = cur.fetchall()

        # Reverse to chronological order
        history = [dict(row) for row in reversed(history_rows)]

        # ============================================================
        # RETURN CONTEXT PAYLOAD
        # ============================================================
        return {
            "proceed": True,
            "webhook_event_id": webhook_event_id,
            "chatbot": {
                "id": chatbot_id,
                "organization_id": org_id,
                "name": bot["name"],
                "system_prompt": bot["system_prompt"],
                "persona": bot["persona"],
                "model_name": bot["model_name"],
                "temperature": float(bot["temperature"]) if bot["temperature"] else 0.7,
                "wa_token": bot["whatsapp_access_token"],
                "rag_config": {
                    "enabled": bot["rag_enabled"],
                },
            },
            "user": {
                "id": contact["id"],
                "phone": user_phone,
                "name": user_name,
                "variables": contact["variables"] or {},
                "tags": contact["tags"] or [],
            },
            "history": history,
            "tools": active_tools,
            "usage_info": usage_check_result,
        }

    except Exception as e:
        print(f"Error in context loading: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals():
            conn.close()


def _check_usage_limits(
    cur,
    org_id: str,
    message_limit: int,
    token_limit: int,
    period_start,
    period_end
) -> Dict[str, Any]:
    """
    Check if organization has remaining quota.
    
    Returns:
        {
            "has_quota": bool,
            "messages_used": int,
            "tokens_used": int,
            "messages_remaining": int,
            "tokens_remaining": int,
            "limit_type": str or None  # "messages" or "tokens" if exceeded
        }
    """
    
    # Get current usage using the database function
    usage_query = "SELECT * FROM get_current_usage(%s)"
    cur.execute(usage_query, (org_id,))
    usage = cur.fetchone()
    
    messages_used = usage["messages_used"]
    tokens_used = usage["tokens_used"]
    
    messages_remaining = message_limit - messages_used
    tokens_remaining = token_limit - tokens_used
    
    # Check if limits exceeded
    has_quota = True
    limit_type = None
    
    if messages_used >= message_limit:
        has_quota = False
        limit_type = "messages"
    elif tokens_used >= token_limit:
        has_quota = False
        limit_type = "tokens"
    
    return {
        "has_quota": has_quota,
        "messages_used": messages_used,
        "tokens_used": tokens_used,
        "messages_remaining": max(0, messages_remaining),
        "tokens_remaining": max(0, tokens_remaining),
        "message_limit": message_limit,
        "token_limit": token_limit,
        "limit_type": limit_type,
        "period_start": str(period_start),
        "period_end": str(period_end),
    }


def _mark_webhook_failed(cur, webhook_event_id: int, error_message: str):
    """Mark webhook event as failed"""
    cur.execute(
        """
        UPDATE webhook_events 
        SET status = 'failed', 
            error_message = %s,
            processed_at = NOW()
        WHERE id = %s
        """,
        (error_message, webhook_event_id)
    )


def _mark_webhook_completed(cur, webhook_event_id: int):
    """Mark webhook event as completed"""
    cur.execute(
        """
        UPDATE webhook_events 
        SET status = 'completed',
            processed_at = NOW()
        WHERE id = %s
        """,
        (webhook_event_id,)
    )