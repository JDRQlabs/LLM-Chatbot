import wmill
import psycopg2
from psycopg2.extras import RealDictCursor


def main(
    context_payload: dict,  # From Step 1 (contains User ID)
    user_message: str,  # Flow Input (The original message)
    llm_result: dict,  # From Step 2 (The AI reply)
    db_resource: str = "f/development/business_layer_db_postgreSQL",
):
    """
    Step 4: Persist Conversation to DB
    """

    contact_id = context_payload["user"]["id"]
    ai_text = llm_result.get("reply_text")

    # Setup DB
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
        cur = conn.cursor()

        # 1. Insert USER Message
        # We assume this flow ran successfully, so we record the user's input now.
        # (Alternatively, you could record this at Step 1, but doing it batch here is easier for MVP)
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
        # This updates the 'variables' JSONB column merging new data
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
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals():
            conn.close()
