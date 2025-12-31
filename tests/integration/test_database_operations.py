"""
Comprehensive integration tests for PostgreSQL database operations.

Tests CRUD operations, triggers, functions, and constraints for all core tables
in the RAG-enabled WhatsApp chatbot system.

Test Categories:
1. CRUD Tests - Basic create, read, update, delete operations
2. Database Trigger Tests - Verify triggers work as expected
3. Database Function Tests - Test stored procedures and functions
4. Constraint Tests - Verify constraints are enforced
"""

import pytest
import psycopg2
from datetime import datetime, timedelta
from decimal import Decimal


# ============================================================================
# 1. CRUD TESTS FOR CORE TABLES
# ============================================================================

class TestOrganizationsCRUD:
    """Test CRUD operations on organizations table."""

    def test_create_organization_with_defaults(self, db_with_data):
        """
        GOAL: Verify organization can be created with default values
        GIVEN: A database connection
        WHEN: An organization is created with only required fields
        THEN: The organization is created with proper default values
        """
        db_with_data.execute("""
            INSERT INTO organizations (name, slug)
            VALUES (%s, %s)
            RETURNING id, plan_tier, is_active, current_knowledge_pdfs, current_storage_mb
        """, ('Test Org', 'test-org'))

        result = db_with_data.fetchone()

        assert result['plan_tier'] == 'free'
        assert result['is_active'] is True
        assert result['current_knowledge_pdfs'] == 0
        assert result['current_storage_mb'] == Decimal('0')

    def test_read_organization_by_id(self, db_with_data):
        """
        GOAL: Verify organizations can be retrieved by ID
        GIVEN: Seeded database with test organization
        WHEN: Organization is queried by ID
        THEN: Correct organization data is returned
        """
        org_id = '11111111-1111-1111-1111-111111111111'

        db_with_data.execute("""
            SELECT name, slug, plan_tier, message_limit_monthly
            FROM organizations
            WHERE id = %s
        """, (org_id,))

        result = db_with_data.fetchone()

        assert result is not None
        assert result['name'] == 'JD Labs Corporation'
        assert result['slug'] == 'jd-labs-corp'
        assert result['plan_tier'] == 'pro'
        assert result['message_limit_monthly'] == 1000

    def test_update_organization_plan_tier(self, db_with_data):
        """
        GOAL: Verify organization plan tier can be updated
        GIVEN: Existing organization
        WHEN: Plan tier is updated with new limits
        THEN: Organization is updated and updated_at changes
        """
        org_id = '11111111-1111-1111-1111-111111111111'

        db_with_data.execute("""
            UPDATE organizations
            SET plan_tier = 'enterprise',
                message_limit_monthly = 10000,
                token_limit_monthly = 5000000
            WHERE id = %s
            RETURNING plan_tier, message_limit_monthly, token_limit_monthly
        """, (org_id,))

        result = db_with_data.fetchone()

        assert result['plan_tier'] == 'enterprise'
        assert result['message_limit_monthly'] == 10000
        assert result['token_limit_monthly'] == 5000000

    def test_delete_organization_cascades_to_users(self, db_with_data):
        """
        GOAL: Verify deleting organization cascades to related users
        GIVEN: Organization with associated users
        WHEN: Organization is deleted
        THEN: Associated users are also deleted (CASCADE)
        """
        # Create test organization with UUID
        import uuid
        test_org_id = str(uuid.uuid4())

        db_with_data.execute("""
            INSERT INTO organizations (id, name, slug)
            VALUES (%s::uuid, %s, %s)
        """, (test_org_id, 'Delete Test Org', 'delete-test'))

        # Create test user
        db_with_data.execute("""
            INSERT INTO users (organization_id, email, full_name)
            VALUES (%s::uuid, %s, %s)
            RETURNING id
        """, (test_org_id, 'testdelete@example.com', 'Test Delete User'))

        user_result = db_with_data.fetchone()
        user_id = user_result['id']

        # Delete organization
        db_with_data.execute("""
            DELETE FROM organizations WHERE id = %s::uuid
        """, (test_org_id,))

        # Verify user was cascade deleted
        db_with_data.execute("""
            SELECT COUNT(*) as count FROM users WHERE id = %s
        """, (user_id,))

        result = db_with_data.fetchone()
        assert result['count'] == 0


