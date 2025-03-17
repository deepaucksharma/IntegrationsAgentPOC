# src/workflow_agent/storage/models.py
import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ExecutionRecord(Base):
    __tablename__ = "execution_records"

    id = Column(Integer, primary_key=True, index=True)
    target_name = Column(String(255), index=True)
    action = Column(String(50), index=True)
    success = Column(Boolean, default=False)
    execution_time = Column(Integer)  # in milliseconds
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    system_context = Column(Text)  # JSON string
    script = Column(Text)
    output = Column(Text)         # JSON string
    parameters = Column(Text)     # JSON string
    transaction_id = Column(String(36), nullable=True)  # For tracking related operations
    user_id = Column(String(50), nullable=True)  # Who initiated the execution