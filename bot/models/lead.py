from sqlalchemy.sql import func
from bot.models.database import Base
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import mapped_column


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    #business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    #telegram_id = Column(BigInteger, nullable=False)
    business_id = mapped_column(BigInteger, ForeignKey("businesses.id"))
    telegram_id = mapped_column(BigInteger)
    username = Column(String(255))
    full_name = Column(String(255))
    status = Column(String(50), default="COLD")
    phone = Column(String(50))
    last_active = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Lead(id={self.id}, business_id={self.business_id}, status={self.status})>"