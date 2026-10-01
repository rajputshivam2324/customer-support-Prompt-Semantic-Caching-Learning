"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Activity, ArrowRight, BarChart3, BookOpen, ChevronDown, ChevronRight, Clock3, Database, Layers3, LogOut, MessageSquareText, Plus, Send, ShieldCheck, Sparkles, Zap } from "lucide-react";

type Source = "exact_cache" | "semantic_cache" | "rag_llm" | "llm" | "tool_llm";
type TraceEvent = { step: string; status: string; duration_ms: number; detail: string };
type Trace = { id: string; question: string; answer: string; source: Source; events: TraceEvent[]; citations: { id: string; title: string }[]; latency_ms: number; input_tokens: number; output_tokens: number; tokens_saved: number; similarity: number | null; model: string | null; created_at: string };
type ChatResult = { answer: string; source: Source; trace_id: string; latency_ms: number; similarity: number | null; citations: { id: string; title: string }[]; usage: { input_tokens: number; output_tokens: number; tokens_saved: number } };
type Metrics = { requests: number; sources: Partial<Record<Source, number>>; cache_hit_rate: number; tokens_saved_estimate: number; avg_latency_ms: number; p95_latency_ms: number };
type Customer = { id: string; name: string; plan: string; region: string };
type User = { id: string; name: string; email: string; role: string; tenant_id: string; tenant_name: string };
type Conversation = { id: string; customer_id: string; title: string; created_at: string; updated_at: string };
type ConversationDetail = Conversation & { traces: Trace[] };

const sourceInfo: Record<Source, { label: string; short: string; icon: typeof Zap; color: string }> = {
  exact_cache: { label: "Exact cache", short: "Exact cache", icon: Zap, color: "violet" },
  semantic_cache: { label: "Semantic cache", short: "Semantic cache", icon: Sparkles, color: "purple" },
  rag_llm: { label: "RAG + Gemini", short: "RAG + LLM", icon: BookOpen, color: "blue" },
  llm: { label: "Gemini", short: "LLM", icon: Sparkles, color: "amber" },
  tool_llm: { label: "Tool + Gemini", short: "Tool + LLM", icon: Database, color: "teal" },
};

const prompts = ["Why did our bill increase in April?", "What is our P1 incident SLA?", "Is SSO included in our plan?", "Can I add 20 seats temporarily?"];

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/gateway/v1/${path}`, { ...options, headers: { "Content-Type": "application/json", ...options?.headers }, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`);
  return data as T;
}

function SourceBadge({ source }: { source: Source }) {
  const info = sourceInfo[source];
  const Icon = info.icon;
  return <span className={`source-badge ${info.color}`}><Icon size={13} strokeWidth={2.2} />{info.label}</span>;
}

function TraceDetails({ trace }: { trace: Trace }) {
  return <div className="trace-detail">
    <div className="trace-topline"><span>EXECUTION PATH</span><span>{trace.id.slice(0, 8)}…</span></div>
    <div className="timeline">{trace.events.map((event, index) => <div className="timeline-row" key={`${event.step}-${index}`}>
      <span className={`timeline-dot ${event.status}`} />
      <div><strong>{event.step.replaceAll("_", " ")}</strong><small>{event.detail || event.status.toUpperCase()}</small></div>
      <span className="duration">{event.duration_ms} ms</span>
    </div>)}</div>
    <div className="trace-stats">
      <div><span>Total latency</span><strong>{trace.latency_ms} ms</strong></div>
      <div><span>LLM invoked</span><strong>{trace.source.includes("cache") ? "No" : "Yes"}</strong></div>
      <div><span>Tokens used</span><strong>{trace.input_tokens + trace.output_tokens}</strong></div>
      <div><span>Tokens saved*</span><strong>{trace.tokens_saved}</strong></div>
      {trace.similarity != null && <div><span>Similarity</span><strong>{(trace.similarity * 100).toFixed(1)}%</strong></div>}
    </div>
    {trace.citations.length > 0 && <div className="citations">Sources: {trace.citations.map(c => <span key={c.id}>{c.title}</span>)}</div>}
    <p className="estimate-note">* Based on the original answer’s recorded token usage.</p>
  </div>;
}