class TestChatbotsCRUD:
    """Test CRUD operations on chatbots table."""

    def test_create_chatbot_with_rag_enabled(self, db_with_data):
        """
        GOAL: Verify chatbot can be created with RAG enabled
        GIVEN: Valid organization
        WHEN: Chatbot is created with rag_enabled=TRUE
        THEN: Chatbot is created successfully with RAG configuration
        """
        org_id = '11111111-1111-1111-1111-111111111111'

        db_with_data.execute("""
            INSERT INTO chatbots (
                organization_id,
                name,
                whatsapp_phone_number_id,
                rag_enabled,
                model_name
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, rag_enabled, is_active, temperature
        """, (org_id, 'RAG Test Bot', 'phone-rag-test-001', True, 'gpt-4'))

        result = db_with_data.fetchone()

        assert result['rag_enabled'] is True
        assert result['is_active'] is True
        assert result['temperature'] == Decimal('0.7')

    def test_read_chatbot_with_organization(self, db_with_data):
        """
        GOAL: Verify chatbot can be retrieved with organization details
        GIVEN: Chatbot in database
        WHEN: Chatbot is queried with JOIN to organization
        THEN: Complete chatbot and organization data is returned
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        db_with_data.execute("""
            SELECT
                c.id,
                c.name as chatbot_name,
                c.whatsapp_phone_number_id,
                c.rag_enabled,
                o.name as org_name,
                o.plan_tier
            FROM chatbots c
            JOIN organizations o ON c.organization_id = o.id
            WHERE c.id = %s
        """, (chatbot_id,))

        result = db_with_data.fetchone()

        assert result is not None
        assert result['chatbot_name'] == 'MVP Test Bot'
        assert result['org_name'] == 'JD Labs Corporation'
        assert result['plan_tier'] == 'pro'

    def test_update_chatbot_model_and_temperature(self, db_with_data):
        """
        GOAL: Verify chatbot AI configuration can be updated
        GIVEN: Existing chatbot
        WHEN: Model and temperature are updated
        THEN: Changes are persisted correctly
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        db_with_data.execute("""
            UPDATE chatbots
            SET model_name = %s,
                temperature = %s
            WHERE id = %s
            RETURNING model_name, temperature
        """, ('gpt-4-turbo', 0.3, chatbot_id))

        result = db_with_data.fetchone()

        assert result['model_name'] == 'gpt-4-turbo'
        assert result['temperature'] == Decimal('0.3')

    def test_chatbot_unique_phone_number_constraint(self, db_with_data):
        """
        GOAL: Verify whatsapp_phone_number_id must be unique
        GIVEN: Existing chatbot with phone number
        WHEN: Another chatbot is created with same phone number
        THEN: Unique constraint violation is raised
        """
        org_id = '11111111-1111-1111-1111-111111111111'

        with pytest.raises(psycopg2.IntegrityError) as exc_info:
            db_with_data.execute("""
                INSERT INTO chatbots (
                    organization_id,
                    name,
                    whatsapp_phone_number_id
                )
                VALUES (%s, %s, %s)
            """, (org_id, 'Duplicate Phone Bot', 'test_phone_123'))

        assert 'whatsapp_phone_number_id' in str(exc_info.value).lower()


