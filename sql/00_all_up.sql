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

-- RAG
\i sql/07_rag_up.sql

-- Vertical Packs & Orchestrator
\i sql/08_vertical_packs_up.sql

-- Orchestrator Functions
\i sql/09_orchestrator_functions.sql

-- Vertical Packs Seed
\i sql/10_vertical_packs_seed.sql

-- File Management System (Improved)
\i sql/11_file_management_improved.sql

-- Raw Files System & Versions
\i sql/12_raw_files_system_fixed.sql