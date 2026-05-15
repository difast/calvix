from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.sql import func
from bot.models.database import Base
from sqlalchemy.orm import mapped_column


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    business_id = mapped_column(BigInteger, ForeignKey("businesses.id"))
    scheduled_at = Column(DateTime, nullable=True)
    phone = Column(String(50))
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Booking(id={self.id}, status={self.status})>"