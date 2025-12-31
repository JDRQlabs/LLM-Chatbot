import wmill  # Required for get_db_connection to access Windmill resources
import json
from f.development.utils.db_utils import get_db_connection
from f.development.utils.flow_utils import check_previous_steps


def main(
    context_payload: dict,  # From Step 1 (contains User ID)
    user_message: str,  # Flow Input (The original message)
    llm_result: dict,  # From Step 2 (The AI reply)
    send_result: dict,  # From Step 3 (Meta API response)
    db_resource: str = "f/development/business_layer_db_postgreSQL",
):
    """
    Step 4: Persist Conversation to DB
    ONLY executes if Meta API successfully delivered the message
    """

    # Check if previous steps succeeded
    step_error = check_previous_steps(context_payload, llm_result, send_result)
    if step_error:
        print("Skipping chat history save")
        return step_error

    contact_id = context_payload["user"]["id"]
    ai_text = llm_result.get("reply_text")

    try:
        with get_db_connection(db_resource, use_dict_cursor=False) as (conn, cur):
            # 1. Insert USER Message
            cur.execute(
                """
                INSERT INTO messages (contact_id, role, content, created_at)
                VALUES (%s, 'user', %s, NOW())
                """,
                (contact_id, user_message),
            )

            # 2. Insert ASSISTANT Message
            if ai_text:
                cur.execute(
                    """
                    INSERT INTO messages (contact_id, role, content, created_at)
                    VALUES (%s, 'assistant', %s, NOW())
                    """,
                    (contact_id, ai_text),
                )

            # 3. Update User Variables (If LLM extracted new info)
            new_vars = llm_result.get("updated_variables")
            if new_vars:
                cur.execute(
                    """
                    UPDATE contacts
                    SET variables = variables || %s
                    WHERE id = %s
                    """,
                    (json.dumps(new_vars), contact_id),
                )

            conn.commit()
            return {"success": True}

    except Exception as e:
        print(f"DB Error: {e}")
        return {"success": False, "error": str(e)}
