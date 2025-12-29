import wmill
import os
import json
from openai import OpenAI
import google.generativeai as genai


def main(
    context_payload: dict,
    user_message: str,
    openai_api_key: str = "",  # Map this to variables inside Windmill
    google_api_key: str = wmill.get_variable("u/admin/GoogleAPI_JD"),
    default_provider: str = "google",  # 'openai' or 'google'
):
    """
    Step 2: AI Reasoning (The Brain)
    - Takes context from Step 1.
    - (Stub) Performs RAG Retrieval.
    - (Stub) Selects Tools.
    - Calls LLM (OpenAI or Gemini).
    - Returns final text + metadata updates.
    """

    # 1. UNPACK CONTEXT
    chatbot = context_payload["chatbot"]
    user = context_payload["user"]
    history = context_payload["history"]
    tools = context_payload["tools"]

    # Check which provider to use (Chatbot setting takes precedence, else default)
    # If chatbot['model_name'] starts with "gemini", force google, etc.
    provider = default_provider
    if "gemini" in chatbot.get("model_name", "").lower():
        provider = "google"

    # 2. CONSTRUCT SYSTEM PROMPT
    # We combine the strict System Prompt + Persona + User Context
    base_prompt = chatbot.get("system_prompt", "You are a helpful assistant.")
    persona = chatbot.get("persona", "")

    # Inject user details so the bot knows who it's talking to
    user_context_str = (
        f"\n\nUser Context:\nName: {user.get('name')}\nPhone: {user.get('phone')}"
    )
    if user.get("variables"):
        user_context_str += f"\nKnown Info: {json.dumps(user['variables'])}"

    full_system_prompt = f"{base_prompt}\n{persona}\n{user_context_str}"

    # =========================================================================
    # STUB: RAG RETRIEVAL
    # =========================================================================
    # Implementation Plan:
    # 1. If chatbot['pinecone_config']['index'] is set:
    # 2.   embedding = openai.embeddings.create(input=user_message)
    # 3.   matches = pinecone.query(vector=embedding, namespace=chatbot['pinecone_config']['namespace'])
    # 4.   context_text = "\n".join([m.metadata['text'] for m in matches])
    # 5.   full_system_prompt += f"\n\nRetrieved Context (Use this to answer):\n{context_text}"
    # =========================================================================

    # =========================================================================
    # STUB: MCP / TOOLS
    # =========================================================================
    # Implementation Plan:
    # 1. Convert `tools` list (from Step 1) into OpenAI Tool Schema / Gemini Function Schema.
    # 2. Pass `tools=tool_definitions` to the LLM call.
    # 3. Handle ToolCall response -> Run Tool -> Send back to LLM.
    # =========================================================================

    reply_text = ""
    updated_variables = {}

    try:
        if provider == "openai":
            if not openai_api_key:
                return {"error": "Missing OpenAI API Key"}

            model_name = chatbot.get("model_name", "gpt-4o")
            print(f"Using OpenAI with model: {model_name}")

            client = OpenAI(api_key=openai_api_key)

            # Format Messages for OpenAI
            messages = [{"role": "system", "content": full_system_prompt}]

            # Add History
            for msg in history:
                # Filter out null content or tool calls for now in this basic version
                if msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Add Current User Message
            messages.append({"role": "user", "content": user_message})

            print(f"Full message to OpenAI: {json.dumps(messages, indent=2)}")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
            )

            reply_text = response.choices[0].message.content

        elif provider == "google":
            if not google_api_key:
                return {"error": "Missing Google API Key"}

            model_name = chatbot.get("model_name", "gemini-pro")
            print(f"Using Google with model: {model_name}")

            genai.configure(api_key=google_api_key)
            model = genai.GenerativeModel(model_name)

            # Format Messages for Gemini (requires specific role mapping)
            chat_history = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                if msg.get("content"):
                    chat_history.append({"role": role, "parts": [msg["content"]]})

            # Start Chat Session
            chat = model.start_chat(history=chat_history)

            # Send current message (System prompt is usually sent as first message or instruction in Gemini)
            # For simplicity, prepending context to message here
            final_input = f"System Instructions: {full_system_prompt}\n\nUser Message: {user_message}"
            print(f"Full message to Google: {final_input}")
            response = chat.send_message(final_input)

            reply_text = response.text

        else:
            return {"error": f"Unknown provider: {provider}"}

    except Exception as e:
        print(f"LLM Error: {e}")
        # Fallback message if AI fails
        reply_text = "I'm having trouble thinking right now. Please try again later."

    # =========================================================================
    # STUB: EXTRACTION (Future Feature)
    # =========================================================================
    # Here we could ask the LLM to output JSON to update user variables
    # e.g. updated_variables = {"email": "extracted@email.com"}

    return {
        "reply_text": reply_text,
        "updated_variables": updated_variables,  # To be saved in Step 4
        "usage_info": {"provider": provider, "model": chatbot.get("model_name")},
    }
