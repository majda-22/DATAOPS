\set ON_ERROR_STOP on

-- Read passwords from the container environment.
\getenv metadata_password METADATA_DB_PASSWORD
\getenv test_password METADATA_TEST_DB_PASSWORD
\getenv airflow_password AIRFLOW_DB_PASSWORD
\getenv marquez_password MARQUEZ_DB_PASSWORD

-- Application accounts cannot administer the PostgreSQL server.
CREATE ROLE dataops LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE
    PASSWORD :'metadata_password';

CREATE ROLE dataops_test LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE
    PASSWORD :'test_password';

CREATE ROLE airflow LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE
    PASSWORD :'airflow_password';

CREATE ROLE marquez LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE
    PASSWORD :'marquez_password';

CREATE DATABASE dataops_metadata OWNER dataops;
CREATE DATABASE dataops_metadata_test OWNER dataops_test;
CREATE DATABASE airflow OWNER airflow;
CREATE DATABASE marquez OWNER marquez;

-- Remove default access for unrelated accounts.
REVOKE ALL ON DATABASE dataops_metadata FROM PUBLIC;
REVOKE ALL ON DATABASE dataops_metadata_test FROM PUBLIC;
REVOKE ALL ON DATABASE airflow FROM PUBLIC;
REVOKE ALL ON DATABASE marquez FROM PUBLIC;