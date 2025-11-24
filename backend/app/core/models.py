from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid
from app.core.database import Base

class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"

class ThreadStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    bins = relationship("KnowledgeBin", back_populates="user", cascade="all, delete-orphan")
    threads = relationship("Thread", back_populates="user", cascade="all, delete-orphan")
    profiles = relationship("StyleProfile", back_populates="user", cascade="all, delete-orphan")

class KnowledgeBin(Base):
    __tablename__ = "knowledge_bins"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    user = relationship("User", back_populates="bins")
    documents = relationship("Document", back_populates="bin", cascade="all, delete-orphan")

class StyleProfile(Base):
    __tablename__ = "style_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tone_urls = Column(JSONB, nullable=True) # List of strings
    style_dna = Column(JSONB, nullable=True) # JSON object
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    user = relationship("User", back_populates="profiles")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bin_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bins.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True) # Path to local file or object storage
    pinecone_id = Column(String, nullable=True)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    bin = relationship("KnowledgeBin", back_populates="documents")

class Thread(Base):
    __tablename__ = "threads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) # This will match the LangGraph thread_id
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    topic = Column(String, nullable=False)
    target_audience = Column(String, nullable=True)
    research_guidelines = Column(Text, nullable=True)
    extra_context = Column(Text, nullable=True)
    status = Column(Enum(ThreadStatus), default=ThreadStatus.RUNNING)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    user = relationship("User", back_populates="threads")

class InternalIndex(Base):
    __tablename__ = "internal_index"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String, index=True, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    last_scraped = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

