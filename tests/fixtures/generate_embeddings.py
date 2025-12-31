"""
Generate Real Embeddings Fixture

This script generates real embeddings from OpenAI and saves them to a JSON file.
Run this script ONCE to create the fixture, then use the fixture in tests.

Usage:
    OPENAI_API_KEY=your_key python tests/fixtures/generate_embeddings.py

The generated fixture contains:
- Sample document embeddings
- Query embeddings for similarity tests
- Metadata about the embedding model used

This allows tests to use real embeddings without calling the API every time.
"""

import json
import os
from datetime import datetime
from pathlib import Path


def generate_embeddings():
    """Generate embeddings for test documents and save to fixture file."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Usage: OPENAI_API_KEY=your_key python generate_embeddings.py")
        return

    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    # Test documents that simulate real knowledge base content
    test_documents = [
        {
            "id": "doc_1",
            "title": "Return Policy",
            "content": "Our return policy allows returns within 30 days of purchase. "
                       "Items must be in original condition with tags attached."
        },
        {
            "id": "doc_2",
            "title": "Shipping Information",
            "content": "We offer free shipping on orders over $50. "
                       "Standard shipping takes 5-7 business days. "
                       "Express shipping is available for an additional fee."
        },
        {
            "id": "doc_3",
            "title": "Product Warranty",
            "content": "All electronics come with a 1-year manufacturer warranty. "
                       "Extended warranty options are available at checkout."
        },
        {
            "id": "doc_4",
            "title": "Customer Support",
            "content": "Our customer support team is available 24/7. "
                       "You can reach us via chat, email, or phone."
        },
        {
            "id": "doc_5",
            "title": "Payment Methods",
            "content": "We accept all major credit cards, PayPal, and Apple Pay. "
                       "Installment payment options are available for orders over $100."
        }
    ]

    # Test queries for similarity search testing
    test_queries = [
        {
            "id": "query_1",
            "text": "How do I return an item?",
            "expected_match": "doc_1"  # Return Policy
        },
        {
            "id": "query_2",
            "text": "How long does shipping take?",
            "expected_match": "doc_2"  # Shipping Information
        },
        {
            "id": "query_3",
            "text": "What warranty do you offer?",
            "expected_match": "doc_3"  # Product Warranty
        },
        {
            "id": "query_4",
            "text": "How can I contact support?",
            "expected_match": "doc_4"  # Customer Support
        }
    ]

    print("Generating embeddings for test documents...")

    # Generate document embeddings
    doc_embeddings = []
    for doc in test_documents:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=doc["content"]
        )
        doc_embeddings.append({
            "id": doc["id"],
            "title": doc["title"],
            "content": doc["content"],
            "embedding": response.data[0].embedding
        })
        print(f"  Generated embedding for: {doc['title']}")

    print("\nGenerating embeddings for test queries...")

    # Generate query embeddings
    query_embeddings = []
    for query in test_queries:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=query["text"]
        )
        query_embeddings.append({
            "id": query["id"],
            "text": query["text"],
            "expected_match": query["expected_match"],
            "embedding": response.data[0].embedding
        })
        print(f"  Generated embedding for: {query['text']}")

    # Create fixture
    fixture = {
        "metadata": {
            "model": "text-embedding-ada-002",
            "dimensions": 1536,
            "generated_at": datetime.now().isoformat(),
            "description": "Pre-computed embeddings for testing RAG functionality"
        },
        "documents": doc_embeddings,
        "queries": query_embeddings
    }

    # Save to file
    fixture_path = Path(__file__).parent / "embeddings.json"
    with open(fixture_path, "w") as f:
        json.dump(fixture, f, indent=2)

    print(f"\nFixture saved to: {fixture_path}")
    print(f"Documents: {len(doc_embeddings)}")
    print(f"Queries: {len(query_embeddings)}")
    print("\nYou can now use this fixture in tests via the 'real_embeddings' fixture.")


if __name__ == "__main__":
    generate_embeddings()
