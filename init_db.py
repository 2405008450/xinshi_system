"""
数据库表初始化脚本
运行此脚本可以创建所有数据库表
"""
from database import engine
from models import Base

if __name__ == "__main__":
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")
