# Backend Feature Requests for Frontend

The following API endpoints and features are required to complete the Phase 0 Frontend MVP.

## High Priority

### 1. Send Message
**Endpoint**: `POST /api/chatbots/:id/messages`
**Purpose**: Allows dashboard operators to reply to users manually.
**Payload**:
```json
{
  "contactId": "uuid",
  "content": "Hello world"
}
```
**Requirements**:
- Must check "24-hour window" rule.
- Must return error if window is closed.
- Should update `messages` table and trigger WhatsApp API.

### 2. Leads Filtering
**Endpoint**: `GET /api/chatbots/:id/leads` OR enhance `GET /api/chatbots/:id/contacts`
**Purpose**: Populate the "Leads Visualizer".
**Requirements**:
- Need a way to distinguish "Leads" from regular contacts.
- Is this based on a tag? A `status` column? Or a score?
- Please clarify the logic for "Visualizing Leads".

### 3. Knowledge Base Source List
**Endpoint**: `GET /api/chatbots/:id/knowledge`
**Purpose**: List all uploaded PDFs and URLs for a chatbot.
**Requirements**:
- Return list of sources with status (indexed, pending, error).
- Used to show the "Knowledge Base" table in the dashboard.

## Low Priority

### 4. Dashboard Analytics
**Endpoint**: `GET /api/analytics/dashboard`
**Purpose**: Fast aggregation for the dashboard overview cards.
**Current Workaround**: We are using `GET /api/organizations/usage`, but it lacks "Active Leads" count and "Active Bots" health status.
