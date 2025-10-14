"""Ensure textchunks are in qdrant
Revision ID: 37b0cb83d755
Revises: 340fc40a6965
Create Date: 2025-09-12 11:15:36.338102
"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy.vector import VECTOR
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, SparseVector
from sqlalchemy.orm import Session

from alembic import op
from api.environment import config
from api.models import Resource, TextChunk

# revision identifiers, used by Alembic.
revision: str = "37b0cb83d755"  # pragma: allowlist secret
down_revision: Union[str, None] = "340fc40a6965"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def check_and_create_qdrant_points():
    """Check if TextChunk points exist in Qdrant and create missing ones."""

    connection = op.get_bind()
    session = Session(connection)
    op.drop_column("textchunk", "embedding")

    try:
        text_chunks = session.query(TextChunk).join(Resource).all()

        if not text_chunks:
            print("No TextChunks found in database")
            return

        print(f"Found {len(text_chunks)} TextChunks to check")

        client = config.get_sync_qdrant_client()
        try:
            existing_chunk_ids = get_existing_chunk_ids(client)
            print(f"Found {len(existing_chunk_ids)} existing points in Qdrant")

            missing_chunks = []
            for chunk in text_chunks:
                if str(chunk.id) not in existing_chunk_ids:
                    missing_chunks.append(chunk)

            print(f"Found {len(missing_chunks)} missing chunks to create")

            if missing_chunks:
                create_missing_points(client, missing_chunks, session)
                print(f"Successfully created {len(missing_chunks)} missing points")
            else:
                print("All chunks already exist in Qdrant")
        finally:
            client.close()

    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        session.close()


def get_existing_chunk_ids(client: QdrantClient) -> set[str]:
    """Get all existing chunk_id values from Qdrant."""
    existing_ids = set()

    try:
        offset = None

        while True:
            scroll_result = client.scroll(
                collection_name=config.qdrant_collection_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            points, next_offset = scroll_result

            if not points:
                break

            for point in points:
                chunk_id = point.payload.get("chunk_id")
                if chunk_id:
                    existing_ids.add(str(chunk_id))

            if next_offset is None:
                break

            offset = next_offset

    except Exception as e:
        print(f"Error getting existing chunk IDs: {e}")
        return set()

    return existing_ids


def create_missing_points(
    client: QdrantClient, missing_chunks: list[TextChunk], session: Session
):
    """Create Qdrant points for missing TextChunks."""

    points_to_create = []

    for chunk in missing_chunks:
        try:
            # Generate dense vector as it already overlaps from the chunking
            dense_embeddings = config.embedding_model.embed_documents([chunk.text])

            # Generate sparse vector for chunks without it
            sparse_embedder = config.get_embedding_handler()
            sparse_embeddings = list(sparse_embedder.embed(chunk.text))
            sparse_embedding = sparse_embeddings[0]

            # Create new point
            point = PointStruct(
                id=str(chunk.id),
                vector={
                    "text_sparse": SparseVector(
                        indices=sparse_embedding.indices,
                        values=sparse_embedding.values,
                    ),
                    "text_dense": dense_embeddings[0],
                },
                payload={
                    "text": chunk.text,
                    "created_at": chunk.resource.created_at.isoformat()
                    if isinstance(chunk.resource.created_at, datetime)
                    else chunk.resource.created_at,
                    "filename": chunk.resource.filename,
                    "content_type": chunk.resource.content_type,
                    "resource_id": str(chunk.resource.id),
                    "collection_id": str(chunk.resource.collection_id),
                    "chunk_id": str(chunk.id),
                },
            )
            points_to_create.append(point)

        except Exception as e:
            print(f"Error creating point for chunk {chunk.id}: {e}")
            session.rollback()
            continue

    if points_to_create:
        batch_size = 100
        for i in range(0, len(points_to_create), batch_size):
            batch = points_to_create[i : i + batch_size]
            try:
                client.upsert(
                    collection_name=config.qdrant_collection_name, points=batch
                )
                print(f"Created batch {i // batch_size + 1}: {len(batch)} points")
            except Exception as e:
                print(f"Error creating batch {i // batch_size + 1}: {e}")
                session.rollback()
                raise


def upgrade() -> None:
    """Run the migration to sync TextChunks to Qdrant."""
    print("Starting Qdrant sync migration...")

    # Initialize Qdrant collections synchronously
    client = config.get_sync_qdrant_client()
    # Check if collection exists, if not this will raise an exception
    try:
        client.get_collection(config.qdrant_collection_name)
    except Exception:
        # Collection doesn't exist, it should be created elsewhere
        print(f"Collection {config.qdrant_collection_name} should already exist")

    check_and_create_qdrant_points()

    print("Qdrant sync migration completed")


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "textchunk",
        sa.Column("embedding", VECTOR(dim=1024), nullable=True, default=None),
    )
    # ### end Alembic commands ###
