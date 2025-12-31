import wmill
import os
import json
from openai import OpenAI
from google import genai
from google.genai import types
from typing import Dict, Any, List, Optional
from f.development.utils.db_utils import get_db_connection
from f.development.utils.flow_utils import estimate_tokens


def build_tool_instructions(tools: List[Dict]) -> str:
    """
    Auto-generate tool usage instructions from tool configs.
    Each MCP provides its own llm_instructions that get injected into the system prompt.
    """
    if not tools:
        return ""

    instructions = "\n\n=== HERRAMIENTAS DISPONIBLES ===\n"
    instructions += "Tienes acceso a las siguientes herramientas. Úsalas cuando sea apropiado:\n\n"

    for tool in tools:
        config = tool.get("config", {})
        tool_name = tool.get("name")
        description = config.get("description", "")
        llm_instructions = config.get("llm_instructions", "")

        instructions += f"• {tool_name}: {description}\n"
        if llm_instructions:
            instructions += f"  CUÁNDO USAR: {llm_instructions}\n"
        instructions += "\n"

    return instructions


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

    # Check if Step 1 succeeded
    if not context_payload.get("proceed", False):
        error_reason = context_payload.get("reason", "Unknown error in Step 1")
        print(f"Step 1 failed: {error_reason}")
        return {
            "error": error_reason,
            "reply_text": "Sorry, I'm unable to process your message at this time. Please try again later.",
            "should_notify_admin": context_payload.get("notify_admin", False)
        }

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

    # AUTO-INJECT tool instructions from MCP configs
    tool_instructions = build_tool_instructions(tools)
    if tool_instructions:
        full_system_prompt += tool_instructions

    # =========================================================================
    # AGENT LOOP: Tool Calling & Multi-Step Reasoning
    # =========================================================================
    # If tools are available, use agent loop for multi-step reasoning
    # Otherwise, fall back to simple LLM call

    reply_text = ""
    updated_variables = {}
    usage_info = {}
    tool_executions = []

    # Prepare tool definitions for LLM
    tool_definitions = prepare_tool_definitions(tools, chatbot["id"])

    # Add built-in RAG search tool if RAG is enabled
    if chatbot.get("rag_config", {}).get("enabled"):
        tool_definitions.append({
            "type": "function",
            "function": {
                "name": "search_knowledge_base",
                "description": "Search the chatbot's knowledge base for relevant information to answer user questions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant information"
                        }
                    },
                    "required": ["query"]
                }
            }
        })

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

            # Use agent loop if tools are available
            if tool_definitions:
                print(f"Agent loop enabled with {len(tool_definitions)} tools")
                result = execute_agent_loop_openai(
                    client=client,
                    model_name=model_name,
                    messages=messages,
                    tools=tool_definitions,
                    chatbot_id=chatbot["id"],
                    temperature=chatbot.get("temperature", 0.7),
                    openai_api_key=openai_api_key,
                    db_resource=db_resource,
                    max_iterations=5
                )
                reply_text = result["reply_text"]
                tool_executions = result["tool_executions"]
                usage_info = result["usage_info"]
                usage_info["rag_used"] = bool(rag_context)
                usage_info["chunks_retrieved"] = len(retrieved_chunks)
            else:
                # Simple LLM call without tools
                print(f"Calling OpenAI without tools (RAG: {bool(rag_context)})")

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

            model_name = chatbot.get("model_name", "gemini-3-flash-preview")
            print(f"Using Google with model: {model_name}")

            client = genai.Client(api_key=google_api_key)

            # Format Messages for Gemini (new SDK uses different format)
            chat_history = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                if msg.get("content"):
                    chat_history.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

            # Use agent loop if tools are available
            if tool_definitions:
                print(f"Gemini agent loop enabled with {len(tool_definitions)} tools")
                result = execute_agent_loop_gemini(
                    client=client,
                    model_name=model_name,
                    system_prompt=full_system_prompt,
                    user_message=user_message,
                    chat_history=chat_history,
                    tools=tool_definitions,
                    chatbot_id=chatbot["id"],
                    temperature=chatbot.get("temperature", 0.7),
                    google_api_key=google_api_key,
                    db_resource=db_resource,
                    fallback_message_error=chatbot.get("fallback_message_error", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo más tarde."),
                    fallback_message_limit=chatbot.get("fallback_message_limit", "Lo siento, he alcanzado mi límite de uso. El administrador ha sido notificado."),
                    max_iterations=5
                )
                reply_text = result["reply_text"]
                tool_executions = result["tool_executions"]
                usage_info = result["usage_info"]
                usage_info["rag_used"] = bool(rag_context)
                usage_info["chunks_retrieved"] = len(retrieved_chunks)
            else:
                # Simple LLM call without tools
                print(f"Calling Google Gemini without tools (RAG: {bool(rag_context)})")

                # Combine system prompt + user message
                final_input = f"{full_system_prompt}\n\nUser Message: {user_message}"

                # Add current message to history
                messages = chat_history + [types.Content(role="user", parts=[types.Part(text=final_input)])]

                # Call Gemini with new SDK
                response = client.models.generate_content(
                    model=model_name,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        temperature=chatbot.get("temperature", 0.7)
                    )
                )

                reply_text = response.text

                # Extract usage info (new SDK structure)
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
        error_str = str(e).lower()

        # Determine if this is a quota/limit error
        is_limit_error = any(keyword in error_str for keyword in ['quota', 'limit', 'rate', 'exhausted', '429'])

        # Use appropriate fallback message
        if is_limit_error:
            reply_text = chatbot.get("fallback_message_limit", "Lo siento, he alcanzado mi límite de uso. El administrador ha sido notificado.")
        else:
            reply_text = chatbot.get("fallback_message_error", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo más tarde.")

        usage_info = {
            "provider": provider,
            "model": chatbot.get("model_name"),
            "error": str(e),
            "is_limit_error": is_limit_error,
        }

    return {
        "reply_text": reply_text,
        "updated_variables": updated_variables,
        "usage_info": usage_info,
        "tool_executions": tool_executions,
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
        with get_db_connection(db_resource) as (conn, cur):
            # Use the search function we created
            cur.execute(
                "SELECT * FROM search_knowledge_base(%s::uuid, %s::vector(1536), %s, %s)",
                (chatbot_id, query_embedding, top_k, similarity_threshold)
            )

            results = cur.fetchall()
            return [dict(row) for row in results]

    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return []


def sanitize_gemini_parameters(params: dict) -> dict:
    """
    Clean up JSON Schema parameters for Gemini API compatibility.

    Gemini's function calling only accepts standard JSON Schema fields.
    Fields like 'additional_properties', 'additionalProperties', etc.
    that may come from Pydantic models or other sources must be removed.

    Args:
        params: Original parameters dict

    Returns:
        Cleaned parameters dict safe for Gemini API
    """
    if not params or not isinstance(params, dict):
        return {"type": "object", "properties": {}}

    # Fields that are valid in JSON Schema for Gemini
    valid_fields = {
        "type", "properties", "required", "description",
        "enum", "items", "minimum", "maximum", "minLength",
        "maxLength", "pattern", "format", "default"
    }

    def clean_dict(d: dict) -> dict:
        if not isinstance(d, dict):
            return d

        cleaned = {}
        for key, value in d.items():
            # Skip invalid fields at any level
            if key.lower().replace("_", "") in {"additionalproperties", "additionalitems"}:
                continue
            if key not in valid_fields and key != "properties":
                # For non-standard fields at root level, skip them
                # But keep 'properties' as it contains nested schemas
                if isinstance(value, dict) and "type" in value:
                    # This looks like a property definition, keep it
                    cleaned[key] = clean_dict(value)
                elif key in valid_fields:
                    cleaned[key] = value if not isinstance(value, dict) else clean_dict(value)
                continue

            if isinstance(value, dict):
                cleaned[key] = clean_dict(value)
            elif isinstance(value, list):
                cleaned[key] = [clean_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                cleaned[key] = value

        return cleaned

    result = clean_dict(params)

    # Ensure minimum required structure
    if "type" not in result:
        result["type"] = "object"
    if "properties" not in result:
        result["properties"] = {}

    return result


# =========================================================================
# AGENT LOOP IMPLEMENTATION
# =========================================================================

def prepare_tool_definitions(tools: List[Dict], chatbot_id: str) -> List[Dict]:
    """
    Convert tool records from database into OpenAI function calling format.

    Args:
        tools: List of tool records from chatbot_integrations table
        chatbot_id: ID of the chatbot

    Returns:
        List of tool definitions in OpenAI format
    """
    tool_defs = []

    for tool in tools:
        # Skip disabled tools
        if not tool.get("enabled", True):
            continue

        # Format depends on tool type
        tool_type = tool.get("provider", "custom")

        if tool_type == "mcp":
            # MCP tools from external servers
            # Extract description and parameters from config
            config = tool.get("config", {})
            tool_defs.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", "unknown_tool"),
                    "description": config.get("description", ""),
                    "parameters": config.get("parameters", {
                        "type": "object",
                        "properties": {}
                    })
                },
                "_metadata": {
                    "tool_type": "mcp",
                    "mcp_server_url": config.get("server_url"),
                    "integration_id": tool.get("integration_id")
                }
            })

        elif tool_type == "windmill":
            # Windmill script tools
            tool_defs.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", "unknown_tool"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {
                        "type": "object",
                        "properties": {}
                    })
                },
                "_metadata": {
                    "tool_type": "windmill",
                    "script_path": tool.get("settings", {}).get("script_path"),
                    "integration_id": tool.get("id")
                }
            })

    return tool_defs


