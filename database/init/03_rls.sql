-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================
-- Políticas de seguridad a nivel de fila para multitenancy
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- ENABLE RLS ON ALL TABLES
-- =====================================================

-- Core tables
ALTER TABLE pulpo.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.messages ENABLE ROW LEVEL SECURITY;

-- Dialogue state tables
ALTER TABLE pulpo.dialogue_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.dialogue_state_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.dialogue_slots ENABLE ROW LEVEL SECURITY;

-- RAG tables
ALTER TABLE pulpo.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.document_chunks ENABLE ROW LEVEL SECURITY;

-- Business logic tables
ALTER TABLE pulpo.business_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.appointments ENABLE ROW LEVEL SECURITY;

-- Monitoring tables
ALTER TABLE pulpo.system_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.error_logs ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- RLS POLICIES - CORE TABLES
-- =====================================================

-- Workspaces: Users can only see workspaces they're members of
CREATE POLICY workspace_member_access ON pulpo.workspaces
  FOR ALL TO public
  USING (
    id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Users: Users can only see themselves
CREATE POLICY user_self_access ON pulpo.users
  FOR ALL TO public
  USING (id = current_setting('pulpo.user_id', true)::uuid);

-- Workspace members: Users can see members of their workspaces
CREATE POLICY workspace_member_list_access ON pulpo.workspace_members
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Channels: Users can see channels of their workspaces
CREATE POLICY channel_workspace_access ON pulpo.channels
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Contacts: Users can see contacts of their workspaces
CREATE POLICY contact_workspace_access ON pulpo.contacts
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Conversations: Users can see conversations of their workspaces
CREATE POLICY conversation_workspace_access ON pulpo.conversations
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Messages: Users can see messages of their workspaces
CREATE POLICY message_workspace_access ON pulpo.messages
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- =====================================================
-- RLS POLICIES - DIALOGUE STATE TABLES
-- =====================================================

-- Dialogue states: Users can see dialogue states of their workspaces
CREATE POLICY dialogue_state_workspace_access ON pulpo.dialogue_states
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Dialogue state history: Users can see history of their workspaces
CREATE POLICY dialogue_history_workspace_access ON pulpo.dialogue_state_history
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Dialogue slots: Users can see slots of their workspaces
CREATE POLICY dialogue_slots_workspace_access ON pulpo.dialogue_slots
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- =====================================================
-- RLS POLICIES - RAG TABLES
-- =====================================================

-- Documents: Users can see documents of their workspaces
CREATE POLICY document_workspace_access ON pulpo.documents
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Document chunks: Users can see chunks of their workspaces
CREATE POLICY document_chunks_workspace_access ON pulpo.document_chunks
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- =====================================================
-- RLS POLICIES - BUSINESS LOGIC TABLES
-- =====================================================

-- Business actions: Users can see actions of their workspaces
CREATE POLICY business_actions_workspace_access ON pulpo.business_actions
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Orders: Users can see orders of their workspaces
CREATE POLICY orders_workspace_access ON pulpo.orders
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Properties: Users can see properties of their workspaces
CREATE POLICY properties_workspace_access ON pulpo.properties
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Appointments: Users can see appointments of their workspaces
CREATE POLICY appointments_workspace_access ON pulpo.appointments
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- =====================================================
-- RLS POLICIES - MONITORING TABLES
-- =====================================================

-- System metrics: Users can see metrics of their workspaces
CREATE POLICY system_metrics_workspace_access ON pulpo.system_metrics
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- Error logs: Users can see errors of their workspaces
CREATE POLICY error_logs_workspace_access ON pulpo.error_logs
  FOR ALL TO public
  USING (
    workspace_id IN (
      SELECT workspace_id 
      FROM pulpo.workspace_members 
      WHERE user_id = current_setting('pulpo.user_id', true)::uuid
    )
  );

-- =====================================================
-- SERVICE ACCOUNT POLICIES
-- =====================================================

-- Create service role for internal services
CREATE ROLE pulpo_service;
GRANT USAGE ON SCHEMA pulpo TO pulpo_service;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA pulpo TO pulpo_service;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA pulpo TO pulpo_service;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pulpo TO pulpo_service;

-- Service accounts bypass RLS for internal operations
CREATE POLICY service_bypass_rls ON pulpo.workspaces
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.users
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.workspace_members
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.channels
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.contacts
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.conversations
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.messages
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.dialogue_states
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.dialogue_state_history
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.dialogue_slots
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.documents
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.document_chunks
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.business_actions
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.orders
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.properties
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.appointments
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.system_metrics
  FOR ALL TO pulpo_service
  USING (true);

CREATE POLICY service_bypass_rls ON pulpo.error_logs
  FOR ALL TO pulpo_service
  USING (true);
