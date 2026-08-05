-- 将译员初次沟通字段由纯日期升级为日期时间，保留已有日期并补零点时间。
ALTER TABLE translator
    ALTER COLUMN first_contact_date TYPE timestamp without time zone
    USING first_contact_date::timestamp without time zone;
