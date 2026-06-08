import sqlalchemy

from .base import Base


class SalesProduct(Base):
    """Product information used by the AI sales assistant."""

    __tablename__ = 'sales_products'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    category = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    price = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    link = sqlalchemy.Column(sqlalchemy.String(1024), nullable=False, default='')
    description = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    selling_points = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    pain_points = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    objections = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    audience = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, index=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class SalesCustomerMemory(Base):
    """Long-lived customer memory keyed by platform session."""

    __tablename__ = 'sales_customer_memories'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    platform = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    customer_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    summary = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    stage = sqlalchemy.Column(sqlalchemy.String(64), nullable=False, default='new')
    last_intent = sqlalchemy.Column(sqlalchemy.String(64), nullable=False, default='unknown')
    preferred_product_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    profile = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    intents = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    last_seen_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class SalesHandoff(Base):
    """Human handoff queue item for sessions that need manual sales support."""

    __tablename__ = 'sales_handoffs'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    target_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='person')
    target_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    platform = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    status = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='open', index=True)
    reason = sqlalchemy.Column(sqlalchemy.String(512), nullable=False, default='')
    last_message = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    operator_reply = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    assigned_to = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class SalesOutreachPlan(Base):
    """Scheduled product-link outreach plan."""

    __tablename__ = 'sales_outreach_plans'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    product_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    target_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='person')
    target_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    segment = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    dedupe_key = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='', index=True)
    message_template = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    message_components = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    scheduled_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    interval_minutes = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, index=True)
    last_sent_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
