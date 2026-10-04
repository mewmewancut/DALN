-- Run against fashion as fashion_e1 (the sequence owner), using psql with
-- --single-transaction --set ON_ERROR_STOP=1. Never run as daln_app.
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO daln_app;

-- Apply the same permissions to sequences created by future migrations.
ALTER DEFAULT PRIVILEGES FOR ROLE fashion_e1 IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO daln_app;
