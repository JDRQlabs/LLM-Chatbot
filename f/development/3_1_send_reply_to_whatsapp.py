import requests
import json

def main(
    phone_number_id: str,  # Map from Flow Input
    context_payload: dict,  # From Step 1
    llm_result: dict,  # From Step 2
):
    token = context_payload["chatbot"]["wa_token"]
    to_phone = str(context_payload["user"]["phone"]).replace("+", "").strip()
    text_body = llm_result.get("reply_text")

    if not text_body:
        print("No text to send.")
        return {"success": False}

    # Ensure phone_number_id is a string and stripped of whitespace
    url = f"https://graph.facebook.com/v22.0/{str(phone_number_id).strip()}/messages"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    data = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text_body},
    }

    print("--- Request Debug ---")
    print(f"POST URL: {url}")
    print(f"Headers: {{'Authorization': 'Bearer {token[:10]}...', 'Content-Type': 'application/json'}}")
    print(f"Payload: {json.dumps(data, indent=2)}")
    print("---------------------")

    try:
        response = requests.post(url, headers=headers, json=data)
        
        if not response.ok:
            print(f"Meta API Error Response ({response.status_code}):")
            print(response.text)
            
        response.raise_for_status()
        return {"success": True, "meta_response": response.json()}
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return {"success": False, "error": str(e)}
