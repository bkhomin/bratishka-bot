from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Text, DateTime, ForeignKey, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base
import uuid


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    telegram_username = Column(String(100))
    phone = Column(String(20))
    email = Column(String(255))
    domain_login = Column(String(100))
    role_id = Column(Integer, ForeignKey("user_roles.id"), default=1)
    is_registered = Column(Boolean, default=False)
    ldap_verified = Column(Boolean, default=False)
    last_activity = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Связи
    role = relationship("UserRole", back_populates="users")
    messages = relationship("Message", back_populates="user")
    chat_participations = relationship("ChatParticipant", back_populates="user")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    chat_type = Column(String(50), nullable=False)
    title = Column(String(255))
    description = Column(Text)
    last_message_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Связи
    messages = relationship("Message", back_populates="chat")
    participants = relationship("ChatParticipant", back_populates="chat")
    contexts = relationship("ConversationContext", back_populates="chat")


class ChatParticipant(Base):
    __tablename__ = "chat_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Связи
    chat = relationship("Chat", back_populates="participants")
    user = relationship("User", back_populates="chat_participations")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_message_id = Column(BigInteger, nullable=False)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    content = Column(Text, nullable=False)
    content_hash = Column(CHAR(64))
    message_type = Column(String(50), default="text")
    is_bot_message = Column(Boolean, default=False)
    is_reply = Column(Boolean, default=False)
    reply_to_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"))
    user_registered = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Связи
    chat = relationship("Chat", back_populates="messages")
    user = relationship("User", back_populates="messages")
    reply_to = relationship("Message", remote_side=[id])


class ConversationContext(Base):
    __tablename__ = "conversation_contexts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"))
    context_summary = Column(Text)
    participants_count = Column(Integer, default=0)
    message_count = Column(Integer, default=0)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    context_hash = Column(CHAR(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Связи
    chat = relationship("Chat", back_populates="contexts")


class RegistrationSession(Base):
    __tablename__ = "registration_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    chat_id = Column(BigInteger, nullable=False)
    current_step = Column(String(50), default="first_name")
    session_data = Column(JSONB, default={})
    expires_at = Column(DateTime(timezone=True), server_default=func.now() + func.make_interval(0, 0, 0, 0, 0, 30))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
