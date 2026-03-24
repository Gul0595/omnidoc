import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Upload, Send, Loader2, LogOut, Plus, FileText,
  X, Users, ChevronRight, AlertCircle, CheckCircle2,
  Clock, Zap, Database, BarChart3,
} from "lucide-react";
import clsx from "clsx";
import {
  getSectors, getSectorConfig, getWorkspaces, createWorkspace, deleteWorkspace,
  getDocuments, uploadDocument, deleteDocument,
  streamQuery, getHistory, getLLMStatus, isLoggedIn, logout, getMe,
} from "../hooks/useApi";
import { useSector, getAccent } from "../hooks/useSector";

// ── Constants ─────────────────────────────────────────────────────────────────
const AGENT_ICONS: Record<string, string> = {
  classifier: "◈", retriever: "◎", extractive: "◆",
  descriptive: "◉", comparative: "⊞", synthesizer: "✦",
};
const PROVIDER_LABELS: Record<string, string> = {
  ollama: "Local GPU", groq: "Groq", gemini: "Gemini",
  cloudflare: "Cloudflare", huggingface: "HuggingFace", none: "Direct",
};
const INTENT_COLORS: Record<string, string> = {
  extractive:  "bg-green-50 text-green-700 border-green-200",
  descriptive: "bg-blue-50 text-blue-700 border-blue-200",
  comparative: "bg-purple-50 text-purple-700 border-purple-200",
};

// ── Types ─────────────────────────────────────────────────────────────────────
interface Step   { agent: string; detail: string; }
interface HistoryItem { id: string; question: string; answer: string; intent: string; llm_provider: string; latency_ms: number; created_at: string; }

