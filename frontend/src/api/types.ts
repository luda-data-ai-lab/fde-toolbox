export type Role = "luda_admin" | "fde" | "client_admin" | "client_user";

export interface Base {
  id: string;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
}
export interface Page<T> {
  items: T[];
  next_cursor?: string | null;
}
export interface User extends Base {
  email: string;
  name: string;
  role: Role;
  home_tenant_id: string | null;
  is_active: boolean;
}
export interface UserAdmin extends User {
  tenant_ids: string[];
}
export interface TenantBrief {
  id: string;
  name: string;
  code: string;
  status: string;
}
export interface Me {
  user: User;
  tenants: TenantBrief[];
  adapters_allowed: boolean;
}
export interface Tenant extends Base {
  name: string;
  code: string;
  status: string;
  deployment_mode: string;
  notes: string | null;
}
export interface Engagement extends Base {
  tenant_id: string;
  name: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  lead_fde_id: string | null;
  description: string | null;
}
export interface System extends Base {
  tenant_id: string;
  name: string;
  short_name: string | null;
  type: string;
  owner_dept: string | null;
  hosting: string | null;
  db_type: string | null;
  notes: string | null;
}
export interface StoredFile extends Base {
  tenant_id: string;
  owner_type: string | null;
  owner_id: string | null;
  filename: string;
  mime: string;
  size: number;
  sha256: string;
}
export interface AuditLog {
  id: string;
  tenant_id: string | null;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown>;
  ip: string | null;
  at: string;
}
export interface AssetRef {
  asset_id: string;
  version: number;
}
export interface Asset extends Base, AssetRef {
  asset_type: string;
  asset_key: string;
  title: string;
  payload: Record<string, unknown>;
  status: string;
  change_note: string | null;
}
export interface AssetSummary {
  asset_id: string;
  asset_type: string;
  asset_key: string;
  title: string;
  latest_version: number;
  latest_status: string;
  versions: number;
}
export interface AssetDiff {
  asset_id: string;
  from_version: number;
  to_version: number;
  payload_diff: string;
  prompt_diff: string | null;
}
export interface Project extends Base {
  tenant_id: string;
  engagement_id: string;
  name: string;
  description: string | null;
  status: string;
  stack: string | null;
  repo_url: string | null;
  env_notes: string | null;
  deploy_notes: string | null;
  spec_document_ids: string[];
}
export interface Task extends Base {
  tenant_id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: string;
  assignee_id: string | null;
  due: string | null;
  pause_note: string | null;
  resume_note: string | null;
}
export type TaskStatus = "todo" | "in_progress" | "review" | "done" | "on_hold";
export interface Prompt extends Base {
  task_id: string;
  tool: string;
  prompt: string;
  result_summary: string | null;
  at: string;
}
export interface ProjectDashboard {
  project: Project;
  status_counts: Record<string, number>;
  total_tasks: number;
  progress: number;
  overdue_tasks: Task[];
  paused_tasks: Task[];
  recent_prompts: Prompt[];
}
export interface EvalCase extends Base, AssetRef {
  name: string;
  input: string;
  expected: string;
  criteria: string | null;
}
export interface EvalResult {
  case_id: string;
  passed: boolean;
  note?: string | null;
}
export interface EvalRun extends Base {
  template_ref: AssetRef;
  run_at: string;
  results: EvalResult[];
  evidence_file_ids: string[];
  notes: string | null;
  pass_rate?: number | null;
}
export interface Instance extends Base {
  tenant_id: string;
  name: string;
  template_ref: AssetRef;
  engagement_id: string;
  deployment: string;
  system_ids: string[];
  overrides: Record<string, unknown>;
  status: string;
  owner_id: string | null;
  dev_project_id: string | null;
  notes: string | null;
}
export interface TenantHome {
  tenant_id: string;
  name: string;
  code: string;
  engagements: { id: string; name: string; status: string }[];
  devtracker: {
    open_tasks?: number;
    paused_tasks?: Task[];
    recent_tasks?: Task[];
  };
  agenthub: { instances_by_status?: Record<string, number> };
}
export interface Home {
  role: Role;
  totals: Record<string, number>;
  tenants: TenantHome[];
}
export type LinkType = "db_link" | "api" | "file" | "mq" | "eai" | "other";
export type InterfaceStatus =
  "planned" | "developing" | "operating" | "retired";
