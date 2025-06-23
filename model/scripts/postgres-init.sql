CREATE USER caddy WITH PASSWORD 'caddy'; -- # pragma: allowlist-secret
ALTER USER caddy CREATEDB;
CREATE DATABASE caddy_local;
GRANT ALL PRIVILEGES ON DATABASE caddy_local TO caddy;

ALTER DATABASE caddy_local OWNER TO caddy;
--needed to create extension
ALTER ROLE caddy SUPERUSER;