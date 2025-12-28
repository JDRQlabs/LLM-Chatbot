import wmill

def main(payload: dict):
    """
    Process WhatsApp webhook notification from Meta.
    
    Extracts message data from the webhook payload and returns structured
    information for the next flow step.
    """
    print(f"Processing WhatsApp webhook: object={payload.get('object')}")
    
    # Initialize result structure
    processed_messages = []
    
    # Process each entry in the webhook payload
    for entry in payload.get("entry", []):
        entry_id = entry.get("id")
        print(f"Processing entry: {entry_id}")
        
        # Process each change in the entry
        for change in entry.get("changes", []):
            value = change.get("value", {})
            field = change.get("field")
            
            # Only process message changes
            if field != "messages":
                continue
            
            # Extract metadata
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
            display_phone_number = metadata.get("display_phone_number")
            
            # Extract contact information
            contacts = value.get("contacts", [])
            contact_map = {}
            for contact in contacts:
                wa_id = contact.get("wa_id")
                profile = contact.get("profile", {})
                contact_map[wa_id] = profile.get("name", "")
            
            # Process each message
            messages = value.get("messages", [])
            for message in messages:
                message_id = message.get("id")
                from_number = message.get("from")
                timestamp = message.get("timestamp")
                message_type = message.get("type")
                
                # Extract message content based on type
                message_body = None
                if message_type == "text":
                    text_data = message.get("text", {})
                    message_body = text_data.get("body")
                elif message_type == "image":
                    image_data = message.get("image", {})
                    message_body = image_data.get("caption", "")
                    # You might want to include image URL/id here
                elif message_type == "audio":
                    audio_data = message.get("audio", {})
                    message_body = f"[Audio message: {audio_data.get('id', 'unknown')}]"
                elif message_type == "video":
                    video_data = message.get("video", {})
                    message_body = video_data.get("caption", "")
                elif message_type == "document":
                    doc_data = message.get("document", {})
                    message_body = doc_data.get("caption", "")
                else:
                    message_body = f"[{message_type} message]"
                
                # Get contact name if available
                contact_name = contact_map.get(from_number, "")
                
                # Build message data structure
                message_data = {
                    "message_id": message_id,
                    "from": from_number,
                    "contact_name": contact_name,
                    "timestamp": timestamp,
                    "message_type": message_type,
                    "message_body": message_body,
                    "phone_number_id": phone_number_id,
                    "display_phone_number": display_phone_number,
                    "entry_id": entry_id
                }
                
                processed_messages.append(message_data)
                print(f"Extracted message: {message_id} from {from_number} ({contact_name})")
    
    # Return structured data for next flow step
    result = {
        "processed_count": len(processed_messages),
        "messages": processed_messages,
        "webhook_object": payload.get("object")
    }
    
    print(f"Processed {len(processed_messages)} message(s)")
    return result