export interface Interface extends Base {
  tenant_id: string;
  if_code: string;
  name: string;
  source_system_id: string;
  target_system_id: string;
  link_type: LinkType;
  schedule: string | null;
  description: string | null;
  daily_volume: number | null;
  owner: string | null;
  status: InterfaceStatus;
  notes: string | null;
}
export interface UploadRow {
  row: number;
  values: Record<string, string | number | null>;
  errors: { field: string; code: string }[];
  unregistered: string[];
  action: "create" | "update" | "error";
}
export interface UnregisteredSystem {
  name: string;
  rows: number;
  in_system_sheet: boolean;
  system: { name: string; type: string; short_name?: string | null };
}
export interface InterfaceUpload extends Base {
  file_id: string;
  status: "validated" | "applied";
  result: {
    filename: string;
    summary: {
      total: number;
      valid: number;
      invalid: number;
      create: number;
      update: number;
    };
    rows: UploadRow[];
    unregistered_systems: UnregisteredSystem[];
    applied?: {
      created: number;
      updated: number;
      skipped: { row: number; if_code: string; code: string }[];
      systems_created: string[];
    };
  };
}
export interface InterfaceDashboard {
  total: number;
  by_link_type: Record<string, number>;
  by_status: Record<string, number>;
  by_system: {
    system_id: string;
    name: string;
    outgoing: number;
    incoming: number;
  }[];
}
export interface GraphNode {
  id: string;
  name: string;
  short_name: string | null;
  type: string;
  degree: number;
}
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  if_code: string;
  name: string;
  link_type: LinkType;
  status: InterfaceStatus;
}
export interface InterfaceGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type SessionType = "interview" | "coaching";
export type DiscoverySessionStatus = "planned" | "in_progress" | "done";
export type ActionStatus = "open" | "in_progress" | "done" | "cancelled";
export interface QuestionRef {
  asset_id: string;
  version: number;
  question_id: string;
}
export interface BankQuestion {
  id: string;
  text: string;
  tags: string[];
  audience: string[];
  follow_ups: string[];
}
export interface BankCategory {
  key: string;
  name: string;
  questions: BankQuestion[];
}
export interface QuestionBank {
  asset_id: string;
  version: number;
  title: string;
  session_types: Record<string, string[]>;
  audiences: string[];
  categories: BankCategory[];
}
export interface QuestionBankResponse {
  bank: QuestionBank | null;
  banks: { asset_id: string; version: number; title: string }[];
}
export interface DiscoverySubject extends Base {
  engagement_id: string;
  name: string;
  department: string | null;
  job_title: string | null;
  system_ids: string[];
  notes: string | null;
}
export interface CustomQuestion extends Base {
  engagement_id: string | null;
  category: string | null;
  text: string;
  tags: string[];
  audience: string[];
  follow_ups: string[];
  source_ref: QuestionRef | null;
}
export interface DiscoverySession extends Base {
  engagement_id: string;
  type: SessionType;
  subject_id: string | null;
  title: string;
  session_date: string | null;
  status: DiscoverySessionStatus;
  summary: string | null;
}
export interface SessionQuestion extends Base {
  session_id: string;
  question_ref: QuestionRef | null;
  custom_question_id: string | null;
  custom_text: string | null;
  text: string;
  category: string | null;
  follow_ups: string[];
  answer: string | null;
  position: number;
}
export interface DiscoveryInsight extends Base {
  session_id: string;
  session_question_id: string | null;
  text: string;
  tags: string[];
}
export interface DiscoveryActionItem extends Base {
  session_id: string;
  insight_id: string | null;
  title: string;
  assignee: string | null;
  due: string | null;
  status: ActionStatus;
}
export interface Worksheet {
  session: DiscoverySession;
  subject: DiscoverySubject | null;
  questions: SessionQuestion[];
  insights: DiscoveryInsight[];
  action_items: DiscoveryActionItem[];
}
export type TermStatus = "candidate" | "confirmed" | "deprecated";
export type CandidateStatus = "open" | "accepted" | "merged" | "ignored";
export interface TermAlias {
  alias: string;
  department: string | null;
}
export interface OntoTerm extends Base {
  term: string;
  definition: string | null;
  abbreviation: string | null;
  status: TermStatus;
  concept_id: string | null;
  source_type: string | null;
  source_id: string | null;
  notes: string | null;
  aliases: TermAlias[];
}
export interface SimilarTerm {
  term_id: string;
  term: string;
  matched: string;
  score: number;
}
export interface OntoCandidate extends Base {
  kind: string;
  name: string;
  payload: {
    context?: string;
    definition?: string;
    department?: string;
    session_question_id?: string;
  };
  source_type: string;
  source_id: string | null;
  status: CandidateStatus;
  resolved_into_id: string | null;
  similar: SimilarTerm[];
}
export interface GlossaryImportRow {
  row: number;
  values: {
    term: string | null;
    definition: string | null;
    abbreviation: string | null;
    aliases: TermAlias[];
    status: TermStatus | null;
    notes: string | null;
  };
  action: "create" | "update" | "skip";
  errors: { field: string; code: string }[];
}
export interface GlossaryImportResult {
  filename: string;
  applied: boolean;
  summary: {
    total: number;
    valid: number;
    invalid: number;
    create: number;
    update: number;
  };
  rows: GlossaryImportRow[];
}
export type JsonScalar = string | number | boolean | null;
export interface EgressNotice {
  destination: string;
  data_kinds: string[];
  features: string[];
}
export interface AdapterConfigField {
  name: string;
  kind: "text" | "int" | "secret";
  required: boolean;
  default: JsonScalar;
}
export interface AdapterActivation {
  id: string;
  tenant_id: string;
  adapter_key: string;
  status: "requested" | "active" | "disabled";
  config: Record<string, JsonScalar>;
  has_credentials: boolean;
  egress_notice: EgressNotice | null;
  request_note: string | null;
  requested_by: string | null;
  requested_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  approval_reason: string | null;
  deactivated_by: string | null;
  deactivated_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface AdapterInfo {
  key: string;
  display_name: string;
  implemented: boolean;
  egress_notice: EgressNotice;
  config_fields: AdapterConfigField[];
  activation: AdapterActivation | null;
}
export interface AdapterHealth {
  ok: boolean;
  message: string | null;
  latency_ms: number;
}
export type FlowKind = "as_is" | "to_be";
export type FlowNodeType = "start" | "end" | "task" | "decision" | "system" | "document" | "role" | "note";
export interface FlowNode {
  id: string;
  type: FlowNodeType;
  label: string;
  lane: string | null;
  system_id?: string | null;
  position: { x: number; y: number };
  data?: Record<string, unknown>;
}
export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  label?: string | null;
}
export interface FlowGraph {
  schema_version: 1;
  lanes: string[];
  nodes: FlowNode[];
  edges: FlowEdge[];
}
export interface FlowSummary extends Base {
  tenant_id: string;
  engagement_id: string;
  kind: FlowKind;
  pair_id: string | null;
  perspective: string;
  title: string;
  description: string | null;
  template_ref: AssetRef | null;
  node_count: number;
}
export interface Flow extends FlowSummary {
  graph: FlowGraph;
}
export interface FlowSnapshot extends Base {
  flow_id: string;
  version: number;
  note: string | null;
  node_count: number;
}
export interface FlowTemplate extends AssetRef {
  asset_key: string;
  title: string;
  graph: FlowGraph;
}
