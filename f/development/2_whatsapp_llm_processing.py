import wmill
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
import google.generativeai as genai
from typing import Dict, Any, List, Optional


def main(
    context_payload: dict,
    user_message: str,
    openai_api_key: str = "",
    google_api_key: str = wmill.get_variable("u/admin/GoogleAPI_JD"),
    default_provider: str = "google",
    db_resource: str = "f/development/business_layer_db_postgreSQL",
):
    """
    Step 2: AI Reasoning with RAG (The Brain)
    
    Flow:
    1. Check if RAG is enabled for this chatbot
    2. If RAG enabled: Retrieve relevant context from knowledge base
    3. Build enhanced prompt with context
    4. Call LLM
    5. Return response with usage info
    """

    # Unpack context
    chatbot = context_payload["chatbot"]
    user = context_payload["user"]
    history = context_payload["history"]
    tools = context_payload["tools"]
    
    # Determine provider
    provider = default_provider
    if "gemini" in chatbot.get("model_name", "").lower():
        provider = "google"
    elif "gpt" in chatbot.get("model_name", "").lower():
        provider = "openai"

    # Base system prompt
    base_prompt = chatbot.get("system_prompt", "You are a helpful assistant.")
    persona = chatbot.get("persona", "")
    
    # Inject user context
    user_context_str = (
        f"\n\nUser Context:\nName: {user.get('name')}\nPhone: {user.get('phone')}"
    )
    if user.get("variables"):
        user_context_str += f"\nKnown Info: {json.dumps(user['variables'])}"
    
    # =========================================================================
    # RAG RETRIEVAL
    # =========================================================================
    rag_context = ""
    retrieved_chunks = []
    
    if chatbot.get("rag_config", {}).get("enabled"):
        print("RAG is enabled, retrieving relevant context...")
        
        retrieved_chunks = retrieve_knowledge(
            chatbot_id=chatbot["id"],
            query=user_message,
            openai_api_key=openai_api_key,
            db_resource=db_resource,
            top_k=5,
            similarity_threshold=0.7
        )
        
        if retrieved_chunks:
            print(f"Retrieved {len(retrieved_chunks)} relevant chunks")
            
            # Format context for prompt
            rag_context = "\n\n=== KNOWLEDGE BASE CONTEXT ===\n"
            rag_context += "Use the following information to answer the user's question. "
            rag_context += "Only use this information if it's relevant to the query.\n\n"
            
            for i, chunk in enumerate(retrieved_chunks, 1):
                source_info = f"[Source: {chunk['source_name']}"
                if chunk.get("metadata", {}).get("page"):
                    source_info += f", Page {chunk['metadata']['page']}"
                source_info += f", Relevance: {chunk['similarity']:.0%}]"
                
                rag_context += f"{i}. {source_info}\n{chunk['content']}\n\n"
            
            rag_context += "=== END KNOWLEDGE BASE CONTEXT ===\n"
    
    # Build full system prompt
    full_system_prompt = f"{base_prompt}\n{persona}\n{user_context_str}"
    if rag_context:
        full_system_prompt += f"\n{rag_context}"
    
    # =========================================================================
    # STUB: MCP / TOOLS
    # =========================================================================
    # TODO: Implement tool calling
    # For now, tools are loaded but not used
    
    reply_text = ""
    updated_variables = {}
    usage_info = {}

    try:
        if provider == "openai":
            if not openai_api_key:
                return {"error": "Missing OpenAI API Key"}

            model_name = chatbot.get("model_name", "gpt-4o")
            print(f"Using OpenAI with model: {model_name}")

            client = OpenAI(api_key=openai_api_key)

            # Format Messages
            messages = [{"role": "system", "content": full_system_prompt}]

            # Add History
            for msg in history:
                if msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Add Current User Message
            messages.append({"role": "user", "content": user_message})

            print(f"Calling OpenAI with {len(messages)} messages (RAG: {bool(rag_context)})")
            
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=chatbot.get("temperature", 0.7),
            )

            reply_text = response.choices[0].message.content
            
            # Extract usage info
            usage_info = {
                "provider": "openai",
                "model": model_name,
                "tokens_input": response.usage.prompt_tokens,
                "tokens_output": response.usage.completion_tokens,
                "rag_used": bool(rag_context),
                "chunks_retrieved": len(retrieved_chunks),
            }

        elif provider == "google":
            if not google_api_key:
                return {"error": "Missing Google API Key"}

            model_name = chatbot.get("model_name", "gemini-pro")
            print(f"Using Google with model: {model_name}")

            genai.configure(api_key=google_api_key)
            model = genai.GenerativeModel(model_name)

            # Format Messages for Gemini
            chat_history = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                if msg.get("content"):
                    chat_history.append({"role": role, "parts": [msg["content"]]})

            # Start Chat Session
            chat = model.start_chat(history=chat_history)

            # Combine system prompt + user message
            final_input = f"{full_system_prompt}\n\nUser Message: {user_message}"
            
            print(f"Calling Google Gemini (RAG: {bool(rag_context)})")
            
            response = chat.send_message(final_input)
            reply_text = response.text
            
            # Extract usage info (Gemini provides this in usage_metadata)
            usage_metadata = getattr(response, 'usage_metadata', None)
            if usage_metadata:
                usage_info = {
                    "provider": "google",
                    "model": model_name,
                    "tokens_input": usage_metadata.prompt_token_count,
                    "tokens_output": usage_metadata.candidates_token_count,
                    "rag_used": bool(rag_context),
                    "chunks_retrieved": len(retrieved_chunks),
                }
            else:
                # Fallback if metadata not available
                usage_info = {
                    "provider": "google",
                    "model": model_name,
                    "tokens_input": estimate_tokens(final_input),
                    "tokens_output": estimate_tokens(reply_text),
                    "rag_used": bool(rag_context),
                    "chunks_retrieved": len(retrieved_chunks),
                }

        else:
            return {"error": f"Unknown provider: {provider}"}

    except Exception as e:
        print(f"LLM Error: {e}")
        reply_text = "I'm having trouble thinking right now. Please try again later."
        usage_info = {
            "provider": provider,
            "model": chatbot.get("model_name"),
            "error": str(e),
        }

    return {
        "reply_text": reply_text,
        "updated_variables": updated_variables,
        "usage_info": usage_info,
        "retrieved_sources": [
            {
                "source_name": chunk["source_name"],
                "similarity": chunk["similarity"],
                "metadata": chunk.get("metadata", {}),
            }
            for chunk in retrieved_chunks
        ] if retrieved_chunks else [],
    }


