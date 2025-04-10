from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv
import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
load_dotenv()
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
    order_id: int = Field(..., description="The ID of the order")
    status: str = Field(..., description="The status of the order")
    customer_name: Optional[str] = Field(None, description="The name of the customer")
    amount: Optional[float] = Field(None, description="The amount of the order")