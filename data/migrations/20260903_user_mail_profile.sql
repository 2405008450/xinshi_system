BEGIN;

CREATE TABLE IF NOT EXISTS user_mail_profile (
    user_id UUID PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    recipient_display_name VARCHAR(255) NULL,
    signature_html TEXT NULL,
    signature_text TEXT NULL,
    signature_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by UUID NULL REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

WITH address_book(email, display_name) AS (
    VALUES
        ('carol@xinshifanyi.com.cn', '信实翻译-Carol 欧阳靖琳'),
        ('erichuang@xinshifanyi.com.cn', '信实翻译-Eric 黄崇本'),
        ('ethan@xinshifanyi.com.cn', '信实翻译-Ethan'),
        ('hr10@xinshifanyi.com.cn', '信实翻译-HR专员李宇琪'),
        ('hr2@xinshifanyi.com.cn', '信实翻译-客户专员钟楚翘'),
        ('hr3@xinshifanyi.com.cn', '信实翻译-HR/行政专员郑立溶'),
        ('hr4@xinshifanyi.com.cn', '信实翻译-HR专员曾紫霞'),
        ('hr5@xinshifanyi.com.cn', '信实翻译-HR专员梁翠珍'),
        ('hr7@xinshifanyi.com.cn', '信实翻译-HR专员彭舒婷'),
        ('hr8@xinshifanyi.com.cn', '信实翻译-HR专员邬颖琦'),
        ('hr9@xinshifanyi.com.cn', '信实翻译-HR专员黄菀筠'),
        ('hr@xinshifanyi.com.cn', '信实翻译-HR专员蔡少洁'),
        ('jz@xinshifanyi.com.cn', 'jz'),
        ('luke@xinshifanyi.com.cn', '信实翻译公司 郭以龙 Luke'),
        ('lulu@xinshify.com.cn', '信实翻译-财务Lulu'),
        ('media_m-spec@xinshifanyi.com.cn', '信实翻译-新媒体运营专员邵浚轩'),
        ('pb01@xinshifanyi.com.cn', '信实翻译-排版专员麦瑞珠'),
        ('pb02@xinshifanyi.com.cn', '信实翻译-排版专员陈大杰'),
        ('sales3@xinshifanyi.com.cn', '信实翻译-客户专员熊旺'),
        ('sales@xinshifanyi.com.cn', '信实翻译-客户专员仇志荣'),
        ('service10@xinshifanyi.com.cn', '信实翻译-IT技术习晨旭'),
        ('service11@xinshifanyi.com.cn', '信实翻译-客户专员刘星宇'),
        ('service12@xinshifanyi.com.cn', '信实翻译-IT技术钟裕林'),
        ('service13@xinshifanyi.com.cn', '信实翻译-客户专员陈伟豪'),
        ('service14@xinshifanyi.com.cn', '信实翻译-客户专员林楷翔'),
        ('service15@xinshifanyi.com.cn', '信实翻译-客户专员黎涛'),
        ('service16@xinshifanyi.com.cn', '信实翻译-客户专员肖景瀚'),
        ('service17@xinshifanyi.com.cn', '信实翻译-客户专员段毅'),
        ('service18@xinshifanyi.com.cn', '信实翻译-客户专员余钟毓'),
        ('service3@xinshifanyi.com.cn', '信实翻译-销售专员刘家铭'),
        ('service5@xinshifanyi.com.cn', '信实翻译-客户专员冯家俊'),
        ('service6@xinshifanyi.com.cn', '信实翻译-客户专员黄萌'),
        ('service7@xinshifanyi.com.cn', '信实翻译-客户专员严韵'),
        ('service8@xinshifanyi.com.cn', '信实翻译-客户部吴美霞'),
        ('service9@xinshifanyi.com.cn', '信实翻译-客户专员杨绍娇'),
        ('shen@xinshifanyi.com.cn', '信实翻译-shen'),
        ('tech002@xinshifanyi.com.cn', '信实翻译-技术李胜辉'),
        ('tech@xinshifanyi.com.cn', '信实翻译-技术黄运坚'),
        ('thomas@xinshifanyi.com.cn', '信实翻译-Thomas'),
        ('trans10@xinshifanyi.com.cn', '信实翻译-项目李娴'),
        ('trans12@xinshifanyi.com.cn', '信实翻译-项目部陈静玲'),
        ('trans15@xinshifanyi.com.cn', '信实翻译-项目专员李振中'),
        ('trans3@xinshifanyi.com.cn', '信实翻译-大项目经理麦韵钰'),
        ('trans4@xinshifanyi.com.cn', '信实翻译-项目专员彭孟花'),
        ('trans6@xinshifanyi.com.cn', '信实翻译-项目部陈依琳'),
        ('trans7@xinshifanyi.com.cn', '信实翻译-项目部罗德胜'),
        ('trans8@xinshifanyi.com.cn', '信实翻译-项目卢少妃'),
        ('trans9@xinshifanyi.com.cn', '信实翻译-项目专员旷姣'),
        ('williamzhao@xinshifanyi.com.cn', '信实翻译_赵震锋_William')
)
INSERT INTO user_mail_profile (user_id, recipient_display_name)
SELECT user_row.id, address_book.display_name
FROM address_book
JOIN app_user AS user_row ON lower(btrim(user_row.email)) = address_book.email
ON CONFLICT (user_id) DO UPDATE
SET recipient_display_name = EXCLUDED.recipient_display_name,
    updated_at = CURRENT_TIMESTAMP;

COMMIT;
