-- Run as a PostgreSQL admin user on the database server.
-- Replace CHANGE_ME with a generated strong password before use.

CREATE DATABASE lyra_chat_router;

CREATE USER chat_router WITH PASSWORD 'CHANGE_ME';
GRANT CONNECT ON DATABASE lyra_chat_router TO chat_router;

\connect lyra_chat_router

GRANT USAGE, CREATE ON SCHEMA public TO chat_router;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chat_router;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chat_router;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chat_router;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO chat_router;
