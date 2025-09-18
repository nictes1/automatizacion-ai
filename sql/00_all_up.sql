\set ON_ERROR_STOP on
SET search_path = public, pulpo;

-- Core + RLS + policies
\i sql/01_core_up.sql

-- Seed
\i sql/02_seed_dev.sql

-- Functions
\i sql/03_functions.sql

-- Debug views
\i sql/04_views_debug.sql

-- Helpers
\i sql/05_settings_and_helpers.sql

-- Plugins
\i sql/06_plg_up.sql