def retrieve_knowledge(
    chatbot_id: str,
    query: str,
    openai_api_key: str,
    db_resource: str,
    top_k: int = 5,
    similarity_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant knowledge from the vector database.
    
    Args:
        chatbot_id: ID of the chatbot
        query: User's query
        openai_api_key: OpenAI API key for embeddings
        db_resource: Database resource path
        top_k: Number of chunks to retrieve
        similarity_threshold: Minimum similarity score (0-1)
    
    Returns:
        List of relevant chunks with content and metadata
    """
    if not openai_api_key:
        print("No OpenAI API key provided, skipping RAG")
        return []
    
    try:
        # 1. Generate embedding for the query
        client = OpenAI(api_key=openai_api_key)
        
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=query
        )
        
        query_embedding = response.data[0].embedding
        
        # 2. Search vector database
        raw_config = wmill.get_resource(db_resource)
        db_params = {
            "host": raw_config.get("host"),
            "port": raw_config.get("port"),
            "user": raw_config.get("user"),
            "password": raw_config.get("password"),
            "dbname": raw_config.get("dbname"),
            "sslmode": "disable",
        }
        
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Use the search function we created
        cur.execute(
            "SELECT * FROM search_knowledge_base(%s, %s, %s, %s)",
            (chatbot_id, query_embedding, top_k, similarity_threshold)
        )
        
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return [dict(row) for row in results]
        
    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return []


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token.
    Used as fallback when actual token counts aren't available.
    """
    return max(len(text) // 4, 1)