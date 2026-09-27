"""add evidence metadata for auditable RAG retrieval"""
import sqlalchemy as sa
from alembic import op

revision = "4f9d2e7c1b6a"
down_revision = "8a367277d328"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("knowledge_documents", sa.Column("topic", sa.String(length=120), nullable=False, server_default="general"))
    op.add_column("knowledge_documents", sa.Column("evidence_level", sa.String(length=40), nullable=False, server_default="reviewed_general"))
    op.add_column("knowledge_documents", sa.Column("population", sa.String(length=500), nullable=False, server_default="一般成年用户"))
    op.add_column("knowledge_documents", sa.Column("contraindications", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("knowledge_documents", sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("knowledge_documents", "topic", server_default=None)
    op.alter_column("knowledge_documents", "evidence_level", server_default=None)
    op.alter_column("knowledge_documents", "population", server_default=None)
    op.alter_column("knowledge_documents", "contraindications", server_default=None)


def downgrade():
    op.drop_column("knowledge_documents", "review_due_at")
    op.drop_column("knowledge_documents", "contraindications")
    op.drop_column("knowledge_documents", "population")
    op.drop_column("knowledge_documents", "evidence_level")
    op.drop_column("knowledge_documents", "topic")
