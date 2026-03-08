-- Initialize Pensy database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create database if running standalone (docker-compose creates it via env vars)
-- CREATE DATABASE pensy;
