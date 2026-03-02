"""
一次性迁移脚本：创建 employee_leave 表
运行方式：python _migrate_leave.py
"""
from database import engine
from models import Base, EmployeeLeave

if __name__ == '__main__':
    Base.metadata.create_all(engine, tables=[EmployeeLeave.__table__])
    print('employee_leave 表创建成功')
