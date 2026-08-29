\set ON_ERROR_STOP on
CREATE TEMP TABLE inventory_counts (
    table_name text PRIMARY KEY,
    row_count bigint NOT NULL
);

SELECT format(
    'INSERT INTO inventory_counts SELECT %L, count(*) FROM %I.%I;',
    schemaname || '.' || tablename,
    schemaname,
    tablename
)
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY schemaname, tablename
\gexec

COPY (
    SELECT table_name, row_count
    FROM inventory_counts
    ORDER BY table_name
) TO STDOUT WITH (FORMAT csv);