def execute_agent_loop_openai(
    client: OpenAI,
    model_name: str,
    messages: List[Dict],
    tools: List[Dict],
    chatbot_id: str,
    temperature: float,
    openai_api_key: str,
    db_resource: str,
    max_iterations: int = 5
) -> Dict[str, Any]:
    """
    Execute agent loop with tool calling for OpenAI.

    The agent iteratively:
    1. Calls LLM with tool definitions
    2. If LLM wants to use a tool, execute it
    3. Feed result back to LLM
    4. Repeat until LLM returns final answer or max iterations reached

    Args:
        client: OpenAI client
        model_name: Model to use
        messages: Conversation messages
        tools: Tool definitions
        chatbot_id: ID of chatbot
        temperature: Sampling temperature
        openai_api_key: API key for embeddings
        db_resource: Database resource path
        max_iterations: Maximum tool call iterations

    Returns:
        Dict with reply_text, tool_executions, and usage_info
    """
    iteration = 0
    tool_executions = []
    total_tokens_input = 0
    total_tokens_output = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"Agent iteration {iteration}/{max_iterations}")

        # Call LLM with tools
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",  # Let model decide when to use tools
                temperature=temperature
            )

            # Track token usage
            total_tokens_input += response.usage.prompt_tokens
            total_tokens_output += response.usage.completion_tokens

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            # Check if model wants to call a tool
            if finish_reason == "tool_calls" and choice.message.tool_calls:
                print(f"LLM requested {len(choice.message.tool_calls)} tool calls")

                # Add assistant message with tool calls
                messages.append(choice.message)

                # Execute each tool call
                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    print(f"Executing tool: {tool_name} with args: {tool_args}")

                    # Execute the tool
                    tool_result = execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        tools=tools,
                        chatbot_id=chatbot_id,
                        openai_api_key=openai_api_key,
                        db_resource=db_resource
                    )

                    # Track execution
                    tool_executions.append({
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "result": tool_result,
                        "status": "success" if not tool_result.get("error") else "failed",
                        "iteration": iteration
                    })

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(tool_result)
                    })

                # Continue loop to get next LLM response
                continue

            elif finish_reason == "stop":
                # Model returned final answer
                reply_text = choice.message.content

                return {
                    "reply_text": reply_text,
                    "tool_executions": tool_executions,
                    "usage_info": {
                        "provider": "openai",
                        "model": model_name,
                        "tokens_input": total_tokens_input,
                        "tokens_output": total_tokens_output,
                        "tool_calls": len(tool_executions),
                        "iterations": iteration
                    }
                }

            else:
                # Unexpected finish reason
                print(f"Unexpected finish_reason: {finish_reason}")
                reply_text = choice.message.content or "I encountered an issue processing your request."

                return {
                    "reply_text": reply_text,
                    "tool_executions": tool_executions,
                    "usage_info": {
                        "provider": "openai",
                        "model": model_name,
                        "tokens_input": total_tokens_input,
                        "tokens_output": total_tokens_output,
                        "tool_calls": len(tool_executions),
                        "iterations": iteration,
                        "finish_reason": finish_reason
                    }
                }

        except Exception as e:
            print(f"Agent loop error: {e}")
            return {
                "reply_text": "I encountered an error while processing your request.",
                "tool_executions": tool_executions,
                "usage_info": {
                    "provider": "openai",
                    "model": model_name,
                    "tokens_input": total_tokens_input,
                    "tokens_output": total_tokens_output,
                    "tool_calls": len(tool_executions),
                    "iterations": iteration,
                    "error": str(e)
                }
            }

    # Max iterations reached
    print(f"Max iterations ({max_iterations}) reached")
    return {
        "reply_text": "I need more time to think about this. Could you please rephrase your question?",
        "tool_executions": tool_executions,
        "usage_info": {
            "provider": "openai",
            "model": model_name,
            "tokens_input": total_tokens_input,
            "tokens_output": total_tokens_output,
            "tool_calls": len(tool_executions),
            "iterations": iteration,
            "max_iterations_reached": True
        }
    }


