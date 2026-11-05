"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, CircuitBoard, Layers3, UploadCloud, FolderClock, ScanSearch, PackageOpen, Clock3, Trash2, ShieldCheck } from "lucide-react";
import UploadSection from "@/components/UploadSection";
import PCBOverview from "@/components/PCBOverview";
import AgentTimeline from "@/components/AgentTimeline";
import DFMReport from "@/components/DFMReport";
import BOMReport from "@/components/BOMReport";
import ManufacturerComparison from "@/components/ManufacturerComparison";
import OrderPanel from "@/components/OrderPanel";
import OrderConfirmation from "@/components/OrderConfirmation";
import TitleBlock from "@/components/TitleBlock";
import StepNav, { type Step } from "@/components/StepNav";
import Footer from "@/components/Footer";
import PCBReveal from "@/components/PCBReveal";

import {
  analyzePCB,
  getEvents,
  createOrder,
  savePrototypeRequest,
  deleteProject,
  uploadPCBRevision,
  verifyOrder,
  getSavedProject,
  listProjects,
  uploadPCB,
  getDemoBoard,
  downloadProjectPackage,
  compareProjects,
} from "@/lib/api";
import type {
  AnalysisBundle,
  AgentEvent,
  OrderResult,
  ProjectSummary,
  ProjectHistoryEntry,
  ProjectComparison,
} from "@/types";