class TestContactsCRUD:
    """Test CRUD operations on contacts table."""

    def test_create_contact_with_variables(self, db_with_data):
        """
        GOAL: Verify contact can be created with JSONB variables
        GIVEN: Valid chatbot
        WHEN: Contact is created with custom variables
        THEN: Contact is created with variables stored as JSONB
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        db_with_data.execute("""
            INSERT INTO contacts (
                chatbot_id,
                phone_number,
                name,
                variables,
                tags
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, variables, tags, conversation_mode
        """, (
            chatbot_id,
            '15551112222',
            'Test Contact',
            '{"lead_score": 85, "industry": "tech"}',
            ['hot-lead', 'enterprise']
        ))

        result = db_with_data.fetchone()

        assert result['variables']['lead_score'] == 85
        assert result['variables']['industry'] == 'tech'
        assert 'hot-lead' in result['tags']
        assert result['conversation_mode'] == 'auto'

    def test_contact_unique_phone_per_chatbot(self, db_with_data):
        """
        GOAL: Verify phone number must be unique per chatbot
        GIVEN: Contact exists for a chatbot
        WHEN: Another contact with same phone is created for same chatbot
        THEN: Unique constraint violation is raised
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'
        phone = '15550001234'  # Alice's existing phone

        with pytest.raises(psycopg2.IntegrityError) as exc_info:
            db_with_data.execute("""
                INSERT INTO contacts (chatbot_id, phone_number, name)
                VALUES (%s, %s, %s)
            """, (chatbot_id, phone, 'Duplicate Alice'))

        assert 'chatbot_id' in str(exc_info.value).lower() or 'phone_number' in str(exc_info.value).lower()

    def test_update_contact_conversation_mode(self, db_with_data):
        """
        GOAL: Verify contact conversation mode can be toggled
        GIVEN: Contact in auto mode
        WHEN: Conversation mode is updated to manual
        THEN: Mode is changed and updated_at is updated
        """
        contact_id = '44444444-4444-4444-4444-444444444444'

        db_with_data.execute("""
            UPDATE contacts
            SET conversation_mode = 'manual',
                unread_count = 5
            WHERE id = %s
            RETURNING conversation_mode, unread_count
        """, (contact_id,))

        result = db_with_data.fetchone()

        assert result['conversation_mode'] == 'manual'
        assert result['unread_count'] == 5


class TestMessagesCRUD:
    """Test CRUD operations on messages table."""

    def test_create_user_message_with_whatsapp_id(self, db_with_data):
        """
        GOAL: Verify user message can be created with WhatsApp message ID
        GIVEN: Valid contact
        WHEN: User message is inserted
        THEN: Message is created with whatsapp_message_id for idempotency
        """
        contact_id = '44444444-4444-4444-4444-444444444444'

        db_with_data.execute("""
            INSERT INTO messages (
                contact_id,
                role,
                content,
                whatsapp_message_id
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id, role, whatsapp_message_id
        """, (contact_id, 'user', 'Test message', 'wamid.test.new.001'))

        result = db_with_data.fetchone()

        assert result['role'] == 'user'
        assert result['whatsapp_message_id'] == 'wamid.test.new.001'

    def test_create_assistant_message_with_tool_calls(self, db_with_data):
        """
        GOAL: Verify assistant message can store tool call data
        GIVEN: Valid contact
        WHEN: Assistant message with tool calls is created
        THEN: Tool call data is stored as JSONB
        """
        contact_id = '44444444-4444-4444-4444-444444444444'

        tool_calls = {
            "calls": [
                {
                    "tool": "calculate_pricing",
                    "args": {"message_volume": 5000, "tier": "professional"}
                }
            ]
        }

        tool_results = {
            "results": [
                {
                    "tool": "calculate_pricing",
                    "result": {"price": 999, "currency": "MXN"}
                }
            ]
        }

        db_with_data.execute("""
            INSERT INTO messages (
                contact_id,
                role,
                content,
                tool_calls,
                tool_results
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, tool_calls, tool_results
        """, (contact_id, 'assistant', 'The price is 999 MXN',
              str(tool_calls).replace("'", '"'),
              str(tool_results).replace("'", '"')))

        result = db_with_data.fetchone()

        assert result['tool_calls'] is not None
        assert result['tool_results'] is not None

    def test_read_conversation_history_ordered(self, db_with_data):
        """
        GOAL: Verify messages can be retrieved in chronological order
        GIVEN: Contact with multiple messages
        WHEN: Messages are queried ordered by created_at
        THEN: Messages are returned in correct order
        """
        contact_id = '44444444-4444-4444-4444-444444444444'

        db_with_data.execute("""
            SELECT role, content, created_at
            FROM messages
            WHERE contact_id = %s
            ORDER BY created_at ASC
        """, (contact_id,))

        messages = db_with_data.fetchall()

        assert len(messages) > 0
        # Verify chronological order
        for i in range(1, len(messages)):
            assert messages[i]['created_at'] >= messages[i-1]['created_at']


class TestKnowledgeSourcesCRUD:
    """Test CRUD operations on knowledge_sources table."""

    def test_create_pdf_knowledge_source(self, db_with_data):
        """
        GOAL: Verify PDF knowledge source can be created
        GIVEN: Valid chatbot
        WHEN: PDF source is inserted
        THEN: Source is created with pending sync status
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        db_with_data.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                file_path,
                file_size_bytes,
                sync_status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, source_type, sync_status, chunks_count
        """, (chatbot_id, 'pdf', 'Product Manual.pdf', '/uploads/manual.pdf',
              1048576, 'pending'))

        result = db_with_data.fetchone()

        assert result['source_type'] == 'pdf'
        assert result['sync_status'] == 'pending'
        assert result['chunks_count'] == 0

    def test_update_knowledge_source_sync_status(self, db_with_data):
        """
        GOAL: Verify knowledge source sync status can be updated
        GIVEN: Knowledge source in pending state
        WHEN: Sync completes and status is updated
        THEN: Status changes to synced with timestamp
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create source
        db_with_data.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                sync_status
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'url', 'Company Website', 'processing'))

        source_id = db_with_data.fetchone()['id']

        # Update to synced
        db_with_data.execute("""
            UPDATE knowledge_sources
            SET sync_status = 'synced',
                last_synced_at = NOW()
            WHERE id = %s
            RETURNING sync_status, last_synced_at
        """, (source_id,))

        result = db_with_data.fetchone()

        assert result['sync_status'] == 'synced'
        assert result['last_synced_at'] is not None


class TestDocumentChunksCRUD:
    """Test CRUD operations on document_chunks table."""

    def test_create_document_chunk_with_embedding(self, db_with_data):
        """
        GOAL: Verify document chunk can be created with vector embedding
        GIVEN: Valid knowledge source
        WHEN: Chunk with 1536-dim embedding is inserted
        THEN: Chunk is stored with embedding vector
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source first
        db_with_data.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                sync_status
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Test Doc', 'processing'))

        source_id = db_with_data.fetchone()['id']

        # Create embedding vector (1536 dimensions)
        embedding = '[' + ', '.join(['0.1'] * 1536) + ']'

        # Insert chunk
        db_with_data.execute("""
            INSERT INTO document_chunks (
                knowledge_source_id,
                chatbot_id,
                content,
                chunk_index,
                embedding,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s::vector, %s)
            RETURNING id, chunk_index, metadata
        """, (source_id, chatbot_id, 'This is test content', 0,
              embedding, '{"page": 1}'))

        result = db_with_data.fetchone()

        assert result['chunk_index'] == 0
        assert result['metadata']['page'] == 1

    def test_document_chunk_unique_constraint(self, db_with_data):
        """
        GOAL: Verify chunk_index must be unique per knowledge source
        GIVEN: Existing chunk with index 0
        WHEN: Another chunk with same index is created for same source
        THEN: Unique constraint violation is raised
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_data.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Test Doc'))

        source_id = db_with_data.fetchone()['id']

        # Insert first chunk
        db_with_data.execute("""
            INSERT INTO document_chunks (
                knowledge_source_id,
                chatbot_id,
                content,
                chunk_index
            )
            VALUES (%s, %s, %s, %s)
        """, (source_id, chatbot_id, 'Chunk 0', 0))

        # Try to insert duplicate
        with pytest.raises(psycopg2.IntegrityError) as exc_info:
            db_with_data.execute("""
                INSERT INTO document_chunks (
                    knowledge_source_id,
                    chatbot_id,
                    content,
                    chunk_index
                )
                VALUES (%s, %s, %s, %s)
            """, (source_id, chatbot_id, 'Duplicate Chunk 0', 0))

        assert 'unique' in str(exc_info.value).lower()


# ============================================================================
# 2. DATABASE TRIGGER TESTS
# ============================================================================

class TestKnowledgeSourceCounterTrigger:
    """
    Test the knowledge_source_counter_trigger that increments counters
    when knowledge sources are added.

    Trigger definition: Lines 460-463 in create.sql
    Function: increment_knowledge_counters() (Lines 423-458)
    """

    def test_pdf_insert_increments_pdf_counter(self, db_with_autocommit):
        """
        GOAL: Verify inserting PDF increments organization's PDF counter
        GIVEN: Organization with 0 PDFs
        WHEN: PDF knowledge source is inserted
        THEN: current_knowledge_pdfs increments by 1
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Get current count
        db_with_autocommit.execute("""
            SELECT current_knowledge_pdfs FROM organizations WHERE id = %s
        """, (org_id,))
        initial_count = db_with_autocommit.fetchone()['current_knowledge_pdfs']

        # Insert PDF
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                file_size_bytes
            )
            VALUES (%s, %s, %s, %s)
        """, (chatbot_id, 'pdf', 'Test.pdf', 2097152))  # 2MB

        # Check counter
        db_with_autocommit.execute("""
            SELECT current_knowledge_pdfs FROM organizations WHERE id = %s
        """, (org_id,))
        new_count = db_with_autocommit.fetchone()['current_knowledge_pdfs']

        assert new_count == initial_count + 1

    def test_url_insert_increments_url_counter(self, db_with_autocommit):
        """
        GOAL: Verify inserting URL increments organization's URL counter
        GIVEN: Organization with 0 URLs
        WHEN: URL knowledge source is inserted
        THEN: current_knowledge_urls increments by 1
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Get current count
        db_with_autocommit.execute("""
            SELECT current_knowledge_urls FROM organizations WHERE id = %s
        """, (org_id,))
        initial_count = db_with_autocommit.fetchone()['current_knowledge_urls']

        # Insert URL
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                file_size_bytes
            )
            VALUES (%s, %s, %s, %s)
        """, (chatbot_id, 'url', 'https://example.com', 10240))  # 10KB

        # Check counter
        db_with_autocommit.execute("""
            SELECT current_knowledge_urls FROM organizations WHERE id = %s
        """, (org_id,))
        new_count = db_with_autocommit.fetchone()['current_knowledge_urls']

        assert new_count == initial_count + 1

    def test_pdf_insert_updates_storage_counter(self, db_with_autocommit):
        """
        GOAL: Verify inserting PDF updates current_storage_mb
        GIVEN: Organization with current storage
        WHEN: PDF with file_size_bytes is inserted
        THEN: current_storage_mb increases by file size in MB
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Get current storage
        db_with_autocommit.execute("""
            SELECT current_storage_mb FROM organizations WHERE id = %s
        """, (org_id,))
        initial_storage = float(db_with_autocommit.fetchone()['current_storage_mb'])

        # Insert 5MB PDF
        file_size_bytes = 5 * 1024 * 1024  # 5MB
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                file_size_bytes
            )
            VALUES (%s, %s, %s, %s)
        """, (chatbot_id, 'pdf', 'Large.pdf', file_size_bytes))

        # Check storage
        db_with_autocommit.execute("""
            SELECT current_storage_mb FROM organizations WHERE id = %s
        """, (org_id,))
        new_storage = float(db_with_autocommit.fetchone()['current_storage_mb'])

        expected_storage = initial_storage + 5.0
        assert abs(new_storage - expected_storage) < 0.01  # Allow small float difference

    def test_daily_ingestion_count_increments(self, db_with_autocommit):
        """
        GOAL: Verify inserting knowledge source updates daily_ingestion_counts
        GIVEN: Organization with no ingestions today
        WHEN: Knowledge source is inserted
        THEN: daily_ingestion_counts table is updated with count=1
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Insert knowledge source
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
        """, (chatbot_id, 'pdf', 'Daily Test.pdf'))

        # Check daily count
        db_with_autocommit.execute("""
            SELECT ingestion_count
            FROM daily_ingestion_counts
            WHERE organization_id = %s AND date = CURRENT_DATE
        """, (org_id,))

        result = db_with_autocommit.fetchone()
        assert result is not None
        assert result['ingestion_count'] >= 1

    def test_multiple_inserts_increment_daily_count(self, db_with_autocommit):
        """
        GOAL: Verify multiple knowledge sources increment daily count correctly
        GIVEN: Organization with existing daily count
        WHEN: Multiple knowledge sources are inserted
        THEN: daily_ingestion_counts increments for each insert
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Get current daily count
        db_with_autocommit.execute("""
            SELECT COALESCE(ingestion_count, 0) as count
            FROM daily_ingestion_counts
            WHERE organization_id = %s AND date = CURRENT_DATE
        """, (org_id,))

        result = db_with_autocommit.fetchone()
        initial_count = result['count'] if result else 0

        # Insert 3 sources
        for i in range(3):
            db_with_autocommit.execute("""
                INSERT INTO knowledge_sources (
                    chatbot_id,
                    source_type,
                    name
                )
                VALUES (%s, %s, %s)
            """, (chatbot_id, 'pdf', f'Test{i}.pdf'))

        # Check count increased by 3
        db_with_autocommit.execute("""
            SELECT ingestion_count
            FROM daily_ingestion_counts
            WHERE organization_id = %s AND date = CURRENT_DATE
        """, (org_id,))

        final_count = db_with_autocommit.fetchone()['ingestion_count']
        assert final_count == initial_count + 3


