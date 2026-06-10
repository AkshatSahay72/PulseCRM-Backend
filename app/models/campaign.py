from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    subject = Column(String(255), nullable=True)
    message_template = Column(Text, nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="draft", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    segment = relationship("Segment", back_populates="campaigns")
    communication_logs = relationship("CommunicationLog", back_populates="campaign", cascade="all, delete-orphan")


class CommunicationLog(Base):
    __tablename__ = "communication_logs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaign = relationship("Campaign", back_populates="communication_logs")
    customer = relationship("Customer", back_populates="communication_logs")
    events = relationship("CampaignEvent", back_populates="log", cascade="all, delete-orphan")


class CampaignEvent(Base):
    __tablename__ = "campaign_events"

    id = Column(Integer, primary_key=True, index=True)
    communication_log_id = Column(Integer, ForeignKey("communication_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(20), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    log = relationship("CommunicationLog", back_populates="events")
