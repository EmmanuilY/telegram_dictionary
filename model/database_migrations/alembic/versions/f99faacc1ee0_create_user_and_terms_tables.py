"""create user and terms tables

Revision ID: f99faacc1ee0
Revises: 
Create Date: 2023-05-03 17:54:39.828359

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f99faacc1ee0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
           CREATE TYPE   roles AS ENUM ('common', 'admin', 'supervisor');
       """
    )
    op.execute(
        """
           CREATE TYPE  type_object AS ENUM ('english_word', 'term');
       """
    )
    op.execute(
        """
           CREATE TYPE  step_of_learning AS ENUM ('learning', 'repeat', 'learned');
       """
    )

    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
      CREATE TABLE  IF NOT EXISTS  users (
      user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      name VARCHAR(120) NOT NULL,
      created_at TIMESTAMP DEFAULT NOW(),
      role roles DEFAULT 'common',
      telegram_id VARCHAR(255) UNIQUE 
      );
    """)
    op.execute(
        """
                   CREATE TABLE IF NOT EXISTS terms (
                       term_id SERIAL PRIMARY KEY,
                       term varchar(255) NOT NULL ,
                       definition varchar(255) NOT NULL,
                       type type_object NOT NULL 
                      );
               """
    )

    op.execute(
        """
                   CREATE TABLE IF NOT EXISTS user_terms_progress (
                       term_id SERIAL REFERENCES terms(term_id),
                       user_id uuid REFERENCES users (user_id),
                       number_of_repetitions INT DEFAULT 0,
                       learning step_of_learning DEFAULT 'learning',
                       PRIMARY KEY (term_id, user_id)
                      );
               """
    )




def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS terms;
        DROP TABLE IF EXISTS user_terms_progress;
        DROP TYPE IF EXISTS roles;
        DROP TYPE IF EXISTS type_object;
        DROP TYPE IF EXISTS step_of_learning;
    """)
