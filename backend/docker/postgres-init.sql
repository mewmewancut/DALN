SELECT 'CREATE DATABASE fashion_test'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'fashion_test'
)\gexec
