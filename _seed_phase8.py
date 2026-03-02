"""
第八阶段初始数据种子脚本
- 批量创建内部员工账号（app_user），设置 department / fixed_tasks
- 批量插入外部译员（translator），设置排班相关字段
默认密码：Xinshi@2024
"""
import sys, hashlib, json
sys.stdout.reconfigure(encoding='utf-8')

from database import engine
from sqlalchemy import text

DEFAULT_PASSWORD = hashlib.sha256("Xinshi@2024".encode()).hexdigest()

# ============================================================
# 1. 内部员工数据
#    来源：WorkSchedule.vue deptPersonData + shiftTableData
#    格式：(full_name, username, department, fixed_tasks)
# ============================================================
STAFF = [
    # 项目经理
    ("伟琪",   "weiqic",   "项目经理", []),
    ("李娴",   "lixian",   "项目经理", []),
    ("孟花",   "menghua",  "项目经理", []),
    ("少妃",   "shaofei",  "项目经理", []),

    # 翻译部
    ("陈佳",   "chenjia",  "翻译部", ["银行词汇", "信实翻译 中译小语种 机翻引擎测试"]),
    ("Thomas", "thomas",   "翻译部", []),

    # 项目部
    ("旷姣",   "kuangjiao","项目部", []),

    # 客户部
    ("楚翘",   "chuqiao",  "客户部", []),
    ("雅然",   "yaran",    "客户部", []),
    ("苗丹",   "miaodan",  "客户部", []),
    ("家铭",   "jiaming",  "客户部", []),
    ("黄萌",   "huangmeng","客户部", []),
    ("武哥",   "wuge",     "客户部", []),
    ("靖琳",   "jinglin",  "客户部", []),
    ("辛建",   "xinjian",  "客户部", []),
    ("舒倩",   "shuqian",  "客户部", []),
    ("烨珊",   "yeshan",   "客户部", []),

    # HR部
    ("韵钰",   "yunyu",    "HR部", ["（暂停）项目专员培训资料调整", "（暂停）项目经理培训资料梳理、编写"]),
    ("立溶",   "lirong",   "HR部", []),
    ("舒婷",   "shuting",  "HR部", []),
    ("宇琪",   "yuqi",     "HR部", []),
    ("翠珍",   "cuizhen",  "HR部", []),
    ("紫霞",   "zixia",    "HR部", []),
    ("菀筠",   "wanjun",   "HR部", []),
    ("颖琦",   "yingqi",   "HR部", []),
    ("少洁",   "shaojie",  "HR部", []),
    ("文慧",   "wenhui",   "HR部", []),

    # 排版
    ("运坚",   "yunjian",  "排版", []),
    ("瑞珠",   "ruizhu",   "排版", ["每月专检稽查（梁承敏、沈佳佳）"]),
    ("大杰",   "dajie",    "排版", ["每月专检稽查（贺媛、孙晓燕）"]),
    ("胜辉",   "shenghui", "排版", []),
    ("浚轩",   "junxuan",  "排版", []),
    ("裕林",   "yulin",    "排版", []),
    ("晨旭",   "chenxu",   "排版", []),
    ("美霞",   "meixia",   "排版", []),

    # 招聘项目
    ("振中",   "zhenzhong","招聘项目", []),

    # 销售
    ("以龙",   "yilong",   "销售", []),
    ("志林",   "zhilin",   "销售", []),
    ("泉哥",   "quange",   "销售", []),
]

