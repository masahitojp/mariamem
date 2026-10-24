"""Repository-authored first revision with a row that must survive upgrade."""
from alembic import op
import sqlalchemy as sa

revision = 'm1_initial'
down_revision = None
branch_labels = depends_on = None


def upgrade():
    users = op.create_table('users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.UniqueConstraint('name', name='uq_users_name'),
        mysql_engine='InnoDB')
    op.bulk_insert(users, [{'id': 1, 'name': 'legacy'}])
