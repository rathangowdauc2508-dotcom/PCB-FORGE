/** Client for the PCB Forge manufacturing API. */

import type { AnalysisBundle, AgentEvent, ProjectComparison, ProjectSummary } from "@/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = "Request failed. Please try again.";
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function uploadPCB(file: File): Promise<{ id: string; filename: string; revision_id?: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/pcb/upload`, { method: "POST", body: form });
  return handle(res);
}

export async function uploadPCBRevision(projectId: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/pcb/projects/${encodeURIComponent(projectId)}/revisions`, { method: "POST", body: form });
  await handle(response);
}

export async function deleteProject(projectId: string): Promise<void> {
  await handle(await fetch(`${API_BASE}/api/pcb/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" }));
}

export async function getDemoBoard(): Promise<File> {
  const response = await fetch(`${API_BASE}/api/pcb/demo-board`);
  if (!response.ok) throw new Error("Could not load the included demo board. Check that the manufacturing API is running.");
  return new File([await response.blob()], "robot_controller.kicad_pcb", { type: "application/octet-stream" });
}

export async function downloadProjectPackage(projectId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/pcb/${encodeURIComponent(projectId)}/manufacturing-package`);
  if (!response.ok) {
    let detail = "Could not prepare the manufacturing package.";
    try { const body = await response.json(); detail = body.detail || detail; } catch { /* keep default */ }
    throw new Error(detail);
  }
  return response.blob();
}

export async function analyzePCB(projectId: string): Promise<AnalysisBundle> {
  const res = await fetch(`${API_BASE}/api/pcb/${projectId}/analyze`, { method: "POST" });
  return handle(res);
}

export async function getEvents(projectId: string): Promise<AgentEvent[]> {
  const res = await fetch(`${API_BASE}/api/agent/events/${projectId}`);
  return handle(res);
}

export async function createOrder(projectId: string, manufacturerId: string, quantity: number, totalPrice: number): Promise<import("@/types").PaymentCheckoutSession> {
  const res = await fetch(`${API_BASE}/api/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pcb_id: projectId, manufacturer_id: manufacturerId, quantity, total_price: totalPrice }),
  });
  return handle(res);
}

export async function savePrototypeRequest(projectId: string, manufacturerId: string, quantity: number, totalPrice: number): Promise<import("@/types").OrderResult> {
  return handle(await fetch(`${API_BASE}/api/orders/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pcb_id: projectId, manufacturer_id: manufacturerId, quantity, total_price: totalPrice }),
  }));
}
export async function verifyOrder(payment: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }): Promise<import("@/types").OrderResult> {
  return handle(await fetch(`${API_BASE}/api/orders/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payment) }));
}

export async function listProjects(): Promise<ProjectSummary[]> {
  return handle(await fetch(`${API_BASE}/api/pcb/projects`));
}

export async function getSavedProject(projectId: string): Promise<Record<string, unknown>> {
  return handle(await fetch(`${API_BASE}/api/pcb/projects/${projectId}`));
}

export async function compareProjects(baselineId: string, currentId: string): Promise<ProjectComparison> {
  const path = `/api/pcb/compare/${encodeURIComponent(baselineId)}/${encodeURIComponent(currentId)}`;
  return handle(await fetch(`${API_BASE}${path}`));
}

export async function saveProjectWorkspace(projectId: string, workspace: Record<string, unknown>): Promise<void> {
  await handle(await fetch(`${API_BASE}/api/pcb/${projectId}/workspace`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(workspace),
  }));
}

export type PCBRevision = { id: string; revision_number: number; filename: string; analysis_status: string; };
export async function listPCBRevisions(projectId: string): Promise<PCBRevision[]> {
  return handle(await fetch(API_BASE + "/api/pcb/projects/" + encodeURIComponent(projectId) + "/revisions"));
}