export default function Home() {
  const [tab, setTab] = useState<"chat" | "traces" | "analytics">("chat");
  const [user, setUser] = useState<User | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Trace[]>([]);
  const [conversationTraces, setConversationTraces] = useState<Trace[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [customers, conversations, traces, data] = await Promise.all([api<Customer[]>("customers"), api<Conversation[]>("conversations"), api<Trace[]>("traces"), api<Metrics>("metrics")]);
      setCustomer(customers[0] || null);
      setConversations(conversations);
      setHistory(traces);
      setMetrics(data);
      setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load dashboard"); }
  }, []);

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" }).then(async response => {
      if (response.ok) {
        setUser(await response.json());
        await refresh();
      } else if (response.status !== 401) {
        const data = await response.json();
        setError(data.detail || "Unable to check session");
      }
    }).catch(() => setError("Unable to connect to gateway")).finally(() => setCheckingSession(false));
  }, [refresh]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      const response = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Sign in failed");
      setUser(data as User); setPassword("");
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Sign in failed"); }
    finally { setLoading(false); }
  }

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    setUser(null); setCustomer(null); setHistory([]); setConversationTraces([]); setConversations([]);
    setActiveConversationId(null); setMetrics(null); setSelected(null); setError("");
  }

  async function openConversation(id: string) {
    setError(""); setTab("chat"); setActiveConversationId(id); setSelected(null);
    try {
      const detail = await api<ConversationDetail>(`conversations/${id}`);
      setConversationTraces(detail.traces);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to open conversation"); }
  }

  function newChat() {
    setTab("chat"); setActiveConversationId(null); setConversationTraces([]); setSelected(null); setQuestion(""); setError("");
  }

  async function submit(value = question) {
    if (!value.trim() || !customer || loading) return;
    setLoading(true); setError(""); setQuestion(""); setTab("chat");
    try {
      let conversationId = activeConversationId;
      if (!conversationId) {
        const created = await api<Conversation>("conversations", { method: "POST", body: JSON.stringify({ customer_id: customer.id }) });
        conversationId = created.id;
        setActiveConversationId(created.id);
        setConversations(previous => [created, ...previous]);
      }
      const result = await api<ChatResult>("chat", { method: "POST", body: JSON.stringify({ conversation_id: conversationId, question: value.trim() }) });
      const trace = await api<Trace>(`traces/${result.trace_id}`);
      setHistory(previous => [trace, ...previous]);
      setConversationTraces(previous => [...previous, trace]);
      setConversations(previous => previous.map(item => item.id === conversationId ? { ...item, title: item.title === "New conversation" ? value.trim().slice(0, 100) : item.title, updated_at: new Date().toISOString() } : item).sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
      setSelected(trace.id);
      const data = await api<Metrics>("metrics");
      setMetrics(data);
    } catch (err) { setError(err instanceof Error ? err.message : "Request failed"); setQuestion(value); }
    finally { setLoading(false); }
  }

  const currentTenant = user?.tenant_name || "Demo Workspace";
  if (checkingSession) return <div className="session-loading">Checking your session…</div>;
  if (!user) return <div className="auth-page"><form className="auth-card" onSubmit={signIn}><div className="brand"><span className="brand-mark"><Layers3 size={20} /></span><span>relay<span className="brand-dot">.</span></span></div><div className="eyebrow"><span className="eyebrow-line" /> DEMO WORKSPACE</div><h1>Welcome back.</h1><p>Sign in to keep your support conversations and execution traces private.</p>{error && <div className="auth-error">{error}</div>}<label>Email<input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label><button type="submit" disabled={loading}>{loading ? "Signing in…" : "Sign in"}<ArrowRight size={16} /></button>{process.env.NODE_ENV === "development" ? <small>Local demo default: demo@relay.example / DemoPass123!</small> : <small>Use your configured demo workspace credentials.</small>}</form></div>;
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Layers3 size={20} strokeWidth={2.3} /></span><span>relay<span className="brand-dot">.</span></span></div>
      <div className="workspace-caption">WORKSPACE</div>
      <div className="workspace-select"><span className="workspace-avatar">{currentTenant.slice(0, 1)}</span><span><strong>{currentTenant}</strong><small>Demo environment</small></span></div>
      <div className="nav-caption">PLATFORM</div>
      <nav className="nav-links">
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}><MessageSquareText size={18} /> Support chat</button>
        <button className={tab === "traces" ? "active" : ""} onClick={() => setTab("traces")}><Activity size={18} /> Request traces <span className="nav-count">{history.length}</span></button>
        <button className={tab === "analytics" ? "active" : ""} onClick={() => setTab("analytics")}><BarChart3 size={18} /> Analytics</button>
      </nav>
      <div className="conversation-heading"><span>YOUR CHATS</span><button type="button" onClick={newChat} aria-label="New chat" title="New chat"><Plus size={17} /></button></div>
      <button className="new-chat-button" type="button" onClick={newChat}><Plus size={16} /> New chat</button>
      <div className="conversation-list">{conversations.length === 0 ? <span className="no-conversations">No saved chats yet</span> : conversations.map(item => <button key={item.id} className={activeConversationId === item.id && tab === "chat" ? "selected" : ""} type="button" onClick={() => openConversation(item.id)} title={item.title}><MessageSquareText size={14} /><span>{item.title}</span></button>)}</div>
      <div className="sidebar-bottom"><div className="system-dot" /> {error ? "Gateway unavailable" : customer ? "Gateway connected" : "Connecting to gateway"} <small>Gemini 2.5 Flash</small></div>
    </aside>

    <main className="main">
      <header className="topbar"><div><span className="breadcrumb">Workspace <ChevronRight size={13} /> {tab === "chat" ? "Support chat" : tab === "traces" ? "Request traces" : "Analytics"}</span></div><div className="topbar-right"><span className="live-indicator"><span /> LIVE</span><span className="operator-name">{user.name}</span><span className="top-avatar">{user.name.slice(0, 1)}</span><button className="logout-button" onClick={signOut} title="Sign out" aria-label="Sign out"><LogOut size={17} /></button></div></header>
      {error && <div className="error-banner">{error}</div>}
      {tab === "chat" && <div className="page-content chat-page">
        <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> SUPPORT CONSOLE</div><h1>Support chat<span className="heading-dot">.</span></h1><p>Ask a question and inspect exactly how the answer was produced.</p></div><div className="heading-chip"><ShieldCheck size={15} /> Fictional demo data</div></div>
        <div className="chat-layout"><section className="chat-card">
          <div className="chat-card-header"><div className="chat-avatar"><MessageSquareText size={17} /></div><div><strong>AcmeCloud support assistant</strong><span>Connected to {currentTenant} knowledge &amp; billing</span></div><span className="online-pill"><span /> Online</span></div>
          <div className="conversation">
            {conversationTraces.length === 0 && <div className="empty-chat"><div className="empty-icon"><Sparkles size={24} /></div><h2>How can I help?</h2><p>Start a new chat or ask a billing or policy question to see the execution path.</p><div className="prompt-list">{prompts.map(prompt => <button key={prompt} onClick={() => submit(prompt)}>{prompt}<ArrowRight size={14} /></button>)}</div></div>}
            {conversationTraces.map(trace => <div className="message-pair" key={trace.id}><div className="user-message"><span>You</span><p>{trace.question}</p></div><div className="ai-message"><div className="ai-message-heading"><span className="small-brand"><Layers3 size={14} /></span><strong>Relay AI</strong><SourceBadge source={trace.source} /></div><p>{trace.answer}</p><button className="inspect-link" onClick={() => setSelected(selected === trace.id ? null : trace.id)}>{selected === trace.id ? "Hide" : "Inspect"} execution trace <ChevronRight size={14} /></button>{selected === trace.id && <TraceDetails trace={trace} />}</div></div>)}
            {loading && <div className="thinking"><span className="thinking-dots"><i /><i /><i /></span> Running support workflow…</div>}
          </div>
          <form className="composer" onSubmit={e => { e.preventDefault(); submit(); }}><div className="composer-inner"><textarea aria-label="Ask a support question" placeholder="Ask about billing, policies, SLA, or your account…" value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} rows={2} /><button type="submit" disabled={loading || !question.trim() || !customer} aria-label="Send question"><Send size={17} /></button></div><div className="composer-foot"><span>Answers are grounded in fictional customer data and knowledge</span><span>Enter to send · Shift + Enter for new line</span></div></form>
        </section><aside className="context-column"><div className="context-card"><div className="context-title"><span className="context-icon"><Database size={16} /></span> CUSTOMER CONTEXT</div>{customer ? <><div className="customer-identity"><span>{customer.name.slice(0, 1)}</span><div><strong>{customer.name}</strong><small>{customer.id}</small></div></div><div className="context-row"><span>Plan</span><strong>{customer.plan}</strong></div><div className="context-row"><span>Region</span><strong>{customer.region}</strong></div><div className="context-row"><span>Tenant</span><strong>{currentTenant}</strong></div></> : <p className="muted">Loading customer…</p>}</div><div className="context-card explainer"><div className="context-title"><span className="context-icon"><Activity size={16} /></span> ANSWER SOURCES</div><p>Every response is labeled with the path it actually took.</p>{(Object.keys(sourceInfo) as Source[]).map(source => <div className="legend-row" key={source}><SourceBadge source={source} /></div>)}<p className="cache-explainer">Exact cache reuses identical questions. Billing answers first check the current invoice snapshot, so edits invalidate old answers. Semantic cache is limited to reusable knowledge answers; RAG searches pgvector-indexed documents.</p></div></aside></div>
      </div>}
      {tab === "traces" && <div className="page-content"><div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> OBSERVABILITY</div><h1>Request traces<span className="heading-dot">.</span></h1><p>Every step, source decision, and token count in one place.</p></div><div className="heading-chip"><Activity size={15} /> {history.length} recent requests</div></div><div className="list-card">{history.length === 0 ? <div className="empty-list">No requests yet. Ask a question in Support chat to create a trace.</div> : history.map(trace => <div className="trace-list-item" key={trace.id}><button onClick={() => setSelected(selected === trace.id ? null : trace.id)}><span className="trace-id">{trace.id.slice(0, 8)}</span><span className="trace-question">{trace.question}</span><SourceBadge source={trace.source} /><span className="trace-time"><Clock3 size={13} /> {trace.latency_ms} ms</span><ChevronDown size={16} /></button>{selected === trace.id && <TraceDetails trace={trace} />}</div>)}</div></div>}
      {tab === "analytics" && <div className="page-content"><div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> PERFORMANCE</div><h1>Analytics<span className="heading-dot">.</span></h1><p>Operational metrics for {currentTenant}.</p></div><div className="heading-chip"><BarChart3 size={15} /> All-time demo data</div></div><div className="metric-grid"><div className="metric-card"><span>Total requests</span><strong>{metrics?.requests ?? 0}</strong><small>Across all answer paths</small></div><div className="metric-card"><span>Cache hit rate</span><strong>{((metrics?.cache_hit_rate ?? 0) * 100).toFixed(0)}%</strong><small>LLM calls avoided</small></div><div className="metric-card"><span>Avg latency</span><strong>{metrics?.avg_latency_ms ?? 0}<em>ms</em></strong><small>End to end</small></div><div className="metric-card"><span>Tokens saved*</span><strong>{(metrics?.tokens_saved_estimate ?? 0).toLocaleString()}</strong><small>Estimated from original usage</small></div></div><div className="distribution-card"><div className="card-heading"><div><h2>Answer source distribution</h2><p>How requests were resolved</p></div><span>{metrics?.requests ?? 0} requests</span></div>{(Object.keys(sourceInfo) as Source[]).map(source => { const count = metrics?.sources[source] || 0; const percent = metrics?.requests ? Math.round(count / metrics.requests * 100) : 0; return <div className="distribution-row" key={source}><SourceBadge source={source} /><div className="bar-track"><span className={sourceInfo[source].color} style={{ width: `${percent}%` }} /></div><strong>{percent}%</strong><small>{count}</small></div>; })}<div className="distribution-footer"><span>P95 latency</span><strong>{metrics?.p95_latency_ms ?? 0} ms</strong></div><p className="estimate-note">* Cached tokens are estimates based on the recorded usage of the answer that populated the cache.</p></div></div>}
    </main>
  </div>;
}