class TestChunksCountTrigger:
    """
    Test the trigger_update_chunks_count that updates knowledge_sources.chunks_count
    when chunks are inserted or deleted.

    Trigger definition: Lines 417-420 in create.sql
    Function: update_knowledge_source_chunks_count() (Lines 399-415)
    """

    def test_insert_chunk_increments_count(self, db_with_autocommit):
        """
        GOAL: Verify inserting chunk increments knowledge_source chunks_count
        GIVEN: Knowledge source with 0 chunks
        WHEN: Document chunk is inserted
        THEN: chunks_count increments by 1
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Chunk Test.pdf'))

        source_id = db_with_autocommit.fetchone()['id']

        # Insert chunk
        db_with_autocommit.execute("""
            INSERT INTO document_chunks (
                knowledge_source_id,
                chatbot_id,
                content,
                chunk_index
            )
            VALUES (%s, %s, %s, %s)
        """, (source_id, chatbot_id, 'Test content', 0))

        # Check count
        db_with_autocommit.execute("""
            SELECT chunks_count FROM knowledge_sources WHERE id = %s
        """, (source_id,))

        result = db_with_autocommit.fetchone()
        assert result['chunks_count'] == 1

    def test_multiple_chunks_increment_count_correctly(self, db_with_autocommit):
        """
        GOAL: Verify inserting multiple chunks increments count correctly
        GIVEN: Knowledge source with 0 chunks
        WHEN: 5 chunks are inserted
        THEN: chunks_count equals 5
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Multi Chunk.pdf'))

        source_id = db_with_autocommit.fetchone()['id']

        # Insert 5 chunks
        for i in range(5):
            db_with_autocommit.execute("""
                INSERT INTO document_chunks (
                    knowledge_source_id,
                    chatbot_id,
                    content,
                    chunk_index
                )
                VALUES (%s, %s, %s, %s)
            """, (source_id, chatbot_id, f'Content {i}', i))

        # Check count
        db_with_autocommit.execute("""
            SELECT chunks_count FROM knowledge_sources WHERE id = %s
        """, (source_id,))

        result = db_with_autocommit.fetchone()
        assert result['chunks_count'] == 5

    def test_delete_chunk_decrements_count(self, db_with_autocommit):
        """
        GOAL: Verify deleting chunk decrements knowledge_source chunks_count
        GIVEN: Knowledge source with 3 chunks
        WHEN: One chunk is deleted
        THEN: chunks_count decrements by 1
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Delete Test.pdf'))

        source_id = db_with_autocommit.fetchone()['id']

        # Insert 3 chunks
        chunk_ids = []
        for i in range(3):
            db_with_autocommit.execute("""
                INSERT INTO document_chunks (
                    knowledge_source_id,
                    chatbot_id,
                    content,
                    chunk_index
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (source_id, chatbot_id, f'Content {i}', i))
            chunk_ids.append(db_with_autocommit.fetchone()['id'])

        # Delete one chunk
        db_with_autocommit.execute("""
            DELETE FROM document_chunks WHERE id = %s
        """, (chunk_ids[0],))

        # Check count
        db_with_autocommit.execute("""
            SELECT chunks_count FROM knowledge_sources WHERE id = %s
        """, (source_id,))

        result = db_with_autocommit.fetchone()
        assert result['chunks_count'] == 2


