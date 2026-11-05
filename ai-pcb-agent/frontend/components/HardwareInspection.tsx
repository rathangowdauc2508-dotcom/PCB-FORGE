"use client";

import { useEffect, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { AlertTriangle, Bot, Camera, CheckCircle2, FileImage, FileText, LoaderCircle, ScanLine, Sparkles, X } from "lucide-react";
import type { AnalysisBundle, HardwareInspectionResult, IntegratedBuildPlan } from "@/types";
import { saveProjectWorkspace } from "@/lib/api";

const INSPECTION_API = process.env.NEXT_PUBLIC_INSPECTION_API_URL || "http://localhost:8001";
type Uploaded = { file_name: string; mime_type: string; base64_data: string };

async function encodeFile(file: File): Promise<Uploaded> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return { file_name: file.name, mime_type: file.type || "application/octet-stream", base64_data: btoa(binary) };
}

function encodeText(value: string, filename: string): Uploaded {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return { file_name: filename, mime_type: "text/plain", base64_data: btoa(binary) };
}

async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${INSPECTION_API}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let message = `Inspection service returned ${response.status}`;
    try { const body = await response.json(); message = body.detail || body.message || message; } catch { /* retain status */ }
    throw new Error(message);
  }
  return response.json();
}

interface Props {
  projectId: string;
  filename: string;
  analysis: AnalysisBundle;
  inspection: HardwareInspectionResult | null;
  setInspection: (value: HardwareInspectionResult) => void;
  plan: IntegratedBuildPlan | null;
  setPlan: (value: IntegratedBuildPlan | null) => void;
  onSaved?: () => void;
}

