"""Repository-authored dependent revision; optional exact failure injection."""
from alembic import op
import sqlalchemy as sa

revision = 'm2_addresses'
down_revision = 'm1_initial'
branch_labels = depends_on = None


def upgrade():
    op.add_column('users', sa.Column('rating', sa.Integer, nullable=False, server_default='0'))
    if op.get_context().config.attributes.get('fail_revision'):
        op.execute('INSERT INTO missing_revision_oracle(id) VALUES(1)')
    op.create_table('addresses',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('email', sa.String(128), nullable=False),
        sa.UniqueConstraint('email', name='uq_address_email'),
        mysql_engine='InnoDB')