type RazorpayPayment = { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string };
type RazorpayCheckout = { open: () => void; on: (event: "payment.failed", callback: (response: { error?: { description?: string } }) => void) => void };
type RazorpayOptions = { key: string; amount: number; currency: string; name: string; description: string; order_id: string; theme?: { color: string }; handler: (payment: RazorpayPayment) => void | Promise<void>; modal?: { ondismiss?: () => void } };
declare global { interface Window { Razorpay?: new (options: RazorpayOptions) => RazorpayCheckout } }
export default function Home() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [bundle, setBundle] = useState<AnalysisBundle | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [selectedMfrId, setSelectedMfrId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(1);
  const [order, setOrder] = useState<OrderResult | null>(null);
  const [savingOrder, setSavingOrder] = useState(false);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loadingProject, setLoadingProject] = useState<string | null>(null);
  const [deletingProject, setDeletingProject] = useState<string | null>(null);
  const repairFileInputRef = useRef<HTMLInputElement | null>(null);
  const [projectHistory, setProjectHistory] = useState<ProjectHistoryEntry[]>([]);
  const [downloadingPackage, setDownloadingPackage] = useState(false);
  const [comparisonIds, setComparisonIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ProjectComparison | null>(null);
  const [comparing, setComparing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  async function handleFileReady(file: File) {
    setError(null);
    setBundle(null);
    setOrder(null);
    setEvents([]);
    setProjectHistory([]);
    setAnalyzing(true);
    setFilename(file.name);
    setStep(1);

    try {
      const { id } = await uploadPCB(file);
      setProjectId(id);
      pollRef.current = setInterval(async () => {
        try {
          setEvents(await getEvents(id));
        } catch {
          // Temporary polling errors are safe to ignore.
        }
      }, 700);

      const result = await analyzePCB(id);
      setBundle(result);
      setSelectedMfrId(result.recommendation.recommended.manufacturer_id);
      setStep(2);
      setEvents(await getEvents(id));
      setProjects(await listProjects().catch(() => []));
      const savedProject: Record<string, unknown> = await getSavedProject(id).catch(() => ({}));
      setProjectHistory(Array.isArray(savedProject.history) ? savedProject.history as ProjectHistoryEntry[] : []);

      if (pollRef.current) clearInterval(pollRef.current);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not analyze this board.");
      if (pollRef.current) clearInterval(pollRef.current);
    } finally {
      setAnalyzing(false);
    }
  }

  async function openProject(summary: ProjectSummary) {
    setLoadingProject(summary.id);
    setError(null);

    try {
      const saved = await getSavedProject(summary.id);
      setProjectId(summary.id);
      setFilename(summary.filename);
      setProjectHistory(Array.isArray(saved.history) ? saved.history as ProjectHistoryEntry[] : []);
      setOrder(null);

      if (
        saved.pcb_analysis &&
        saved.dfm_result &&
        saved.bom_result &&
        saved.recommendation
      ) {
        const nextBundle = saved as unknown as AnalysisBundle;
        setBundle(nextBundle);
        setSelectedMfrId(nextBundle.recommendation.recommended.manufacturer_id);
        setOrder(
          ((saved.manufacturing_requests as OrderResult[] | undefined) ?? []).at(
            -1,
          ) ?? null,
        );
        setEvents(await getEvents(summary.id).catch(() => []));
        const savedRequests = (saved.manufacturing_requests as OrderResult[] | undefined) ?? [];
        setStep(savedRequests.length > 0 ? 4 : 2);
      } else {
        setBundle(null);
        setStep(1);
      }
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not reopen this saved project.",
      );
    } finally {
      setLoadingProject(null);
    }
  }

  async function handleRestoreSource(file: File) {
    if (!projectId) return;
    const currentProjectId = projectId;
    setAnalyzing(true);
    setError(null);
    try {
      await uploadPCBRevision(currentProjectId, file);
      const result = await analyzePCB(currentProjectId);
      setFilename(file.name);
      setBundle(result);
      setSelectedMfrId(result.recommendation.recommended.manufacturer_id);
      setEvents(await getEvents(currentProjectId).catch(() => []));
      const saved: Record<string, unknown> = await getSavedProject(currentProjectId).catch(() => ({}));
      setProjectHistory(Array.isArray(saved.history) ? saved.history as ProjectHistoryEntry[] : []);
      setProjects(await listProjects().catch(() => []));
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not restore this board file.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleDeleteProject(project: ProjectSummary) {
    if (!window.confirm(`Delete ${project.filename} and its saved PCB Forge workspace? This cannot be undone.`)) return;
    setDeletingProject(project.id);
    setError(null);
    try {
      await deleteProject(project.id);
      setProjects((rows) => rows.filter((row) => row.id !== project.id));
      setComparisonIds((ids) => ids.filter((id) => id !== project.id));
      setComparison(null);
      if (projectId === project.id) {
        setProjectId(null);
        setFilename("");
        setBundle(null);
        setOrder(null);
        setEvents([]);
        setProjectHistory([]);
        setSelectedMfrId("");
        setStep(1);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete this saved project.");
    } finally {
      setDeletingProject(null);
    }
  }

  async function handleDemoBoard() {
    setError(null);
    try {
      await handleFileReady(await getDemoBoard());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the example board.");
    }
  }

  async function handlePackageDownload() {
    if (!projectId) return;
    setDownloadingPackage(true);
    setError(null);
    try {
      const blob = await downloadProjectPackage(projectId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${projectId.toLowerCase()}-manufacturing-passport.zip`;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not download the project package.");
    } finally {
      setDownloadingPackage(false);
    }
  }

  async function handleOrder(quantity: number, totalPrice: number) {
    if (!projectId) return;
    setSavingOrder(true);
    setError(null);
    try {
      const session = await createOrder(projectId, selectedMfrId, quantity, totalPrice);
      if (!window.Razorpay) {
        await new Promise<void>((resolve, reject) => {
          const script = document.createElement("script");
          script.src = "https://checkout.razorpay.com/v1/checkout.js";
          script.onload = () => resolve();
          script.onerror = () => reject(new Error("Could not load Razorpay checkout. Check your internet connection."));
          document.body.appendChild(script);
        });
      }
      if (!window.Razorpay) throw new Error("Razorpay checkout did not load. Refresh and try again.");
      const checkout = new window.Razorpay({
        key: session.key_id, amount: session.amount, currency: session.currency,
        name: "PCB Forge", description: `Test checkout - ${session.manufacturer} - ${session.quantity} boards`,
        order_id: session.razorpay_order_id, theme: { color: "#d87934" },
        handler: async (payment) => {
          try {
            const paidOrder = await verifyOrder(payment);
            setOrder(paidOrder);
            setProjects((rows) => rows.map((p) => p.id === projectId ? { ...p, has_manufacturing_request: true } : p));
            const savedProject: Record<string, unknown> = await getSavedProject(projectId).catch(() => ({}));
            setProjectHistory(Array.isArray(savedProject.history) ? savedProject.history as ProjectHistoryEntry[] : []);
          } catch (e) {
            setError(e instanceof Error ? e.message : "Could not verify the test payment. Retry verification.");
          } finally { setSavingOrder(false); }
        },
        modal: { ondismiss: () => setSavingOrder(false) },
      });
      checkout.on("payment.failed", (response) => {
        setError(response.error?.description || "Test payment failed. Please try again.");
        setSavingOrder(false);
      });
      checkout.open();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Could not start the request.";
      if (message.includes("Razorpay Test Mode is not configured") || message.includes("Method Not Allowed")) {
        try {
          const request = await savePrototypeRequest(projectId, selectedMfrId, quantity, totalPrice);
          setOrder(request);
          setProjects((rows) => rows.map((p) => p.id === projectId ? { ...p, has_manufacturing_request: true } : p));
          const savedProject: Record<string, unknown> = await getSavedProject(projectId).catch(() => ({}));
          setProjectHistory(Array.isArray(savedProject.history) ? savedProject.history as ProjectHistoryEntry[] : []);
          setError(null);
        } catch (requestError) {
          setError(requestError instanceof Error ? requestError.message : "Could not save the prototype request.");
        }
      } else {
        setError(message);
      }
      setSavingOrder(false);
    }
  }

  function toggleComparison(projectIdToToggle: string) {
    setComparison(null);
    setComparisonIds((ids) => {
      if (ids.includes(projectIdToToggle)) return ids.filter((id) => id !== projectIdToToggle);
      return ids.length >= 2 ? [projectIdToToggle] : [...ids, projectIdToToggle];
    });
  }

  async function handleCompareProjects() {
    if (comparisonIds.length !== 2) return;
    setComparing(true);
    setError(null);
    try {
      setComparison(await compareProjects(comparisonIds[0], comparisonIds[1]));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not compare these projects.");
    } finally {
      setComparing(false);
    }
  }

  const steps: Step[] = [
    { id: 1, label: "Board upload", unlocked: true },
    { id: 2, label: "Design analysis", unlocked: Boolean(bundle) },
    { id: 3, label: "BOM & sourcing", unlocked: Boolean(bundle) },
    { id: 4, label: "Build request", unlocked: Boolean(bundle) },
  ];

  const selectedQuote = bundle?.recommendation.all_quotes.find(
    (q) => q.manufacturer_id === selectedMfrId,
  );

  return (
    <main className="forge-workspace mx-auto max-w-7xl px-6 py-6 sm:px-8">
      <PCBReveal />
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-base-700 pb-5">
        <a href="/" className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-accent-500/40 bg-accent-500/10">
            <CircuitBoard className="h-6 w-6 text-accent-400" />
          </div>
          <div>
            <div className="font-display text-xl font-semibold text-[#E8EDE9]">
              PCB Forge
            </div>
            <div className="label-tech">PCB design · fabrication · quality</div>
          </div>
        </a>
        <a
          href="http://localhost:5173/#forgeTransition=1"
          className="group inline-flex items-center gap-2 rounded-lg border border-accent-500/35 bg-accent-500/10 px-4 py-2.5 text-sm font-medium text-accent-300 transition duration-200 hover:-translate-y-0.5 hover:border-accent-400/70 hover:bg-accent-500/15 hover:text-white"
        >
          <ScanSearch className="h-4 w-4" />
          PCB inspection
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </a>
      </header>

      <section className="mb-7">
        <div className="forge-hero rounded-2xl border border-base-700 bg-base-900/70 p-6 transition-colors duration-200 hover:border-base-600 sm:p-8">
          <div>
            <div className="label-tech mb-3 flex items-center gap-2">
              <Layers3 className="h-4 w-4 text-accent-400" />
              PCB ENGINEERING WORKSPACE
            </div>
            <h1 className="max-w-2xl font-display text-3xl font-semibold leading-tight text-[#E8EDE9] sm:text-4xl">
              PCB manufacturing, from file to build.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-base-400">
              Upload a KiCad board for DFM, Gemma 4 BOM analysis, and supplier planning.
            </p>
          </div>
        </div>
      </section>

      {projects.length > 0 && (
        <section className="mb-6 rounded-2xl border border-base-700 bg-base-900/60 p-4 sm:p-5">
          <div className="mb-3 flex items-center gap-2">
            <FolderClock className="h-4 w-4 text-accent-400" />
            <h2 className="label-tech">Saved project workspaces</h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {projects.slice(0, 6).map((p) => (
              <div key={p.id} className={`rounded-xl border bg-base-850/60 p-3 transition duration-200 hover:-translate-y-0.5 hover:shadow-md ${comparisonIds.includes(p.id) ? "border-accent-500/70" : "border-base-700 hover:border-accent-500/50"}`}>
                <button
                  onClick={() => openProject(p)}
                  disabled={loadingProject !== null}
                  className="flex w-full items-center justify-between gap-3 text-left disabled:opacity-50"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-base-200">{p.filename}</span>
                    <span className="mt-1 block font-mono text-[10px] text-base-600">
                      {p.id} · {p.has_manufacturing_request ? "request saved" : p.analyzed ? "design analyzed" : "uploaded"}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs text-accent-400">{loadingProject === p.id ? "Opening…" : "Open"}</span>
                </button>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <button
                    onClick={() => toggleComparison(p.id)}
                    disabled={!p.analyzed || deletingProject === p.id}
                    className="rounded-md border border-base-700 px-2.5 py-1 text-[10px] font-medium text-base-400 transition hover:border-accent-500/50 hover:text-accent-300 disabled:cursor-not-allowed disabled:opacity-40"
                    title={!p.analyzed ? "Analyze this board before comparing it" : "Select this project for revision comparison"}
                  >
                    {comparisonIds.includes(p.id) ? "Selected for compare" : "Compare revision"}
                  </button>
                  <button
                    onClick={() => handleDeleteProject(p)}
                    disabled={deletingProject === p.id || loadingProject === p.id}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-red-300 transition hover:bg-red-500/10 disabled:opacity-50"
                    aria-label={`Delete ${p.filename}`}
                  >
                    <Trash2 className="h-3 w-3" />
                    {deletingProject === p.id ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
          {comparisonIds.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <span className="text-xs text-base-500">Select two analyzed projects to compare board metrics, DFM status, and BOM estimates ({comparisonIds.length}/2).</span>
              <button onClick={handleCompareProjects} disabled={comparisonIds.length !== 2 || comparing} className="rounded-lg border border-accent-500/35 bg-accent-500/10 px-3 py-2 text-xs font-semibold text-accent-300 transition hover:bg-accent-500/15 disabled:opacity-40">
                {comparing ? "Comparing…" : "Compare selected"}
              </button>
            </div>
          )}
          {comparison && (
            <div className="mt-4 overflow-hidden rounded-xl border border-base-700 bg-base-900/50">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-base-700 px-4 py-3">
                <div className="text-xs font-medium text-base-200">Revision comparison <span className="text-base-500">{comparison.baseline.filename} → {comparison.current.filename}</span></div>
                <button onClick={() => setComparison(null)} className="text-xs text-base-500 hover:text-white">Close</button>
              </div>
              <div className="grid gap-3 p-4 sm:grid-cols-3">
                <div className="rounded-lg border border-base-700 p-3"><div className="label-tech">DFM status</div><div className="mt-1 text-sm text-base-200">{comparison.dfm.baseline ?? "—"} → {comparison.dfm.current ?? "—"}</div></div>
                <div className="rounded-lg border border-base-700 p-3"><div className="label-tech">BOM cost change</div><div className="mt-1 font-mono text-sm text-base-200">{comparison.bom.cost_delta_usd >= 0 ? "+" : ""}${comparison.bom.cost_delta_usd.toFixed(2)} / unit</div></div>
                <div className="rounded-lg border border-base-700 p-3"><div className="label-tech">Sourcing risks</div><div className="mt-1 text-sm text-base-200">{comparison.bom.baseline_risks ?? "—"} → {comparison.bom.current_risks ?? "—"}</div></div>
              </div>
              <div className="overflow-x-auto px-4 pb-4">
                <table className="w-full min-w-[560px] text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-base-600"><tr><th className="py-2">Board metric</th><th>Baseline</th><th>Current</th><th>Change</th></tr></thead>
                  <tbody>{comparison.metrics.map((metric) => <tr key={metric.label} className="border-t border-base-800"><td className="py-2 text-base-300">{metric.label}</td><td className="font-mono text-base-400">{metric.baseline}</td><td className="font-mono text-base-400">{metric.current}</td><td className="font-mono text-accent-300">{metric.delta > 0 ? "+" : ""}{metric.delta}</td></tr>)}</tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      <TitleBlock bundle={bundle} selectedManufacturer={selectedMfrId} />
      

      {bundle && projectId && (
        <section className="mt-3 flex flex-col gap-5 rounded-2xl border border-accent-500/25 bg-gradient-to-r from-accent-500/[0.07] to-base-900/70 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div className="flex min-w-0 items-start gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-accent-500/30 bg-accent-500/10">
              <ShieldCheck className="h-5 w-5 text-accent-400" />
            </div>
            <div>
              <div className="label-tech mb-1">MANUFACTURING RELEASE</div>
              <h2 className="font-display text-lg font-semibold text-[#E8EDE9]">Fabrication Passport</h2>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-base-400">One traceable handoff: board fingerprint, KiCad DRC report when available, manufacturer DFM findings, BOM, and fabrication files. Missing checks stay marked for review.</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-base-400">
                <span className="rounded-full border border-base-700 px-2.5 py-1">SHA-256 board identity</span>
                <span className="rounded-full border border-base-700 px-2.5 py-1">Native KiCad DRC</span>
                <span className="rounded-full border border-base-700 px-2.5 py-1">Artifact checksums</span>
              </div>
            </div>
          </div>
          <button onClick={handlePackageDownload} disabled={downloadingPackage} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-accent-500/40 bg-accent-500/10 px-4 py-3 text-sm font-semibold text-accent-300 transition hover:border-accent-400/70 hover:bg-accent-500/15 hover:text-white disabled:cursor-wait disabled:opacity-50">
            <PackageOpen className="h-4 w-4" />
            {downloadingPackage ? "Preparing passport…" : "Download passport"}
          </button>
        </section>
      )}

      {projectHistory.length > 0 && projectId && (
        <details className="mt-2 rounded-xl border border-base-700 bg-base-900/40 px-4 py-3">
          <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-base-300">
            <Clock3 className="h-4 w-4 text-accent-400" />
            Project history <span className="font-mono text-base-600">{projectHistory.length} events</span>
          </summary>
          <ol className="mt-4 space-y-3 border-l border-base-700 pl-4">
            {[...projectHistory].reverse().slice(0, 12).map((item) => (
              <li key={item.id} className="relative text-xs text-base-400">
                <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-accent-500" />
                <span className="font-medium text-base-200">{item.detail}</span>
                <span className="ml-2 font-mono text-[10px] text-base-600">{new Date(item.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ol>
        </details>
      )}

      <div className="mb-6 mt-5">
        <StepNav steps={steps} current={step} onSelect={setStep} />
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-300"
        >
          {error}
          {projectId && error.includes("uploaded KiCad board file is no longer available") && (
            <div className="mt-3">
              <button onClick={() => repairFileInputRef.current?.click()} disabled={analyzing} className="rounded-lg border border-red-300/30 px-3 py-2 text-xs font-semibold text-red-200 transition hover:bg-red-500/10 disabled:opacity-50">
                {analyzing ? "Restoring and re-analyzing…" : "Attach the board file to this workspace"}
              </button>
              <input ref={repairFileInputRef} type="file" accept=".kicad_pcb" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void handleRestoreSource(file); }} />
            </div>
          )}
        </div>
      )}

      {filename && (
        <p className="mb-4 text-xs text-base-500">
          Current board: <span className="font-mono text-base-300">{filename}</span>
        </p>
      )}

      <div className="space-y-6">
        {step === 1 && (
          <>
            <div className="rounded-xl border border-base-700 bg-base-900/50 p-4 text-sm text-base-400">
              <UploadCloud className="mr-2 inline h-4 w-4 text-accent-400" />
              Upload a KiCad PCB file to start the design review.
            </div>
            <UploadSection
              onFileReady={handleFileReady}
              isBusy={analyzing}
              filename={filename}
              onDemoBoard={handleDemoBoard}
            />
          </>
        )}

        {step === 2 && bundle && (
          <>
            <PCBOverview pcb={bundle.pcb_analysis} />
            <DFMReport dfm={bundle.dfm_result} />
            <AgentTimeline events={events} />
          </>
        )}

        {step === 3 && bundle && (
          <>
            <BOMReport bom={bundle.bom_result} />
            <ManufacturerComparison
              recommendation={bundle.recommendation}
              selectedId={selectedMfrId}
              onSelect={setSelectedMfrId}
            />
          </>
        )}

        {step === 4 && bundle && selectedQuote && (
          <>
            <div className="rounded-xl border border-base-700 bg-base-900/50 p-4 text-sm leading-6 text-base-400">
              Supplier prices and lead times are estimates for planning. Saving
              the request records it in this app; it does not charge you or place
              an order with a factory.
            </div>
            <OrderPanel
              quote={selectedQuote}
              dfm={bundle.dfm_result}
              onApprove={handleOrder}
              disabled={savingOrder || Boolean(order)}
            />
            {order && <OrderConfirmation order={order} />}
          </>
        )}

        {step > 1 && !bundle && (
          <div className="rounded-xl border border-base-700 bg-base-900/50 p-8 text-center text-sm text-base-500">
            Upload a board to unlock this workspace.
          </div>
        )}
      </div>

      <div className="mt-8 flex items-center justify-between border-t border-base-700 pt-5">
        <button
          onClick={() => setStep((n) => Math.max(1, n - 1))}
          disabled={step === 1}
          className="rounded-lg border border-base-700 px-4 py-2 text-xs font-semibold text-base-400 transition-colors hover:border-base-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
        >
          Back
        </button>
        <span className="label-tech">
          Workspace {String(step).padStart(2, "0")} / 04
        </span>
        <button
          onClick={() => setStep((n) => Math.min(4, n + 1))}
          disabled={step === 4 || !steps[step]?.unlocked}
          className="inline-flex items-center gap-2 rounded-lg border border-accent-500/40 bg-accent-500/10 px-4 py-2 text-xs font-semibold text-accent-400 transition-colors hover:border-accent-400/70 hover:bg-accent-500/15 disabled:cursor-not-allowed disabled:opacity-35"
        >
          Next <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <Footer />
    </main>
  );
}