export default function Dashboard() {
  const qc = useQueryClient();
  const { activeSector, setActiveSector } = useSector();

  // State
  const [activeWsId, setActiveWsId]   = useState("");
  const [question, setQuestion]       = useState("");
  const [steps, setSteps]             = useState<Step[]>([]);
  const [intent, setIntent]           = useState("");
  const [answer, setAnswer]           = useState("");
  const [provider, setProvider]       = useState("");
  const [streaming, setStreaming]     = useState(false);
  const [queryErr, setQueryErr]       = useState("");
  const [showCreate, setShowCreate]   = useState(false);
  const [newWsName, setNewWsName]     = useState("");
  const [uploadPct, setUploadPct]     = useState<Record<string, number>>({});
  const [activeTab, setActiveTab]     = useState<"chat" | "history" | "team">("chat");
  const fileRef   = useRef<HTMLInputElement>(null);
  const answerRef = useRef<HTMLDivElement>(null);

  // Auth guard
  useEffect(() => { if (!isLoggedIn()) window.location.href = "/login"; }, []);
  useEffect(() => {
    answerRef.current?.scrollTo(0, answerRef.current.scrollHeight);
  }, [answer]);

  // Queries
  const { data: sectors   = [] } = useQuery({ queryKey: ["sectors"],    queryFn: getSectors });
  const { data: sectorCfg }      = useQuery({ queryKey: ["cfg", activeSector], queryFn: () => getSectorConfig(activeSector) });
  const { data: workspaces = [] }= useQuery({ queryKey: ["workspaces"], queryFn: getWorkspaces });
  const { data: llmStatus }      = useQuery({ queryKey: ["llm"],        queryFn: getLLMStatus, refetchInterval: 30000 });
  const { data: docs = [] }      = useQuery({ queryKey: ["docs", activeWsId], queryFn: () => getDocuments(activeWsId), enabled: !!activeWsId, refetchInterval: 3000 });
  const { data: history = [] }   = useQuery({ queryKey: ["hist", activeWsId], queryFn: () => getHistory(activeWsId), enabled: !!activeWsId && activeTab === "history" });

  useEffect(() => {
    if (workspaces.length && !activeWsId) setActiveWsId(workspaces[0]?.id || "");
  }, [workspaces]);

  const activeWs = workspaces.find((w: any) => w.id === activeWsId);
  const wsAccent = getAccent(activeWs?.sector_accent || "blue");
  const suggestions: string[] = sectorCfg?.suggestions || [];

  // Create workspace
  const createWsMut = useMutation({
    mutationFn: () => createWorkspace({ name: newWsName, description: "", sector_id: activeSector }),
    onSuccess: (ws: any) => {
      qc.invalidateQueries({ queryKey: ["workspaces"] });
      setActiveWsId(ws.id); setShowCreate(false); setNewWsName("");
    },
  });

  // Upload
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeWsId) return;
    const tempId = Date.now().toString();
    setUploadPct(p => ({ ...p, [tempId]: 0 }));
    try {
      await uploadDocument(activeWsId, file, (pct) =>
        setUploadPct(p => ({ ...p, [tempId]: pct })));
      qc.invalidateQueries({ queryKey: ["docs", activeWsId] });
    } finally {
      setUploadPct(p => { const n = { ...p }; delete n[tempId]; return n; });
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  // Ask question
  const ask = useCallback(async (q?: string) => {
    const query = q || question;
    if (!query.trim() || !activeWsId || streaming) return;
    setQuestion(query); setStreaming(true);
    setSteps([]); setAnswer(""); setIntent(""); setProvider(""); setQueryErr("");
    await streamQuery(
      query, activeWsId,
      (a, d) => setSteps(s => [...s, { agent: a, detail: d }]),
      i => setIntent(i),
      t => setAnswer(a => a + t),
      (_, __, p) => { setProvider(p); setStreaming(false); },
      err => { setQueryErr(err); setStreaming(false); },
    );
  }, [question, activeWsId, streaming]);

  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden">

      {/* ── Header ── */}
      <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-4 py-2.5 flex items-center gap-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-xs flex-shrink-0">O</div>
          <span className="font-semibold text-sm text-gray-900 dark:text-white hidden sm:block">OmniDoc</span>
        </div>

        {/* Sector switcher */}
        <div className="flex items-center gap-1 flex-1 flex-wrap">
          {sectors.map((s: any) => {
            const a = getAccent(s.accent);
            return (
              <button key={s.id} onClick={() => setActiveSector(s.id)}
                className={clsx(
                  "px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                  s.id === activeSector ? `${a.bg} ${a.text}` : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
                )}>
                {s.label}
              </button>
            );
          })}
        </div>

        {/* LLM status */}
        {llmStatus?.primary && (
          <div className="hidden md:flex items-center gap-1.5 text-xs text-gray-400">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            {PROVIDER_LABELS[llmStatus.primary] || llmStatus.primary}
            {llmStatus.fallbacks?.length > 0 &&
              <span className="text-gray-300">+{llmStatus.fallbacks.length}</span>}
          </div>
        )}

        <button onClick={() => { logout(); window.location.href = "/login"; }}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition">
          <LogOut className="w-3.5 h-3.5" />
          <span className="hidden sm:block">Sign out</span>
        </button>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Sidebar ── */}
        <aside className="w-60 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col flex-shrink-0 hidden sm:flex">

          {/* Workspaces */}
          <div className="p-3 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Workspaces</span>
              <button onClick={() => setShowCreate(true)}
                className="w-5 h-5 flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition">
                <Plus className="w-3.5 h-3.5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-0.5">
              {workspaces.length === 0 && (
                <button onClick={() => setShowCreate(true)}
                  className="w-full text-left px-2 py-2 text-xs text-gray-400 hover:text-gray-600 border border-dashed border-gray-200 rounded-lg transition">
                  + Create your first workspace
                </button>
              )}
              {workspaces.map((ws: any) => {
                const a = getAccent(ws.sector_accent || "blue");
                return (
                  <button key={ws.id} onClick={() => setActiveWsId(ws.id)}
                    className={clsx(
                      "w-full text-left px-2.5 py-2 rounded-lg text-xs transition-all group",
                      ws.id === activeWsId
                        ? `${a.lightBg} ${a.lightText} font-medium`
                        : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
                    )}>
                    <div className="flex items-center gap-1.5">
                      <span className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0", a.bg)} />
                      <span className="truncate flex-1">{ws.name}</span>
                    </div>
                    <div className="text-gray-400 text-xs ml-3 mt-0.5">
                      {ws.sector_label} · {ws.document_count} doc{ws.document_count !== 1 ? "s" : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Documents */}
          {activeWsId && (
            <div className="flex-1 overflow-y-auto p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Documents</span>
                <div>
                  <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} />
                  <button onClick={() => fileRef.current?.click()}
                    className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-600 transition">
                    <Upload className="w-3 h-3" />
                    Upload PDF
                  </button>
                </div>
              </div>

              {/* Upload progress */}
              {Object.entries(uploadPct).map(([id, pct]) => (
                <div key={id} className="mb-2">
                  <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Uploading... {pct}%</span>
                  </div>
                  <div className="h-1 bg-gray-100 rounded">
                    <div className="h-1 bg-blue-500 rounded transition-all"
                         style={{ width: `${pct}%` }} />
                  </div>
                </div>
              ))}

              {docs.length === 0 ? (
                <div className="text-center py-6">
                  <FileText className="w-8 h-8 text-gray-200 mx-auto mb-2" />
                  <p className="text-xs text-gray-400">No PDFs yet</p>
                  <p className="text-xs text-gray-300 mt-1">Upload a PDF to get started</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {docs.map((d: any) => (
                    <div key={d.id} className="flex items-center gap-1.5 py-1.5 px-1 rounded hover:bg-gray-50 dark:hover:bg-gray-800 group transition">
                      <FileText className="w-3 h-3 text-gray-300 flex-shrink-0" />
                      <span className="text-xs text-gray-600 dark:text-gray-300 truncate flex-1 min-w-0">{d.filename}</span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {d.indexed
                          ? <CheckCircle2 className="w-3 h-3 text-green-500" />
                          : <Loader2 className="w-3 h-3 text-gray-400 animate-spin" />}
                        {d.has_scanned && <span title="OCR used" className="text-xs text-amber-500">OCR</span>}
                        {d.has_tables  && <span title="Tables extracted" className="text-xs text-blue-500">TBL</span>}
                        <button
                          onClick={() => deleteDocument(activeWsId, d.id).then(() =>
                            qc.invalidateQueries({ queryKey: ["docs", activeWsId] }))}
                          className="opacity-0 group-hover:opacity-100 transition-opacity ml-0.5">
                          <X className="w-3 h-3 text-red-400 hover:text-red-600" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </aside>

        {/* ── Main panel ── */}
        <main className="flex-1 flex flex-col overflow-hidden">

          {/* Workspace header + tabs */}
          {activeWs && (
            <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-4 py-2 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <span className={clsx("px-2 py-0.5 rounded-md text-xs font-medium", wsAccent.lightBg, wsAccent.lightText)}>
                  {activeWs.sector_label}
                </span>
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{activeWs.name}</span>
              </div>
              <div className="flex items-center gap-1">
                {(["chat", "history", "team"] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveTab(tab)}
                    className={clsx(
                      "px-3 py-1 rounded-lg text-xs font-medium transition",
                      activeTab === tab
                        ? "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200"
                        : "text-gray-400 hover:text-gray-600"
                    )}>
                    {tab === "chat" ? "Chat" : tab === "history" ? "History" : "Team"}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ── Chat Tab ── */}
          {activeTab === "chat" && (
            <div className="flex-1 flex flex-col overflow-hidden p-4 gap-3">

              {/* No workspace selected */}
              {!activeWsId && (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <Database className="w-8 h-8 text-blue-400" />
                    </div>
                    <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-1">No workspace selected</h3>
                    <p className="text-sm text-gray-400 mb-4">Create a workspace and upload PDFs to get started</p>
                    <button onClick={() => setShowCreate(true)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition">
                      Create workspace
                    </button>
                  </div>
                </div>
              )}

              {/* Agent steps */}
              {steps.length > 0 && (
                <div className="flex flex-wrap gap-1.5 flex-shrink-0">
                  {steps.map((s, i) => (
                    <div key={i} className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                      <span>{AGENT_ICONS[s.agent] ?? "○"}</span>
                      <span>{s.detail}</span>
                      {!streaming && i === steps.length - 1 &&
                        <CheckCircle2 className="w-3 h-3 text-green-500 ml-0.5" />}
                    </div>
                  ))}
                </div>
              )}

              {/* Answer */}
              {(answer || streaming) && (
                <div className="flex-1 min-h-0 flex flex-col gap-2">
                  <div ref={answerRef}
                    className="flex-1 overflow-y-auto bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed">
                    {answer}
                    {streaming && <span className="animate-pulse text-blue-500">▋</span>}
                  </div>
                  {!streaming && (intent || provider) && (
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {intent && (
                        <span className={clsx("text-xs px-2 py-0.5 rounded-full border font-medium",
                          INTENT_COLORS[intent] || INTENT_COLORS.descriptive)}>
                          {intent}
                        </span>
                      )}
                      {provider && provider !== "none" && (
                        <span className="text-xs text-gray-400">
                          via {PROVIDER_LABELS[provider] || provider}
                        </span>
                      )}
                      {provider === "none" && (
                        <span className="text-xs text-green-600">
                          ✓ Direct extraction — no LLM used
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Error */}
              {queryErr && (
                <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                  {queryErr}
                </div>
              )}

              {/* Suggestions */}
              {!answer && !streaming && !queryErr && activeWsId && suggestions.length > 0 && (
                <div className="flex-1 flex flex-col justify-center max-w-2xl mx-auto w-full">
                  <p className="text-xs text-gray-400 text-center mb-3">
                    {sectorCfg?.terminology?.query || "Ask anything about your documents"}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {suggestions.map((s: string, i: number) => (
                      <button key={i} onClick={() => ask(s)}
                        className="text-left px-3.5 py-3 rounded-xl border border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-900 hover:border-blue-300 hover:bg-blue-50/50 dark:hover:bg-gray-800 transition-all group">
                        <span>{s}</span>
                        <ChevronRight className="w-3 h-3 inline-block ml-1 opacity-0 group-hover:opacity-100 transition" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Input */}
              {activeWsId && (
                <div className="flex gap-2 flex-shrink-0">
                  <input
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && !e.shiftKey && ask()}
                    placeholder={
                      docs.filter((d: any) => d.indexed).length === 0
                        ? "Upload and wait for indexing first..."
                        : sectorCfg?.terminology?.query || "Ask anything about your documents..."
                    }
                    disabled={streaming || docs.filter((d: any) => d.indexed).length === 0}
                    className="flex-1 px-4 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl text-sm bg-white dark:bg-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-40 transition"
                  />
                  <button
                    onClick={() => ask()}
                    disabled={streaming || !question.trim() || docs.filter((d: any) => d.indexed).length === 0}
                    className={clsx(
                      "px-4 py-2.5 rounded-xl text-white text-sm font-medium flex items-center gap-1.5 transition disabled:opacity-40",
                      wsAccent.bg, "hover:opacity-90"
                    )}>
                    {streaming
                      ? <Loader2 className="w-4 h-4 animate-spin" />
                      : <Send className="w-4 h-4" />}
                    <span className="hidden sm:block">Ask</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── History Tab ── */}
          {activeTab === "history" && (
            <div className="flex-1 overflow-y-auto p-4">
              {history.length === 0 ? (
                <div className="text-center py-12">
                  <Clock className="w-8 h-8 text-gray-200 mx-auto mb-2" />
                  <p className="text-sm text-gray-400">No queries yet</p>
                </div>
              ) : (
                <div className="space-y-3 max-w-2xl mx-auto">
                  {history.map((h: HistoryItem) => (
                    <div key={h.id} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{h.question}</p>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          {h.intent && (
                            <span className={clsx("text-xs px-2 py-0.5 rounded-full border",
                              INTENT_COLORS[h.intent] || INTENT_COLORS.descriptive)}>
                              {h.intent}
                            </span>
                          )}
                        </div>
                      </div>
                      {h.answer && (
                        <p className="text-xs text-gray-500 line-clamp-3 mb-2">{h.answer}</p>
                      )}
                      <div className="flex items-center gap-3 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <Zap className="w-3 h-3" />
                          {PROVIDER_LABELS[h.llm_provider] || h.llm_provider || "—"}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {h.latency_ms.toFixed(0)}ms
                        </span>
                        <span>{new Date(h.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Team Tab ── */}
          {activeTab === "team" && (
            <div className="flex-1 overflow-y-auto p-4">
              <div className="max-w-lg mx-auto">
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
                  <h3 className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">Team members</h3>
                  <p className="text-xs text-gray-400 mb-4">
                    Invite team members to collaborate on this workspace.
                    Use the API endpoint <code className="bg-gray-100 px-1 rounded">/api/v1/workspaces/{"{id}"}/members</code> to manage access.
                  </p>
                  <div className="text-xs text-gray-500 space-y-1">
                    <p><strong>viewer</strong> — can read documents and ask questions</p>
                    <p><strong>editor</strong> — can also upload and delete documents</p>
                    <p><strong>admin</strong> — can also invite and remove members</p>
                  </div>
                  <a href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/docs#/members`}
                    target="_blank" rel="noreferrer"
                    className="mt-4 inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
                    Open API docs for team management →
                  </a>
                </div>

                {/* LLM chain status */}
                {llmStatus && (
                  <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 mt-3">
                    <h3 className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-3">LLM fallback chain</h3>
                    <div className="space-y-2">
                      {llmStatus.chain?.map((p: string, i: number) => (
                        <div key={p} className="flex items-center gap-2 text-xs">
                          <span className="w-5 h-5 rounded-full bg-green-100 text-green-700 flex items-center justify-center font-medium flex-shrink-0">
                            {i + 1}
                          </span>
                          <span className="text-gray-700 dark:text-gray-300 font-medium">
                            {PROVIDER_LABELS[p] || p}
                          </span>
                          {i === 0 && <span className="text-green-500 text-xs">← active</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ── Create workspace modal ── */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-xl p-6 w-full max-w-sm">
            <h2 className="font-semibold text-gray-900 dark:text-white text-sm mb-4">New workspace</h2>

            <input value={newWsName} onChange={e => setNewWsName(e.target.value)}
              placeholder="e.g. Legal contracts Q3, Patient records, Course materials"
              className="w-full px-3 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl text-sm mb-3 bg-white dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              onKeyDown={e => e.key === "Enter" && newWsName.trim() && createWsMut.mutate()} />

            <p className="text-xs text-gray-500 mb-4">
              Sector: <span className="font-medium text-gray-700 dark:text-gray-300">{activeSector}</span>
              {" — "}the AI agent will use the {activeSector} persona and extraction patterns for all documents in this workspace.
            </p>

            <div className="flex gap-2">
              <button onClick={() => { setShowCreate(false); setNewWsName(""); }}
                className="flex-1 py-2 border border-gray-200 dark:border-gray-700 rounded-xl text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                Cancel
              </button>
              <button onClick={() => createWsMut.mutate()}
                disabled={!newWsName.trim() || createWsMut.isPending}
                className={clsx(
                  "flex-1 py-2 rounded-xl text-white text-sm font-medium transition disabled:opacity-40",
                  getAccent(activeSector).bg
                )}>
                {createWsMut.isPending ? "Creating..." : "Create workspace"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
