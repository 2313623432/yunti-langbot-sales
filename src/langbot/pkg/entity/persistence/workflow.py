import sqlalchemy

from .base import Base


class WorkflowFolder(Base):
    """Folder used by the workflow library page."""

    __tablename__ = 'workflow_folders'

    name = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WorkflowProject(Base):
    """Saved workflow canvas from the workflow library page."""

    __tablename__ = 'workflow_projects'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    folder = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True, default='我的项目')
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    description = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    workflow = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
