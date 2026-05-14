from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from bot.models.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True)
    bot_token = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=False)
    welcome_message = Column(Text, nullable=True)
    manager_link = Column(String(255), default="@akovpyat")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Business(id={self.id}, name={self.name}, active={self.is_active})>"