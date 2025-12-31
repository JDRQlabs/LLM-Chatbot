# MCP Servers

This directory contains Model Context Protocol (MCP) servers that provide external tools to the LLM agent.

## Contact Owner MCP (`mcp-servers/contact-owner`)

Allows the chatbot to escalate issues or notify the business owner about high-value leads.

### Features & Implementation Status

| Channel | Status | Description |
| :--- | :--- | :--- |
| **Slack** | ✅ **Active** | Fully functional. Requires `slack_webhook_url` in the organization settings. |
| **Email** | 🚧 **In Progress** | Currently a stub. Logic exists but email provider integration (SendGrid/AWS SES) is pending. |
| **WhatsApp** | 🚧 **Planned** | Planned for future release. Will use template messages to notify owners via WhatsApp. |

### Configuration
To enable notifications, update the `organizations` table:
- Set `notification_method` to `'slack'`, `'email'`, or `'whatsapp'`.
- Ensure corresponding connection details (e.g., `slack_webhook_url`) are populated.
- If `notification_method` is missing or invalid, the tool will log the attempt but take no action (Fail-Safe).