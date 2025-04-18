from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel, Field
from typing import Optional, Literal
from dotenv import load_dotenv
import hmac, hashlib
import datetime
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, nullable=False, default="default") 
    payload = Column(JSON, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

class WebHookPayload(BaseModel):
    order_id: int = Field(..., gt=0, description="The ID of the order")
    status: Literal['created', 'pending', 'failed'] = Field(..., description="Allowed: created, pending, failed")
    customer_name: Optional[str] = Field(None, min_length=3, max_length=15, description="The name of the customer")
    amount: Optional[float] = Field(None, description="The amount of the order")

def verify_hmac(secret: str, body:bytes, signature: str) -> bool:
    computed = hmac.new(
        key = secret.encode('utf-8'),
        msg = body,
        digestmod = hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)