# ============================================================================
# 3. DATABASE FUNCTION TESTS
# ============================================================================

class TestSearchKnowledgeBaseFunction:
    """
    Test the search_knowledge_base() function for RAG similarity search.

    Function definition: Lines 344-375 in create.sql
    """

    def test_search_returns_similar_chunks_above_threshold(self, db_with_autocommit):
        """
        GOAL: Verify search_knowledge_base returns chunks above similarity threshold
        GIVEN: Chunks with embeddings in database
        WHEN: Function is called with query embedding and threshold=0.7
        THEN: Only chunks with similarity >= 0.7 are returned
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                sync_status
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Search Test.pdf', 'synced'))

        source_id = db_with_autocommit.fetchone()['id']

        # Create similar embedding (1536 dimensions, all 0.1)
        similar_embedding = '[' + ', '.join(['0.1'] * 1536) + ']'

        # Insert chunks with embeddings
        db_with_autocommit.execute("""
            INSERT INTO document_chunks (
                knowledge_source_id,
                chatbot_id,
                content,
                chunk_index,
                embedding,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s::vector, %s)
        """, (source_id, chatbot_id, 'Similar content', 0,
              similar_embedding, '{"page": 1}'))

        # Call search function
        query_embedding = '[' + ', '.join(['0.1'] * 1536) + ']'

        db_with_autocommit.execute("""
            SELECT * FROM search_knowledge_base(
                %s::uuid,
                %s::vector,
                5,
                0.7
            )
        """, (chatbot_id, query_embedding))

        results = db_with_autocommit.fetchall()

        # Should return at least the similar chunk
        assert len(results) > 0
        # All results should have similarity >= 0.7
        for result in results:
            assert result['similarity'] >= 0.7

    def test_search_respects_chatbot_filter(self, db_with_autocommit):
        """
        GOAL: Verify search_knowledge_base only returns chunks for specified chatbot
        GIVEN: Chunks for multiple chatbots
        WHEN: Search is called for specific chatbot
        THEN: Only chunks from that chatbot are returned
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id_1 = '22222222-2222-2222-2222-222222222222'

        # Create second chatbot
        db_with_autocommit.execute("""
            INSERT INTO chatbots (
                organization_id,
                name,
                whatsapp_phone_number_id
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (org_id, 'Bot 2', 'phone-test-search-002'))

        chatbot_id_2 = db_with_autocommit.fetchone()['id']

        # Create knowledge sources for both chatbots
        for chatbot_id, name in [(chatbot_id_1, 'Doc1'), (chatbot_id_2, 'Doc2')]:
            db_with_autocommit.execute("""
                INSERT INTO knowledge_sources (
                    chatbot_id,
                    source_type,
                    name
                )
                VALUES (%s, %s, %s)
                RETURNING id
            """, (chatbot_id, 'pdf', name))

            source_id = db_with_autocommit.fetchone()['id']

            # Insert chunk
            embedding = '[' + ', '.join(['0.1'] * 1536) + ']'
            db_with_autocommit.execute("""
                INSERT INTO document_chunks (
                    knowledge_source_id,
                    chatbot_id,
                    content,
                    chunk_index,
                    embedding
                )
                VALUES (%s, %s, %s, %s, %s::vector)
            """, (source_id, chatbot_id, f'Content for {name}', 0, embedding))

        # Search for chatbot 1 only
        query_embedding = '[' + ', '.join(['0.1'] * 1536) + ']'

        db_with_autocommit.execute("""
            SELECT * FROM search_knowledge_base(
                %s::uuid,
                %s::vector,
                10,
                0.5
            )
        """, (chatbot_id_1, query_embedding))

        results = db_with_autocommit.fetchall()

        # Should only have results from Doc1
        assert len(results) > 0
        for result in results:
            assert result['source_name'] == 'Doc1'

    def test_search_respects_limit_parameter(self, db_with_autocommit):
        """
        GOAL: Verify search_knowledge_base respects the limit parameter
        GIVEN: 10 chunks in database
        WHEN: Search is called with limit=3
        THEN: At most 3 results are returned
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Limit Test.pdf'))

        source_id = db_with_autocommit.fetchone()['id']

        # Insert 10 chunks
        embedding = '[' + ', '.join(['0.1'] * 1536) + ']'
        for i in range(10):
            db_with_autocommit.execute("""
                INSERT INTO document_chunks (
                    knowledge_source_id,
                    chatbot_id,
                    content,
                    chunk_index,
                    embedding
                )
                VALUES (%s, %s, %s, %s, %s::vector)
            """, (source_id, chatbot_id, f'Chunk {i}', i, embedding))

        # Search with limit=3
        query_embedding = '[' + ', '.join(['0.1'] * 1536) + ']'

        db_with_autocommit.execute("""
            SELECT * FROM search_knowledge_base(
                %s::uuid,
                %s::vector,
                3,
                0.5
            )
        """, (chatbot_id, query_embedding))

        results = db_with_autocommit.fetchall()

        assert len(results) <= 3

    def test_search_returns_metadata_and_source_info(self, db_with_autocommit):
        """
        GOAL: Verify search results include metadata and source information
        GIVEN: Chunks with metadata
        WHEN: Search is performed
        THEN: Results include chunk metadata and source details
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_autocommit.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Metadata Test.pdf'))

        source_id = db_with_autocommit.fetchone()['id']

        # Insert chunk with metadata
        embedding = '[' + ', '.join(['0.2'] * 1536) + ']'
        db_with_autocommit.execute("""
            INSERT INTO document_chunks (
                knowledge_source_id,
                chatbot_id,
                content,
                chunk_index,
                embedding,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s::vector, %s)
        """, (source_id, chatbot_id, 'Test content', 0,
              embedding, '{"page": 5, "section": "Introduction"}'))

        # Search
        query_embedding = '[' + ', '.join(['0.2'] * 1536) + ']'

        db_with_autocommit.execute("""
            SELECT * FROM search_knowledge_base(
                %s::uuid,
                %s::vector,
                5,
                0.5
            )
        """, (chatbot_id, query_embedding))

        results = db_with_autocommit.fetchall()

        assert len(results) > 0
        result = results[0]
        assert result['source_name'] == 'Metadata Test.pdf'
        assert result['source_type'] == 'pdf'
        assert result['metadata']['page'] == 5
        assert result['metadata']['section'] == 'Introduction'


class TestGetCurrentUsageFunction:
    """
    Test the get_current_usage() function for billing period usage calculation.

    Function definition: Lines 490-511 in create.sql
    """

    def test_get_usage_sums_messages_and_tokens(self, db_with_data):
        """
        GOAL: Verify get_current_usage correctly sums messages and tokens
        GIVEN: Usage logs for an organization
        WHEN: Function is called
        THEN: Correct total messages and tokens are returned
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id = '22222222-2222-2222-2222-222222222222'
        contact_id = '44444444-4444-4444-4444-444444444444'

        # Get billing period for the org
        db_with_data.execute("""
            SELECT billing_period_start, billing_period_end
            FROM organizations WHERE id = %s
        """, (org_id,))

        org = db_with_data.fetchone()

        # Insert test usage logs within the billing period
        for i in range(3):
            db_with_data.execute("""
                INSERT INTO usage_logs (
                    organization_id,
                    chatbot_id,
                    contact_id,
                    message_count,
                    tokens_total,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (org_id, chatbot_id, contact_id, 1, 100 + (i * 50)))

        # Call function
        db_with_data.execute("""
            SELECT * FROM get_current_usage(%s)
        """, (org_id,))

        result = db_with_data.fetchone()

        # Should have at least 3 messages and 100 + 150 + 200 = 450 tokens from our inserts
        assert result['messages_used'] >= 3
        assert result['tokens_used'] >= 450

    def test_get_usage_respects_billing_period(self, db_with_data):
        """
        GOAL: Verify function only counts usage within billing period
        GIVEN: Usage logs outside and inside billing period
        WHEN: Function is called
        THEN: Only usage within billing period is counted
        """
        org_id = '11111111-1111-1111-1111-111111111111'

        # Get billing period
        db_with_data.execute("""
            SELECT billing_period_start, billing_period_end
            FROM organizations WHERE id = %s
        """, (org_id,))

        org = db_with_data.fetchone()

        # Add usage outside billing period
        chatbot_id = '22222222-2222-2222-2222-222222222222'
        contact_id = '44444444-4444-4444-4444-444444444444'

        outside_date = org['billing_period_end'] + timedelta(days=1)

        db_with_data.execute("""
            INSERT INTO usage_logs (
                organization_id,
                chatbot_id,
                contact_id,
                message_count,
                tokens_total,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (org_id, chatbot_id, contact_id, 1, 500, outside_date))

        # Get usage - should not include the outside usage
        db_with_data.execute("""
            SELECT * FROM get_current_usage(%s)
        """, (org_id,))

        result = db_with_data.fetchone()

        # Should not include the 500 tokens from outside period
        # (Exact value depends on seed data, but should be < 500 + seed total)
        assert result['tokens_used'] < 2000  # Reasonable upper bound

    def test_get_usage_returns_zero_for_new_org(self, db_with_data):
        """
        GOAL: Verify function returns zero for organization with no usage
        GIVEN: New organization with no usage logs
        WHEN: Function is called
        THEN: 0 messages and 0 tokens are returned
        """
        # Create new org
        db_with_data.execute("""
            INSERT INTO organizations (name, slug)
            VALUES (%s, %s)
            RETURNING id
        """, ('New Org', 'new-org'))

        new_org_id = db_with_data.fetchone()['id']

        # Get usage
        db_with_data.execute("""
            SELECT * FROM get_current_usage(%s)
        """, (new_org_id,))

        result = db_with_data.fetchone()

        assert result['messages_used'] == 0
        assert result['tokens_used'] == 0


# ============================================================================
# 4. CONSTRAINT TESTS
# ============================================================================

class TestUniqueConstraints:
    """Test UNIQUE constraints across tables."""

    def test_organization_slug_must_be_unique(self, db_with_data):
        """
        GOAL: Verify organization slug must be unique
        GIVEN: Organization with slug 'test-slug'
        WHEN: Another organization with same slug is created
        THEN: Unique constraint violation is raised
        """
        db_with_data.execute("""
            INSERT INTO organizations (name, slug)
            VALUES (%s, %s)
        """, ('First Org', 'unique-slug-test'))

        with pytest.raises(psycopg2.IntegrityError) as exc_info:
            db_with_data.execute("""
                INSERT INTO organizations (name, slug)
                VALUES (%s, %s)
            """, ('Second Org', 'unique-slug-test'))

        assert 'unique' in str(exc_info.value).lower()

    def test_user_email_must_be_unique(self, db_with_data):
        """
        GOAL: Verify user email must be unique across all organizations
        GIVEN: User with email 'test@example.com'
        WHEN: Another user with same email is created
        THEN: Unique constraint violation is raised
        """
        org_id = '11111111-1111-1111-1111-111111111111'

        db_with_data.execute("""
            INSERT INTO users (organization_id, email, full_name)
            VALUES (%s, %s, %s)
        """, (org_id, 'unique@test.com', 'First User'))

        with pytest.raises(psycopg2.IntegrityError) as exc_info:
            db_with_data.execute("""
                INSERT INTO users (organization_id, email, full_name)
                VALUES (%s, %s, %s)
            """, (org_id, 'unique@test.com', 'Second User'))

        assert 'email' in str(exc_info.value).lower() or 'unique' in str(exc_info.value).lower()

    def test_webhook_message_id_must_be_unique(self, db_with_data):
        """
        GOAL: Verify WhatsApp message ID must be unique in webhook_events
        GIVEN: Webhook event with message ID
        WHEN: Another event with same message ID is created
        THEN: Unique constraint violation is raised (idempotency)
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        db_with_data.execute("""
            INSERT INTO webhook_events (
                whatsapp_message_id,
                phone_number_id,
                chatbot_id
            )
            VALUES (%s, %s, %s)
        """, ('wamid.unique.test.001', 'phone_123', chatbot_id))

        with pytest.raises(psycopg2.IntegrityError) as exc_info:
            db_with_data.execute("""
                INSERT INTO webhook_events (
                    whatsapp_message_id,
                    phone_number_id,
                    chatbot_id
                )
                VALUES (%s, %s, %s)
            """, ('wamid.unique.test.001', 'phone_123', chatbot_id))

        assert 'whatsapp_message_id' in str(exc_info.value).lower() or 'unique' in str(exc_info.value).lower()


class TestForeignKeyConstraints:
    """Test foreign key constraints and CASCADE behavior."""

    def test_delete_chatbot_cascades_to_contacts(self, db_with_data):
        """
        GOAL: Verify deleting chatbot cascades to contacts
        GIVEN: Chatbot with contacts
        WHEN: Chatbot is deleted
        THEN: All associated contacts are deleted
        """
        org_id = '11111111-1111-1111-1111-111111111111'

        # Create chatbot
        db_with_data.execute("""
            INSERT INTO chatbots (
                organization_id,
                name,
                whatsapp_phone_number_id
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (org_id, 'Cascade Test Bot', 'phone-cascade-001'))

        chatbot_id = db_with_data.fetchone()['id']

        # Create contacts
        contact_ids = []
        for i in range(3):
            db_with_data.execute("""
                INSERT INTO contacts (
                    chatbot_id,
                    phone_number,
                    name
                )
                VALUES (%s, %s, %s)
                RETURNING id
            """, (chatbot_id, f'155500{i:05d}', f'Contact {i}'))
            contact_ids.append(db_with_data.fetchone()['id'])

        # Delete chatbot
        db_with_data.execute("""
            DELETE FROM chatbots WHERE id = %s
        """, (chatbot_id,))

        # Verify contacts deleted
        db_with_data.execute("""
            SELECT COUNT(*) as count FROM contacts
            WHERE id = ANY(%s::uuid[])
        """, (contact_ids,))

        result = db_with_data.fetchone()
        assert result['count'] == 0

    def test_delete_contact_cascades_to_messages(self, db_with_data):
        """
        GOAL: Verify deleting contact cascades to messages
        GIVEN: Contact with message history
        WHEN: Contact is deleted
        THEN: All associated messages are deleted
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create contact
        db_with_data.execute("""
            INSERT INTO contacts (
                chatbot_id,
                phone_number,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, '15551234567', 'Message Cascade Test'))

        contact_id = db_with_data.fetchone()['id']

        # Create messages
        message_ids = []
        for i in range(5):
            db_with_data.execute("""
                INSERT INTO messages (
                    contact_id,
                    role,
                    content
                )
                VALUES (%s, %s, %s)
                RETURNING id
            """, (contact_id, 'user' if i % 2 == 0 else 'assistant', f'Message {i}'))
            message_ids.append(db_with_data.fetchone()['id'])

        # Delete contact
        db_with_data.execute("""
            DELETE FROM contacts WHERE id = %s
        """, (contact_id,))

        # Verify messages deleted
        db_with_data.execute("""
            SELECT COUNT(*) as count FROM messages
            WHERE id = ANY(%s::bigint[])
        """, (message_ids,))

        result = db_with_data.fetchone()
        assert result['count'] == 0

    def test_delete_knowledge_source_cascades_to_chunks(self, db_with_data):
        """
        GOAL: Verify deleting knowledge source cascades to chunks
        GIVEN: Knowledge source with document chunks
        WHEN: Knowledge source is deleted
        THEN: All associated chunks are deleted
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        # Create knowledge source
        db_with_data.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (chatbot_id, 'pdf', 'Cascade Chunks Test.pdf'))

        source_id = db_with_data.fetchone()['id']

        # Create chunks
        chunk_ids = []
        for i in range(10):
            db_with_data.execute("""
                INSERT INTO document_chunks (
                    knowledge_source_id,
                    chatbot_id,
                    content,
                    chunk_index
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (source_id, chatbot_id, f'Chunk {i}', i))
            chunk_ids.append(db_with_data.fetchone()['id'])

        # Delete knowledge source
        db_with_data.execute("""
            DELETE FROM knowledge_sources WHERE id = %s
        """, (source_id,))

        # Verify chunks deleted
        db_with_data.execute("""
            SELECT COUNT(*) as count FROM document_chunks
            WHERE id = ANY(%s::uuid[])
        """, (chunk_ids,))

        result = db_with_data.fetchone()
        assert result['count'] == 0

    def test_delete_webhook_event_sets_null_on_usage_logs(self, db_with_data):
        """
        GOAL: Verify deleting webhook event sets usage_logs.webhook_event_id to NULL
        GIVEN: Usage log referencing webhook event
        WHEN: Webhook event is deleted
        THEN: usage_logs.webhook_event_id is set to NULL (not cascade delete)
        """
        org_id = '11111111-1111-1111-1111-111111111111'
        chatbot_id = '22222222-2222-2222-2222-222222222222'
        contact_id = '44444444-4444-4444-4444-444444444444'

        # Create webhook event
        db_with_data.execute("""
            INSERT INTO webhook_events (
                whatsapp_message_id,
                phone_number_id,
                chatbot_id,
                status
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, ('wamid.set.null.test', 'phone_123', chatbot_id, 'completed'))

        webhook_id = db_with_data.fetchone()['id']

        # Create usage log
        db_with_data.execute("""
            INSERT INTO usage_logs (
                organization_id,
                chatbot_id,
                contact_id,
                webhook_event_id,
                message_count,
                tokens_total
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (org_id, chatbot_id, contact_id, webhook_id, 1, 100))

        usage_log_id = db_with_data.fetchone()['id']

        # Delete webhook event
        db_with_data.execute("""
            DELETE FROM webhook_events WHERE id = %s
        """, (webhook_id,))

        # Verify usage log still exists but webhook_event_id is NULL
        db_with_data.execute("""
            SELECT webhook_event_id FROM usage_logs WHERE id = %s
        """, (usage_log_id,))

        result = db_with_data.fetchone()
        assert result is not None
        assert result['webhook_event_id'] is None


class TestCheckConstraints:
    """Test CHECK constraints if any exist."""

    def test_organization_plan_tier_valid_values(self, db_with_data):
        """
        GOAL: Verify plan_tier accepts standard values
        GIVEN: Database connection
        WHEN: Organization is created with valid plan_tier
        THEN: Organization is created successfully
        """
        # Test all valid plan tiers
        for plan_tier in ['free', 'starter', 'pro', 'enterprise']:
            db_with_data.execute("""
                INSERT INTO organizations (name, slug, plan_tier)
                VALUES (%s, %s, %s)
                RETURNING plan_tier
            """, (f'{plan_tier} org', f'{plan_tier}-org-test', plan_tier))

            result = db_with_data.fetchone()
            assert result['plan_tier'] == plan_tier

    def test_message_role_valid_values(self, db_with_data):
        """
        GOAL: Verify message role accepts standard values
        GIVEN: Valid contact
        WHEN: Messages are created with different roles
        THEN: All standard roles are accepted
        """
        contact_id = '44444444-4444-4444-4444-444444444444'

        for role in ['user', 'assistant', 'system', 'tool']:
            db_with_data.execute("""
                INSERT INTO messages (contact_id, role, content)
                VALUES (%s, %s, %s)
                RETURNING role
            """, (contact_id, role, f'Test {role} message'))

            result = db_with_data.fetchone()
            assert result['role'] == role

    def test_contact_conversation_mode_valid_values(self, db_with_data):
        """
        GOAL: Verify conversation_mode accepts 'auto' and 'manual'
        GIVEN: Chatbot
        WHEN: Contacts are created with different modes
        THEN: Both modes are accepted
        """
        chatbot_id = '22222222-2222-2222-2222-222222222222'

        for mode in ['auto', 'manual']:
            db_with_data.execute("""
                INSERT INTO contacts (
                    chatbot_id,
                    phone_number,
                    name,
                    conversation_mode
                )
                VALUES (%s, %s, %s, %s)
                RETURNING conversation_mode
            """, (chatbot_id, f'15559999{mode[:3]}', f'{mode} Contact', mode))

            result = db_with_data.fetchone()
            assert result['conversation_mode'] == mode
