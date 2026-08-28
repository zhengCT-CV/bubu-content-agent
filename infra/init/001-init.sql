CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

SELECT 'CREATE DATABASE bubu_checkpoints OWNER bubu'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'bubu_checkpoints')\gexec

\connect bubu_checkpoints
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