def execute_agent_loop_gemini(
    client: Any,
    model_name: str,
    system_prompt: str,
    user_message: str,
    chat_history: List[Any],
    tools: List[Dict],
    chatbot_id: str,
    temperature: float,
    google_api_key: str,
    db_resource: str,
    fallback_message_error: str,
    fallback_message_limit: str,
    max_iterations: int = 5
) -> Dict[str, Any]:
    """
    Execute agent loop with tool calling for Google Gemini using new SDK.

    Args:
        client: Gemini Client instance (new SDK)
        model_name: Model name (e.g., "gemini-3-flash-preview")
        system_prompt: System prompt
        user_message: Current user message
        chat_history: Conversation history as list of types.Content
        tools: Tool definitions
        chatbot_id: ID of chatbot
        temperature: Sampling temperature
        google_api_key: API key for embeddings
        db_resource: Database resource path
        max_iterations: Maximum tool call iterations

    Returns:
        Dict with reply_text, tool_executions, and usage_info
    """
    iteration = 0
    tool_executions = []
    total_tokens_input = 0
    total_tokens_output = 0

    # Convert tool definitions to Gemini function declarations format (new SDK)
    function_declarations = []
    for tool in tools:
        if "function" in tool:
            func = tool["function"]
            # Sanitize parameters to remove non-standard JSON Schema fields
            clean_params = sanitize_gemini_parameters(func.get("parameters", {}))
            function_declarations.append(
                types.FunctionDeclaration(
                    name=func["name"],
                    description=func.get("description", ""),
                    parameters=clean_params
                )
            )

    # Create tool config (new SDK)
    tool_config = None
    if function_declarations:
        tool_config = types.Tool(function_declarations=function_declarations)

    # Build message history - start with system prompt + user message
    first_message = f"{system_prompt}\n\nUser Message: {user_message}"
    messages = chat_history + [types.Content(role="user", parts=[types.Part(text=first_message)])]

    while iteration < max_iterations:
        iteration += 1
        print(f"Gemini agent iteration {iteration}/{max_iterations}")

        try:
            # Call Gemini with tools (new SDK)
            config_params = {
                "temperature": temperature
            }
            if tool_config:
                config_params["tools"] = [tool_config]

            response = client.models.generate_content(
                model=model_name,
                contents=messages,
                config=types.GenerateContentConfig(**config_params)
            )

            # Track token usage
            usage_metadata = getattr(response, 'usage_metadata', None)
            if usage_metadata:
                total_tokens_input += usage_metadata.prompt_token_count
                total_tokens_output += usage_metadata.candidates_token_count

            # Check if model wants to call functions
            candidate = response.candidates[0]
            parts = candidate.content.parts

            # Check for function calls in parts
            function_calls = [part for part in parts if hasattr(part, 'function_call') and part.function_call]

            if function_calls:
                print(f"Gemini requested {len(function_calls)} function calls")

                # Add assistant message with function calls to history
                messages.append(candidate.content)

                # Execute each function call
                function_response_parts = []
                for part in function_calls:
                    fc = part.function_call
                    tool_name = fc.name

                    # Convert function call args to dict (new SDK)
                    tool_args = {}
                    if hasattr(fc, 'args') and fc.args:
                        # fc.args is a dict-like object in new SDK
                        tool_args = dict(fc.args)

                    print(f"Executing tool: {tool_name} with args: {tool_args}")

                    # Execute the tool
                    tool_result = execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        tools=tools,
                        chatbot_id=chatbot_id,
                        openai_api_key=google_api_key,  # Used for RAG embeddings
                        db_resource=db_resource
                    )

                    # Track execution
                    tool_executions.append({
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "result": tool_result,
                        "status": "success" if not tool_result.get("error") else "failed",
                        "iteration": iteration
                    })

                    # Create function response (new SDK)
                    function_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response=tool_result
                            )
                        )
                    )

                # Add function responses to messages
                messages.append(
                    types.Content(
                        role="function",
                        parts=function_response_parts
                    )
                )

                # Continue loop to get next response
                continue

            # No function calls - this is the final response
            reply_text = response.text
            print(f"Gemini returned final answer after {iteration} iterations")

            return {
                "reply_text": reply_text,
                "tool_executions": tool_executions,
                "usage_info": {
                    "provider": "google",
                    "model": model_name,
                    "tokens_input": total_tokens_input,
                    "tokens_output": total_tokens_output,
                    "tool_calls": len(tool_executions),
                    "iterations": iteration
                }
            }

        except Exception as e:
            import traceback
            print(f"Gemini agent loop error: {e}")
            print(f"Traceback: {traceback.format_exc()}")

            # Determine if this is a quota/limit error
            error_str = str(e).lower()
            is_limit_error = any(keyword in error_str for keyword in ['quota', 'limit', 'rate', 'exhausted', '429'])

            # Use appropriate fallback message
            reply_text = fallback_message_limit if is_limit_error else fallback_message_error

            return {
                "reply_text": reply_text,
                "tool_executions": tool_executions,
                "usage_info": {
                    "provider": "google",
                    "model": model_name,
                    "tokens_input": total_tokens_input,
                    "tokens_output": total_tokens_output,
                    "tool_calls": len(tool_executions),
                    "iterations": iteration,
                    "error": str(e),
                    "is_limit_error": is_limit_error,
                }
            }

    # Max iterations reached
    print(f"Max iterations ({max_iterations}) reached")
    return {
        "reply_text": "Necesito más información para responder. ¿Podrías reformular tu pregunta?",
        "tool_executions": tool_executions,
        "usage_info": {
            "provider": "google",
            "model": model_name,
            "tokens_input": total_tokens_input,
            "tokens_output": total_tokens_output,
            "tool_calls": len(tool_executions),
            "iterations": iteration,
            "max_iterations_reached": True
        }
    }


