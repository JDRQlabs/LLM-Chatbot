import wmill
import psycopg2
from psycopg2.extras import RealDictCursor


def main(
    whatsapp_phone_id: str,
    user_phone: str,
    user_name: str = "Unknown",
    # Make sure this matches your actual resource path in Windmill
    db_resource: str = "f/development/business_layer_db_postgreSQL",
):
    # 1. SETUP DATABASE CONNECTION
    # Fetch credentials from Windmill Resource
    raw_config = wmill.get_resource(db_resource)
    print(f"raw_config: {raw_config}")

    # Explicitly map only the keys psycopg2 understands
    # This filters out 'root_certificate_pem' and other Windmill-specific UI fields
    db_params = {
        "host": raw_config.get("host"),
        "port": raw_config.get("port"),
        "user": raw_config.get("user"),
        "password": raw_config.get("password"),
        "dbname": raw_config.get("dbname"),
        "sslmode": "disable",  # Since we are in internal Docker network
    }

    # Connect
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        # Helpful error printing
        print(
            f"Connection params used: host={db_params.get('host')} db={db_params.get('dbname')}"
        )
        print(f"db_params: {db_params}")
        return {"proceed": False, "reason": f"DB Connection Failed: {str(e)}"}

    try:
        # 2. FETCH CHATBOT SETTINGS
        bot_query = """
            SELECT 
                id, 
                organization_id,
                name,
                system_prompt, 
                persona,
                model_name,
                pinecone_index_name,
                pinecone_namespace,
                whatsapp_access_token
            FROM chatbots 
            WHERE whatsapp_phone_number_id = %s
        """
        cur.execute(bot_query, (whatsapp_phone_id,))
        bot = cur.fetchone()

        if not bot:
            print(f"No chatbot found for WhatsApp ID: {whatsapp_phone_id}")
            return {"proceed": False, "reason": "Chatbot not found"}

        chatbot_id = bot["id"]

        # 3. UPSERT CONTACT (The User)
        contact_upsert = """
            INSERT INTO contacts (chatbot_id, phone_number, name, last_message_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (chatbot_id, phone_number) 
            DO UPDATE SET 
                name = EXCLUDED.name, 
                last_message_at = NOW()
            RETURNING id, conversation_mode, variables
        """
        cur.execute(contact_upsert, (chatbot_id, user_phone, user_name))
        contact = cur.fetchone()

        conn.commit()

        # CHECK HUMAN TAKEOVER
        if contact["conversation_mode"] == "manual":
            print(f"User {user_phone} is in MANUAL mode.")
            return {"proceed": False, "reason": "Manual Mode"}

        # 4. FETCH ACTIVE TOOLS
        tools_query = """
            SELECT 
                oi.provider, 
                oi.name, 
                oi.config, 
                oi.credentials,
                ci.settings_override
            FROM chatbot_integrations ci
            JOIN org_integrations oi ON ci.integration_id = oi.id
            WHERE ci.chatbot_id = %s AND ci.is_enabled = TRUE
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
                    "provider": t["provider"],
                    "name": t["name"],
                    "config": merged_config,
                    "credentials": t["credentials"],
                }
            )

        # 5. FETCH CHAT HISTORY
        history_query = """
            SELECT role, content, tool_calls
            FROM messages 
            WHERE contact_id = %s 
            ORDER BY created_at DESC 
            LIMIT 10
        """
        cur.execute(history_query, (contact["id"],))
        history_rows = cur.fetchall()

        history = [dict(row) for row in reversed(history_rows)]

        return {
            "proceed": True,
            "chatbot": {
                "id": chatbot_id,
                "name": bot["name"],
                "system_prompt": bot["system_prompt"],
                "persona": bot["persona"],
                "model_name": bot["model_name"],
                "wa_token": bot["whatsapp_access_token"],
                "pinecone_config": {
                    "index": bot["pinecone_index_name"],
                    "namespace": bot["pinecone_namespace"],
                },
            },
            "user": {
                "id": contact["id"],
                "phone": user_phone,
                "name": user_name,
                "variables": contact["variables"] or {},
            },
            "history": history,
            "tools": active_tools,
        }

    except Exception as e:
        print(f"Error executing logic: {e}")
        conn.rollback()
        raise e
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals():
            conn.close()
