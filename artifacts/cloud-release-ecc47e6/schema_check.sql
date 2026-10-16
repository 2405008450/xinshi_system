SELECT 'COLUMN', table_name, column_name, data_type, udt_name, is_nullable,
       coalesce(column_default,''), coalesce(character_maximum_length::text,'')
FROM information_schema.columns
WHERE table_schema='public' AND table_name IN ('project_notice_section','project_notice_attachment')
ORDER BY table_name, ordinal_position;
SELECT 'CONSTRAINT', c.relname, pg_get_constraintdef(p.oid), p.convalidated
FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('project_notice_section','project_notice_attachment')
ORDER BY c.relname, pg_get_constraintdef(p.oid);
SELECT 'INDEX', tablename,indexname,indexdef FROM pg_indexes
WHERE schemaname='public' AND tablename IN ('project_notice_section','project_notice_attachment')
ORDER BY tablename,indexname;
