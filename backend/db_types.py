"""
Backend-agnostic GUID column type.

Uses PostgreSQL's native UUID type when available; falls back to CHAR(36) on
SQLite (used for the no-Docker local demo). Unlike SQLAlchemy's built-in
Uuid(as_uuid=True), this accepts both str and uuid.UUID on bind — so query
filters like `Client.id == client_id` work whether client_id came from a
path param (str), a JWT claim (str), or an ORM object (uuid.UUID).
"""
import uuid
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value