export default function HardwareInspection({ projectId, filename, analysis, inspection, setInspection, plan, setPlan, onSaved }: Props) {
  const [designImage, setDesignImage] = useState<File | null>(null);
  const [testedImage, setTestedImage] = useState<File | null>(null);
  const [specFile, setSpecFile] = useState<File | null>(null);
  const [specText, setSpecText] = useState("");
  const [observations, setObservations] = useState("");
  const [testReadings, setTestReadings] = useState({ supplyVoltage: "", boardTemperature: "", continuity: "", i2cStatus: "" });

  const [busy, setBusy] = useState<"inspection" | "plan" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);

  useEffect(() => () => {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  useEffect(() => {
    if (cameraOpen && videoRef.current && cameraStreamRef.current) {
      videoRef.current.srcObject = cameraStreamRef.current;
      void videoRef.current.play().catch(() => undefined);
    }
  }, [cameraOpen]);

  async function openCamera() {
    setCameraError(null);
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser does not provide camera access. Use localhost or HTTPS, or upload a photo instead.");
      cameraStreamRef.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      setCameraOpen(true);
    } catch (e) {
      setCameraError(e instanceof Error ? e.message : "Could not open the camera. Check browser permissions.");
    }
  }

  function closeCamera() {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
    setCameraOpen(false);
  }

  function captureBoard() {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) {
      setCameraError("Wait for the camera preview to appear, then try again.");
      return;
    }
    const scale = Math.min(1, 1600 / video.videoWidth);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) {
        setCameraError("Could not capture the camera image.");
        return;
      }
      setTestedImage(new File([blob], "pcb-camera-capture.jpg", { type: "image/jpeg" }));
      closeCamera();
    }, "image/jpeg", 0.9);
  }

  async function loadSampleCase() {
    setError(null);
    try {
      const fetchImage = async (name: string) => {
        const response = await fetch(`${INSPECTION_API}/images/${name}`);
        if (!response.ok) throw new Error("Could not load the sample board images. Check that the inspection API is running.");
        return new File([await response.blob()], name, { type: "image/png" });
      };
      const [design, tested] = await Promise.all([fetchImage("template_board.png"), fetchImage("tested_board.png")]);
      setDesignImage(design); setTestedImage(tested);
      setObservations("Intermittent I2C failure: SDA is reported stuck LOW after board validation.");
      setSpecFile(null);
      setSpecText("IPC-2221B Section 6.1. For low-voltage 5V logic traces, maintain at least 0.10 mm spacing. Prevent residual copper bridges between SDA/SCL and neighboring GND references. Verify etching and wash processes to prevent conductive residue.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load the sample inspection case."); }
  }

  async function runInspection() {
    setError(null);
    if (!designImage || !testedImage) { setError("Choose both the CAD or reference image and a photo of the tested PCB."); return; }
    if (!observations.trim()) { setError("Describe the hardware symptom or test observation so the agents know what to investigate."); return; }
    if (!specFile && !specText.trim()) { setError("Add a relevant hardware specification file or paste the requirement text."); return; }
    setBusy("inspection");
    try {
      const [design, tested, spec] = await Promise.all([
        encodeFile(designImage), encodeFile(testedImage), specFile ? encodeFile(specFile) : Promise.resolve(encodeText(specText, "board-requirements.txt")),
      ]);
      const readings = [
        testReadings.supplyVoltage && `Supply voltage: ${testReadings.supplyVoltage} V`,
        testReadings.boardTemperature && `Board temperature: ${testReadings.boardTemperature} °C`,
        testReadings.continuity && `Continuity test: ${testReadings.continuity}`,
        testReadings.i2cStatus && `I2C test: ${testReadings.i2cStatus}`,
      ].filter(Boolean).join("\n");
      const errorLog = encodeText(`PCB project: ${filename} (project ${projectId})\nHardware observation: ${observations.trim()}${readings ? `\nRecorded test readings:\n${readings}` : ""}`, "hardware-test-log.txt");
      const result = await apiPost<HardwareInspectionResult>("/orchestrate/uploaded", {
        input: {
          error_log_file: errorLog,
          design_image_file: design,
          tested_image_file: tested,
          spec_files: [spec],
          design_reference_files: [],
        },
        options: { include_raw_agent_payloads: true },
      });
      setInspection(result);
      setPlan(null);
      await saveProjectWorkspace(projectId, { physical_inspection: result, build_plan: null });
      onSaved?.();
    } catch (e) { setError(e instanceof Error ? e.message : "Hardware inspection failed."); }
    finally { setBusy(null); }
  }

  async function generateBuildPlan() {
    if (!inspection) return;
    setError(null); setBusy("plan");
    try {
      const result = await apiPost<IntegratedBuildPlan>("/ecosystem/build-plan", {
        project_id: projectId,
        pcb_analysis: analysis.pcb_analysis,
        dfm_result: analysis.dfm_result,
        bom_result: analysis.bom_result,
        manufacturing_recommendation: analysis.recommendation,
        physical_inspection: inspection.output,
      });
      setPlan(result);
      await saveProjectWorkspace(projectId, { physical_inspection: inspection, build_plan: result });
      onSaved?.();
    } catch (e) { setError(e instanceof Error ? e.message : "Gemma 4 build plan failed."); }
    finally { setBusy(null); }
  }

  const hasInspection = Boolean(inspection);
  return <div className="space-y-5">
    <section className="rounded-2xl border border-base-700 bg-base-900/70 p-5 sm:p-7">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div><div className="label-tech flex items-center gap-2"><ScanLine className="h-4 w-4 text-accent-400" /> Hardware validation · Gemma 4</div><h2 className="mt-2 font-display text-2xl font-semibold text-[#E8EDE9]">Bring the physical board into the loop</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-base-400">Five vision and specification agents compare your CAD image with the tested board, investigate the failure, then a sixth Gemma agent combines those findings with this project’s KiCad, DFM, BOM, and supplier data.</p></div>
        <span className="inline-flex items-center rounded-lg border border-base-700 bg-base-850 px-3 py-2 text-xs text-base-400">Gemma 4 · best available</span>
      </div>
      <button type="button" onClick={loadSampleCase} disabled={busy !== null} className="mb-4 inline-flex items-center gap-2 rounded-lg border border-base-700 px-3 py-2 text-xs font-medium text-base-300 transition hover:border-accent-500/50 hover:text-white disabled:opacity-50"><Sparkles className="h-3.5 w-3.5 text-accent-400" />Load included demo board and test case</button>
      <div className="mb-5 grid gap-3 rounded-xl border border-base-700 bg-base-850/70 p-4 sm:grid-cols-3">
        <UploadField label="CAD / reference image" hint="Top-down render or schematic image" accept="image/png,image/jpeg,image/webp" file={designImage} setFile={setDesignImage} icon={<FileImage className="h-4 w-4" />} />
        <UploadField label="Tested hardware image" hint="Clear photo of assembled board" accept="image/png,image/jpeg,image/webp" file={testedImage} setFile={setTestedImage} icon={<ScanLine className="h-4 w-4" />} />
        <UploadField label="Specification document" hint="PDF, or paste text below" accept="application/pdf,.pdf,.txt,.md" file={specFile} setFile={setSpecFile} icon={<FileText className="h-4 w-4" />} />
      </div>
      <div className="mb-5">
        {!cameraOpen ? (
          <button type="button" onClick={openCamera} disabled={busy !== null} className="inline-flex items-center gap-2 rounded-lg border border-accent-500/30 bg-accent-500/5 px-3 py-2 text-xs font-medium text-accent-300 transition hover:border-accent-400/60 hover:bg-accent-500/10 disabled:opacity-50">
            <Camera className="h-4 w-4" /> Capture PCB with camera
          </button>
        ) : (
          <div className="max-w-2xl rounded-xl border border-base-700 bg-base-950 p-3">
            <video ref={videoRef} autoPlay playsInline muted className="max-h-[420px] w-full rounded-lg bg-black object-contain" />
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={captureBoard} className="inline-flex items-center gap-2 rounded-lg bg-accent-500 px-4 py-2 text-xs font-semibold text-base-950 hover:bg-accent-400"><Camera className="h-4 w-4" /> Capture image</button>
              <button type="button" onClick={closeCamera} className="inline-flex items-center gap-2 rounded-lg border border-base-700 px-3 py-2 text-xs text-base-300 hover:border-base-500"><X className="h-3.5 w-3.5" /> Cancel</button>
            </div>
          </div>
        )}
        {cameraError && <p role="alert" className="mt-2 text-xs text-amber-300">{cameraError}</p>}
      </div>
      <label className="mb-4 block text-xs font-semibold uppercase tracking-wider text-base-500">Observed behavior or test failure<textarea className="mt-2 min-h-24 w-full rounded-xl border border-base-700 bg-base-850 p-3 text-sm leading-6 text-base-200 placeholder:text-base-600 focus:border-accent-500 focus:outline-none" value={observations} onChange={e => setObservations(e.target.value)} placeholder="Example: The sensor board intermittently loses I²C communication after 3 minutes. Mention the test step, error code, or symptom." /></label>
      <div className="mb-5 rounded-xl border border-base-700 bg-base-850/50 p-4">
        <div className="mb-3"><h3 className="text-xs font-semibold uppercase tracking-wider text-base-400">Optional physical test readings</h3><p className="mt-1 text-[11px] text-base-600">Enter readings from a multimeter or test fixture. Gemma receives them as operator-provided evidence.</p></div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-[11px] text-base-500">Supply voltage (V)<input type="number" step="0.01" value={testReadings.supplyVoltage} onChange={e => setTestReadings({ ...testReadings, supplyVoltage: e.target.value })} placeholder="3.30" className="mt-1 w-full rounded-lg border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-200 outline-none focus:border-accent-500" /></label>
          <label className="text-[11px] text-base-500">Board temperature (°C)<input type="number" step="0.1" value={testReadings.boardTemperature} onChange={e => setTestReadings({ ...testReadings, boardTemperature: e.target.value })} placeholder="38.5" className="mt-1 w-full rounded-lg border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-200 outline-none focus:border-accent-500" /></label>
          <label className="text-[11px] text-base-500">Continuity<select value={testReadings.continuity} onChange={e => setTestReadings({ ...testReadings, continuity: e.target.value })} className="mt-1 w-full rounded-lg border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-200 outline-none focus:border-accent-500"><option value="">Not recorded</option><option>Passed</option><option>Failed</option><option>Intermittent</option></select></label>
          <label className="text-[11px] text-base-500">I²C / bus test<select value={testReadings.i2cStatus} onChange={e => setTestReadings({ ...testReadings, i2cStatus: e.target.value })} className="mt-1 w-full rounded-lg border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-200 outline-none focus:border-accent-500"><option value="">Not recorded</option><option>Passed</option><option>Failed</option><option>Intermittent</option></select></label>
        </div>
      </div>
      <label className="mb-4 block text-xs font-semibold uppercase tracking-wider text-base-500">Specification text <span className="font-normal normal-case tracking-normal">(required when no PDF is selected)</span><textarea className="mt-2 min-h-24 w-full rounded-xl border border-base-700 bg-base-850 p-3 text-sm leading-6 text-base-200 placeholder:text-base-600 focus:border-accent-500 focus:outline-none" value={specText} onChange={e => setSpecText(e.target.value)} placeholder="Paste the relevant IPC, electrical, thermal, or board-specific requirements." /></label>
      {error && <div role="alert" className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
      <button onClick={runInspection} disabled={busy !== null} className="inline-flex items-center gap-2 rounded-xl bg-accent-500 px-5 py-3 text-sm font-semibold text-base-950 transition hover:bg-accent-400 disabled:cursor-wait disabled:opacity-60">{busy === "inspection" ? <><LoaderCircle className="h-4 w-4 animate-spin" /> Running vision and spec agents…</> : <><Sparkles className="h-4 w-4" /> Run Gemma 4 hardware inspection</>}</button>
      <p className="mt-3 text-[11px] leading-5 text-base-600">Images and specification content are sent to the configured Gemma 4 inspection API. Confirm you are allowed to share the files before submitting.</p>
    </section>

    {inspection && <>
      <section className="rounded-2xl border border-accent-500/30 bg-base-900/80 p-5 sm:p-7">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><div className="label-tech">Gemma 4 inspection result · {inspection.model_used}</div><h3 className="mt-2 font-display text-xl font-semibold text-[#E8EDE9]">{inspection.output.root_cause}</h3></div><span className="rounded-full border border-accent-500/30 bg-accent-500/10 px-3 py-1 font-mono text-xs text-accent-400">{Math.round(inspection.output.confidence * 100)}% confidence</span></div>
        <p className="mb-5 text-sm leading-6 text-base-300">{inspection.output.impact}</p>
        {inspection.annotated_tested_image && <img className="mb-5 max-h-[480px] w-full rounded-xl border border-base-700 bg-base-950 object-contain" src={`data:image/png;base64,${inspection.annotated_tested_image}`} alt="Gemma and computer vision inspection annotations over the tested PCB" />}
        <div className="grid gap-5 md:grid-cols-2"><div><h4 className="label-tech mb-3">Specialist agent trace</h4><ol className="space-y-2">{inspection.agent_trace.map((agent, i) => <li key={agent.agent_id} className="flex items-start gap-3 rounded-lg border border-base-700 bg-base-850/60 p-3"><span className="font-mono text-xs text-accent-400">0{i + 1}</span><div><div className="text-sm font-medium text-base-200">{agent.agent_name}</div>{agent.handoff_message && <p className="mt-1 text-xs leading-5 text-base-500">{agent.handoff_message}</p>}</div></li>)}</ol></div><div><h4 className="label-tech mb-3">Resolution steps</h4><ol className="space-y-2">{inspection.output.resolution.map((item, i) => <li key={i} className="flex gap-3 rounded-lg border border-base-700 bg-base-850/60 p-3 text-sm leading-5 text-base-300"><span className="font-mono text-xs text-accent-400">{String(i + 1).padStart(2, "0")}</span>{item}</li>)}</ol></div></div>
      </section>
      <section className="rounded-2xl border border-base-700 bg-base-900/70 p-5 sm:p-7"><div className="flex flex-wrap items-center justify-between gap-4"><div><div className="label-tech flex items-center gap-2"><Bot className="h-4 w-4 text-accent-400" /> Unified design-to-hardware agent</div><h3 className="mt-2 font-display text-xl font-semibold text-[#E8EDE9]">Generate the prototype build plan</h3><p className="mt-1 text-sm text-base-500">Grounded in the actual board parse, DFM checks, BOM, supplier options, and physical inspection.</p></div><button onClick={generateBuildPlan} disabled={busy !== null} className="inline-flex items-center gap-2 rounded-xl border border-accent-500/40 bg-accent-500/10 px-4 py-3 text-sm font-semibold text-accent-400 hover:bg-accent-500/15 disabled:opacity-50">{busy === "plan" ? <><LoaderCircle className="h-4 w-4 animate-spin" /> Building plan…</> : <><Sparkles className="h-4 w-4" /> {plan ? "Regenerate plan" : "Generate with Gemma 4"}</>}</button></div></section>
      {plan && <section className="rounded-2xl border border-base-700 bg-base-900/80 p-5 sm:p-7"><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><div className="label-tech">Integrated build plan · {plan.model_used}</div><h3 className="mt-2 font-display text-xl font-semibold text-[#E8EDE9]">{plan.build_plan.manufacturing_readiness.replaceAll("_", " ")}</h3></div><span className="inline-flex items-center gap-2 rounded-full border border-green-500/25 bg-green-500/5 px-3 py-1 text-xs text-green-300"><CheckCircle2 className="h-4 w-4" /> Project plan saved</span></div><p className="mb-6 max-w-4xl text-sm leading-6 text-base-300">{plan.build_plan.executive_summary}</p><div className="grid gap-5 md:grid-cols-2"><PlanList title="Design risks" items={plan.build_plan.design_risks} /><PlanList title="Physical quality findings" items={plan.build_plan.quality_findings} /><div><h4 className="label-tech mb-3">Prioritized actions</h4><ul className="space-y-2">{plan.build_plan.recommended_actions.map((item, i) => <li key={i} className="rounded-lg border border-base-700 bg-base-850/60 p-3"><div className="flex items-center gap-2"><span className={`rounded px-2 py-0.5 font-mono text-[10px] ${item.priority === "HIGH" ? "bg-red-500/10 text-red-300" : item.priority === "MEDIUM" ? "bg-yellow-500/10 text-yellow-300" : "bg-green-500/10 text-green-300"}`}>{item.priority}</span><span className="text-sm font-medium text-base-200">{item.action}</span></div><p className="mt-1 pl-2 text-xs leading-5 text-base-500">{item.reason}</p></li>)}</ul></div><PlanList title="Prototype verification checklist" items={plan.build_plan.prototype_checklist} /></div></section>}
    </>}
  </div>;
}

function UploadField({ label, hint, accept, file, setFile, icon }: { label: string; hint: string; accept: string; file: File | null; setFile: (file: File | null) => void; icon: ReactNode }) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] ?? null); }
  return <label className="group flex min-h-32 cursor-pointer flex-col justify-between rounded-xl border border-dashed border-base-600 p-4 transition hover:border-accent-500/70"><input className="sr-only" type="file" accept={accept} onChange={handleChange} /><div className="flex items-center gap-2 text-xs font-semibold text-base-300">{icon}{label}</div><div><div className="truncate text-sm text-accent-400">{file?.name || "Choose file"}</div><div className="mt-1 text-[11px] text-base-600">{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : hint}</div></div></label>;
}

function PlanList({ title, items }: { title: string; items: string[] }) {
  return <div><h4 className="label-tech mb-3">{title}</h4>{items.length ? <ul className="space-y-2">{items.map((item, i) => <li key={i} className="flex gap-2 rounded-lg border border-base-700 bg-base-850/60 p-3 text-sm leading-5 text-base-300"><span className="text-accent-400">·</span>{item}</li>)}</ul> : <p className="rounded-lg border border-base-700 bg-base-850/60 p-3 text-sm text-base-500">No issues reported from the provided evidence.</p>}</div>;
}