def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tools: List[Dict],
    chatbot_id: str,
    openai_api_key: str,
    db_resource: str
) -> Dict[str, Any]:
    """
    Execute a single tool call.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments
        tools: List of available tool definitions
        chatbot_id: ID of chatbot
        openai_api_key: API key for OpenAI
        db_resource: Database resource path

    Returns:
        Tool execution result
    """
    # Find tool definition
    tool = next((t for t in tools if t.get("function", {}).get("name") == tool_name), None)

    if not tool:
        # Check if it's a built-in tool
        if tool_name == "search_knowledge_base":
            return execute_rag_search(
                chatbot_id=chatbot_id,
                query=arguments.get("query", ""),
                openai_api_key=openai_api_key,
                db_resource=db_resource
            )

        return {"error": f"Tool '{tool_name}' not found"}

    metadata = tool.get("_metadata", {})
    tool_type = metadata.get("tool_type", "unknown")

    try:
        if tool_type == "mcp":
            # Execute MCP tool via HTTP
            return execute_mcp_tool(tool_name, metadata, arguments, chatbot_id)

        elif tool_type == "windmill":
            # Execute Windmill script
            return execute_windmill_tool(metadata, arguments)

        else:
            return {"error": f"Unknown tool type: {tool_type}"}

    except Exception as e:
        print(f"Tool execution error ({tool_name}): {e}")
        return {"error": str(e)}


