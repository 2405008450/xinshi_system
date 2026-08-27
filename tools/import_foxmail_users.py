"""将 Foxmail 公司地址簿安全导入 app_user。

默认仅预览；传入 --apply 后才会在单个数据库事务中写入。
已存在账号只更新邮箱，避免改动历史任务依赖的用户名、姓名、部门、密码和角色。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import secrets
import sys
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import engine


PROFILES = {
    "media_m-spec@xinshifanyi.com.cn": ("邵浚轩", "其他", "junxuan"),
    "service3@xinshifanyi.com.cn": ("刘家铭", "销售", "jiaming"),
    "trans4@xinshifanyi.com.cn": ("彭孟花", "项目部", "menghua"),
    "trans15@xinshifanyi.com.cn": ("李振中", "项目部", "zhenzhong"),
    "trans9@xinshifanyi.com.cn": ("旷姣", "项目部", "kuangjiao"),
    "trans8@xinshifanyi.com.cn": ("卢少妃", "项目经理", "shaofei"),
    "carol@xinshifanyi.com.cn": ("欧阳靖琳", "客户部", "jinglin"),
    "trans10@xinshifanyi.com.cn": ("李娴", "项目部", "lixian"),
    "pb01@xinshifanyi.com.cn": ("麦瑞珠", "排版", "ruizhu"),
    "pb02@xinshifanyi.com.cn": ("陈大杰", "排版", "dajie"),
    "hr2@xinshifanyi.com.cn": ("钟楚翘", "客户部", "chuqiao"),
    "service9@xinshifanyi.com.cn": ("杨绍娇", "客户部", None),
    "service7@xinshifanyi.com.cn": ("严韵", "客户部", None),
    "sales3@xinshifanyi.com.cn": ("熊旺", "客户部", None),
    "service16@xinshifanyi.com.cn": ("肖景瀚", "客户部", None),
    "service11@xinshifanyi.com.cn": ("刘星宇", "客户部", None),
    "service14@xinshifanyi.com.cn": ("林楷翔", "客户部", None),
    "service15@xinshifanyi.com.cn": ("黎涛", "客户部", None),
    "service6@xinshifanyi.com.cn": ("黄萌", "客户部", "huangmeng"),
    "service5@xinshifanyi.com.cn": ("冯家俊", "客户部", None),
    "sales@xinshifanyi.com.cn": ("仇志荣", "客户部", None),
    "service13@xinshifanyi.com.cn": ("陈伟豪", "客户部", None),
    "service8@xinshifanyi.com.cn": ("吴美霞", "客户部", "meixia"),
    "tech002@xinshifanyi.com.cn": ("李胜辉", "IT部", "shenghui"),
    "tech@xinshifanyi.com.cn": ("黄运坚", "IT部", None),
    "luke@xinshifanyi.com.cn": ("郭以龙", "销售", "yilong"),
    "trans3@xinshifanyi.com.cn": ("麦韵钰", "项目经理", "yunyu"),
    "trans7@xinshifanyi.com.cn": ("陈佳", "项目经理", "chenjia"),
    "lulu@xinshify.com.cn": ("Lulu", "其他", None),
    "thomas@xinshifanyi.com.cn": ("Thomas", "翻译部", "thomas"),
    "shen@xinshifanyi.com.cn": ("shen", "其他", None),
    "service12@xinshifanyi.com.cn": ("钟裕林", "IT部", "yulin"),
    "service10@xinshifanyi.com.cn": ("习晨旭", "IT部", "chenxu"),
    "hr8@xinshifanyi.com.cn": ("邬颖琦", "HR部", "yingqi"),
    "hr7@xinshifanyi.com.cn": ("彭舒婷", "HR部", "shuting"),
    "hr5@xinshifanyi.com.cn": ("梁翠珍", "HR部", "cuizhen"),
    "hr10@xinshifanyi.com.cn": ("李宇琪", "HR部", "yuqi"),
    "hr9@xinshifanyi.com.cn": ("黄菀筠", "HR部", "wanjun"),
    "hr4@xinshifanyi.com.cn": ("曾紫霞", "HR部", "zixia"),
    "hr@xinshifanyi.com.cn": ("蔡少洁", "HR部", "shaojie"),
    "hr3@xinshifanyi.com.cn": ("郑立溶", "HR部", "lirong"),
    "ethan@xinshifanyi.com.cn": ("Ethan", "其他", None),
    "erichuang@xinshifanyi.com.cn": ("黄崇本", "其他", None),
    "williamzhao@xinshifanyi.com.cn": ("赵震锋", "其他", None),
    "service18@xinshifanyi.com.cn": ("余钟毓", "客户部", None),
    "service17@xinshifanyi.com.cn": ("段毅", "客户部", None),
    "trans12@xinshifanyi.com.cn": ("陈静玲", "项目部", None),
    "jz@xinshifanyi.com.cn": ("jz", "其他", None),
    "trans6@xinshifanyi.com.cn": ("陈依琳", "项目部", None),
}

USERNAME_OVERRIDES = {
    # sales 已是系统通用角色账号，不能占用。
    "sales@xinshifanyi.com.cn": "zhirong",
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    normalized = hashlib.sha256(raw).hexdigest() if len(raw) > 72 else password
    return pwd_context.hash(normalized)


def load_contacts(path: Path) -> dict[str, str]:
    with path.open("r", encoding="gb18030", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["姓名", "电子邮件地址"]:
            raise ValueError(f"CSV 表头不符合预期：{reader.fieldnames!r}")
        rows = list(reader)

    contacts: dict[str, str] = {}
    for row_number, row in enumerate(rows, start=2):
        email = (row["电子邮件地址"] or "").strip().lower()
        source_name = (row["姓名"] or "").strip()
        if not email or "@" not in email:
            raise ValueError(f"第 {row_number} 行邮箱无效：{email!r}")
        if email in contacts:
            raise ValueError(f"第 {row_number} 行邮箱重复：{email}")
        contacts[email] = source_name

    expected = set(PROFILES)
    actual = set(contacts)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(f"CSV 内容与已核对清单不一致；缺少={missing}，新增={unexpected}")
    return contacts


def choose_username(email: str, occupied: set[str]) -> str:
    base = USERNAME_OVERRIDES.get(email, email.split("@", 1)[0].lower())
    candidate = base
    suffix = 2
    while candidate.lower() in occupied:
        candidate = f"{base}{suffix}"
        suffix += 1
    occupied.add(candidate.lower())
    return candidate


def run(path: Path, apply_changes: bool) -> None:
    contacts = load_contacts(path)
    with engine.connect() as connection:
        current = connection.execute(
            text("SELECT id, username, email FROM app_user ORDER BY username")
        ).mappings().all()
        by_username = {row["username"].lower(): row for row in current}
        by_email = {
            row["email"].strip().lower(): row
            for row in current
            if row["email"] and row["email"].strip()
        }
        occupied = set(by_username)

        updates = []
        inserts = []
        for email in contacts:
            full_name, department, existing_username = PROFILES[email]
            existing = by_email.get(email)
            if existing is None and existing_username:
                existing = by_username.get(existing_username.lower())
                if existing is None:
                    raise ValueError(f"预期账号不存在：{existing_username}（{email}）")
            if existing is not None:
                if (existing["email"] or "").strip().lower() != email:
                    updates.append((existing["id"], existing["username"], email))
                continue

            username = choose_username(email, occupied)
            inserts.append((username, full_name, email, department))

        print(f"源记录：{len(contacts)}；更新邮箱：{len(updates)}；新建账号：{len(inserts)}")
        for _, username, email in updates:
            print(f"UPDATE\t{username}\t{email}")
        for username, full_name, email, department in inserts:
            print(f"INSERT\t{username}\t{full_name}\t{email}\t{department}")

        if not apply_changes:
            print("DRY_RUN：未写入数据库。")
            return

        # 前面的预检 SELECT 会触发 SQLAlchemy autobegin；写入前结束只读事务。
        connection.rollback()
        transaction = connection.begin()
        try:
            for user_id, _, email in updates:
                connection.execute(
                    text("UPDATE app_user SET email=:email, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
                    {"id": user_id, "email": email},
                )
            for username, full_name, email, department in inserts:
                password_hash = hash_password(secrets.token_urlsafe(32))
                connection.execute(
                    text(
                        """
                        INSERT INTO app_user
                            (username, password_hash, full_name, email, is_active, department)
                        VALUES
                            (:username, :password_hash, :full_name, :email, true, :department)
                        """
                    ),
                    {
                        "username": username,
                        "password_hash": password_hash,
                        "full_name": full_name,
                        "email": email,
                        "department": department,
                    },
                )
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        print("APPLIED：事务已提交。")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--apply", action="store_true", help="确认写入数据库")
    args = parser.parse_args()
    run(args.csv_path.resolve(), args.apply)


if __name__ == "__main__":
    main()