# ============================================================
# 2. 外部译员数据
#    来源：scheduleDefaultData.js urgentTableZhEn / urgentTableEnZh
#    direction: zh_en / en_zh / both
#    格式：(translator_name, code, direction, translation_type,
#           quality_score, cloud_revision, daily_rate,
#           default_priority, schedule_remarks)
# ============================================================
TRANSLATORS = [
    # ---- 中英 (zh_en) ----
    ("王婷",   "T_wangting",   "zh_en", "全部",   "73", "-",    "5/1000/8000",
     2, "法律类需审改，其他中英要求不是很高的可基本检查"),
    ("高超",   "T_gaochao",    "zh_en", "全部",   "73", "可/可","5/1000/8000",
     1, "大概仅适合银行，法律类需审改"),
    ("孙红艳", "T_sunhy",      "zh_en", "全部",   "74", "可/可","2/500/2000",
     0, "中英要求不高的均可基本检查"),
    ("商莹",   "T_shangying",  "zh_en", "全部",   "74", "可/可","3/500/3000",
     1, "不接法律和医学"),
    ("陈风",   "T_chenfeng",   "zh_en", "全部",   "73", "-",    "?/?/7000",
     0, "需审改"),
    ("雷智",   "T_leizhi",     "zh_en", "全部",   "74", "-",    "?/?/4000",
     2, "需审改"),
    ("何长青", "T_hecq",       "zh_en", "全部",   "74", "-",    "?/?/4000",
     0, "需审改"),
    ("李鲁莎", "T_lilusa",     "zh_en", "全部",   "73", "-",    "?/?/6000",
     1, "需审改"),

    # ---- 英中 (en_zh) ----
    ("史明月", "T_shimy",      "en_zh", "全部（不适合对中文要求高的）", "74", "可/未知", "1/500/4000",
     2, "工作日中午和下午不能做稿，一般需审改"),
    ("杨雪",   "T_yangxue",   "en_zh", "全部（法律类优先）",           "75", "可/未知", "5/350/3000",
     1, "律师，一般需审改"),
    ("梁昌金", "T_liangcj",   "en_zh", "全部",   "75", "可/未知","-",
     1, "一般需审改"),
    ("熊建磊", "T_xiongjl",   "en_zh", "全部",   "75", "可/未知","-",
     1, "一般要审改"),
    ("张留寰", "T_zhanglh",   "en_zh", "全部",   "75", "可/未知","-",
     1, "一般要审改"),
    ("乔艳红", "T_qiaoyh",    "en_zh", "全部",   "75", "可/可", "?/?/7000",
     1, "急稿可不改"),

    # ---- 中英+英中 (both) ----
    # 王邃玲：zh_en priority=3；en_zh N/A（注意优先安排中英）
    ("王邃玲", "T_wangsl",    "both",  "全部",   "80", "可/可", "5/1000/6000",
     3, "法律类需安排审改；英译中质量78，注意优先安排中英项目"),
    # 曹柳云：两方向均 N/A
    ("曹柳云", "T_caoly",     "both",  "全部",   "74", "可/可", "5/500/4000",
     0, "非合同法律类需审改；中英/英中均可"),
]


def seed_staff(conn):
    inserted, skipped = 0, 0
    for full_name, username, dept, fixed_tasks in STAFF:
        # 已有同 username 则只补全 full_name / department / fixed_tasks
        exists = conn.execute(
            text("SELECT id FROM app_user WHERE username = :u"),
            {"u": username}
        ).fetchone()
        if exists:
            conn.execute(
                text("""UPDATE app_user
                        SET full_name   = :fn,
                            department  = :dept,
                            fixed_tasks = :ft
                        WHERE username  = :u"""),
                {"fn": full_name, "dept": dept,
                 "ft": json.dumps(fixed_tasks, ensure_ascii=False), "u": username}
            )
            skipped += 1
        else:
            conn.execute(
                text("""INSERT INTO app_user
                        (username, password_hash, full_name, department, fixed_tasks, is_active)
                        VALUES (:u, :pw, :fn, :dept, :ft, true)"""),
                {"u": username, "pw": DEFAULT_PASSWORD,
                 "fn": full_name, "dept": dept,
                 "ft": json.dumps(fixed_tasks, ensure_ascii=False)}
            )
            inserted += 1
    return inserted, skipped


def seed_translators(conn):
    inserted, skipped = 0, 0
    for (name, code, direction, t_type, quality,
         cloud_rev, daily_rate, priority, remarks) in TRANSLATORS:
        exists = conn.execute(
            text("SELECT id FROM translator WHERE translator_name = :n"),
            {"n": name}
        ).fetchone()
        if exists:
            conn.execute(
                text("""UPDATE translator
                        SET translation_type = :tt,
                            quality_score    = :qs,
                            cloud_revision   = :cr,
                            daily_rate       = :dr,
                            direction        = :dir,
                            default_priority = :prio,
                            schedule_remarks = :rem
                        WHERE translator_name = :n"""),
                {"tt": t_type, "qs": quality, "cr": cloud_rev, "dr": daily_rate,
                 "dir": direction, "prio": priority, "rem": remarks, "n": name}
            )
            skipped += 1
        else:
            conn.execute(
                text("""INSERT INTO translator
                        (translator_code, translator_name, translation_type,
                         quality_score, cloud_revision, daily_rate,
                         direction, default_priority, schedule_remarks)
                        VALUES (:code, :n, :tt, :qs, :cr, :dr, :dir, :prio, :rem)"""),
                {"code": code, "n": name, "tt": t_type, "qs": quality,
                 "cr": cloud_rev, "dr": daily_rate, "dir": direction,
                 "prio": priority, "rem": remarks}
            )
            inserted += 1
    return inserted, skipped


with engine.connect() as conn:
    s_ins, s_upd = seed_staff(conn)
    t_ins, t_upd = seed_translators(conn)
    conn.commit()

print(f"员工账号  — 新建 {s_ins} 条，更新 {s_upd} 条")
print(f"外部译员  — 新建 {t_ins} 条，更新 {t_upd} 条")
print()
print("默认密码：Xinshi@2024（员工首次登录后请自行修改）")