def execute_rag_search(
    chatbot_id: str,
    query: str,
    openai_api_key: str,
    db_resource: str
) -> Dict[str, Any]:
    """
    Execute RAG search as a tool.

    Args:
        chatbot_id: ID of chatbot
        query: Search query
        openai_api_key: API key for embeddings
        db_resource: Database resource path

    Returns:
        Search results
    """
    try:
        chunks = retrieve_knowledge(
            chatbot_id=chatbot_id,
            query=query,
            openai_api_key=openai_api_key,
            db_resource=db_resource,
            top_k=5,
            similarity_threshold=0.7
        )

        if not chunks:
            return {
                "success": True,
                "results": [],
                "message": "No relevant information found in knowledge base."
            }

        # Format results for LLM
        formatted_results = []
        for chunk in chunks:
            formatted_results.append({
                "content": chunk["content"],
                "source": chunk["source_name"],
                "relevance": f"{chunk['similarity']:.0%}",
                "metadata": chunk.get("metadata", {})
            })

        return {
            "success": True,
            "results": formatted_results,
            "count": len(formatted_results)
        }

    except Exception as e:
        return {"error": f"RAG search failed: {str(e)}"}


def execute_mcp_tool(tool_name: str, metadata: Dict, arguments: Dict, chatbot_id: str) -> Dict[str, Any]:
    """
    Execute MCP tool by calling external MCP server via HTTP.

    Args:
        tool_name: Name of the tool to execute
        metadata: Tool metadata with MCP server URL
        arguments: Tool arguments from LLM
        chatbot_id: ID of the chatbot (auto-injected for MCP servers that need it)

    Returns:
        Tool result
    """
    import requests

    mcp_server_url = metadata.get("mcp_server_url")
    if not mcp_server_url:
        return {"error": "MCP server URL not configured"}

    # Construct full tool endpoint URL: server_url + /tools/ + tool_name
    # e.g., http://mcp_pricing_calculator:3001/tools/calculate_pricing
    tool_endpoint = f"{mcp_server_url.rstrip('/')}/tools/{tool_name}"

    # Auto-inject chatbot_id into all MCP tool calls
    # Some MCPs (like contact_owner) need it to look up org/notification settings
    payload = {**arguments, "chatbot_id": chatbot_id}

    try:
        # Call MCP server at the specific tool endpoint
        response = requests.post(
            tool_endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30  # 30 second timeout
        )

        response.raise_for_status()
        return response.json()

    except requests.Timeout:
        return {"error": "MCP server timeout (30s)"}
    except requests.RequestException as e:
        return {"error": f"MCP server error: {str(e)}"}


def execute_windmill_tool(metadata: Dict, arguments: Dict) -> Dict[str, Any]:
    """
    Execute Windmill script tool.

    Args:
        metadata: Tool metadata with script path
        arguments: Tool arguments

    Returns:
        Tool result
    """
    script_path = metadata.get("script_path")
    if not script_path:
        return {"error": "Windmill script path not configured"}

    try:
        # Execute Windmill script synchronously
        result = wmill.run_script_by_path(
            path=script_path,
            args=arguments,
            timeout=30  # 30 second timeout
        )

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        return {"error": f"Windmill script execution failed: {str(e)}"}