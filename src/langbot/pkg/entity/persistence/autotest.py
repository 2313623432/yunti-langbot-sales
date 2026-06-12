import sqlalchemy

from .base import Base


class AutoTestRun(Base):
    """AI self-test run for a pipeline or workflow target."""

    __tablename__ = 'auto_test_runs'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    target_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, index=True)
    target_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    target_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    status = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='completed', index=True)
    scenario = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    messages = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    evaluation = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    user_feedback = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='')
    feedback_reason = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    optimization_summary = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    optimization_patch = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
