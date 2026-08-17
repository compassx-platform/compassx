-- CompassX databases (created once on first postgres container start).
CREATE DATABASE compassx_account;
CREATE DATABASE compassx_system;
CREATE DATABASE asset_manager;
CREATE DATABASE airflow_meta;
CREATE DATABASE landing_zone;
CREATE DATABASE test;

\c compassx_account;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\c compassx_system;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
