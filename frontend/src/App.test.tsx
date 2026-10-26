import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

vi.mock("react-pdf", () => ({ Document: ({ children }: { children: unknown }) => <div data-testid="pdf">{children as never}</div>, Page: () => <canvas />, pdfjs: { GlobalWorkerOptions: {} } }));

import Login from "./pages/Login";
import Queue from "./pages/officer/Queue";
import Workbench from "./pages/officer/Workbench";

const QUEUE = [
  { application_id: 5, institution_id: 3, institution_name: "Chandra Technical Campus (Synthetic)", state: "Tamil Nadu", category: "EOA", academic_year: "2027-28", status: "SUBMITTED", submitted_at: "2027-03-01T00:00:00",
    tier: "RED", tier_label: "High risk", score: 245.05, top_reason: "LAND_DOCUMENT was changed after it was digitally signed", open_flags: 14 },
  { application_id: 3, institution_id: 2, institution_name: "Bhavani College of Engineering (Synthetic)", state: "Maharashtra", category: "EOA", academic_year: "2027-28", status: "SUBMITTED", submitted_at: "2027-03-01T00:00:00",
    tier: "AMBER", tier_label: "Medium risk", score: 30, top_reason: "Fire safety certificate is valid only till 2027-06-30", open_flags: 2 },
  { application_id: 2, institution_id: 1, institution_name: "Aurora Institute of Technology (Synthetic)", state: "Karnataka", category: "EOA", academic_year: "2027-28", status: "SUBMITTED", submitted_at: "2027-03-01T00:00:00",
    tier: "GREEN", tier_label: "No risk", score: 0, top_reason: null, open_flags: 0 },
];
const APP = { id: 5, institution_name: "Chandra Technical Campus (Synthetic)", state: "Tamil Nadu", aicte_id: "SYN-AICTE-1003", category: "EOA", academic_year: "2027-28", status: "SUBMITTED",
  risk: { tier: "RED", tier_label: "High risk", score: 245.05, routing_text: "Added to the ranked inspection list", rule_pack_version: "v1", reasons: [{ flag_id: 1, severity: "CRITICAL", message: "LAND_DOCUMENT was changed after signing", contribution: 40 }] } };
const DOCS = [{ id: 9, doc_type: "LAND_DOCUMENT", filename: "LAND_DOCUMENT.pdf", content_type: "application/pdf", dsc_status: "SIGNED_MODIFIED", proof_level: "FORENSIC_ONLY", has_ela: true }];
const FLAGS = [
  { id: 1, application_id: 5, engine: "authenticity", code: "MODIFIED_AFTER_SIGNING", severity: "CRITICAL", confidence: 1, message: "LAND_DOCUMENT was changed after it was digitally signed", explanation: "Signed revision compared.",
    evidence: [{ document_id: 9, page: 1, bbox: [0.41, 0.14, 0.52, 0.17], field: "survey_no", value: "SY-118/9C" }], rule_id: null, citation: null, status: "OPEN", forensic: false, preliminary_indicator: false, decisions: [] },
  { id: 2, application_id: 5, engine: "authenticity", code: "TAMPER_SUSPECTED", severity: "CRITICAL", confidence: 0.75, message: "survey_no is in a different font", explanation: "Preliminary indicator — requires human verification. Fonts differ.",
    evidence: [{ document_id: 9, page: 1, bbox: [0.41, 0.14, 0.52, 0.17], field: "survey_no" }], rule_id: null, citation: null, status: "OPEN", forensic: true, preliminary_indicator: true, decisions: [] },
];

const routes: Record<string, unknown> = {
  "/risk/queue": QUEUE, "/risk/stats": { by_tier: { GREEN: 1, AMBER: 1, RED: 1 }, flags_by_engine: { authenticity: 3 }, flags_by_severity: { CRITICAL: 2, MAJOR: 1 }, total_applications: 3 },
  "/applications/5": APP, "/applications/5/documents": DOCS, "/flags": FLAGS, "/alerts": { unread_count: 0, alerts: [] },
};

beforeEach(() => {
  URL.createObjectURL = () => "blob:mock";
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} }); // recharts needs it; jsdom has none
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url).replace(/^.*\/api\/v1/, "").split("?")[0];
    return new Response(JSON.stringify(routes[path] ?? {}), { status: path in routes ? 200 : 404, headers: { "content-type": "application/json" } });
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("login form renders", () => {
  render(<Login onLogin={() => {}} />);
  expect(screen.getByText("Sign in")).toBeTruthy();
});

test("officer queue lists applications with text-labelled risk tiers, highest first", async () => {
  render(<MemoryRouter><Queue /></MemoryRouter>);
  await screen.findByText("Chandra Technical Campus (Synthetic)");
  const text = document.body.textContent ?? "";
  expect(text).toContain("RED · High risk");
  expect(text).toContain("AMBER · Medium risk");
  expect(text).toContain("GREEN · No risk");
  expect(text.indexOf("Chandra")).toBeLessThan(text.indexOf("Bhavani"));
  expect(text.indexOf("Bhavani")).toBeLessThan(text.indexOf("Aurora"));
});

test("workbench shows tabs, flags with evidence, and requires a reason before a decision", async () => {
  render(
    <MemoryRouter initialEntries={["/officer/applications/5?tab=flags"]}>
      <Routes><Route path="/officer/applications/:id" element={<Workbench user={{ id: 1, email: "o@x", name: "Officer", role: "officer", institution_id: null, mfa_enabled: false }} />} /></Routes>
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "Chandra Technical Campus (Synthetic)" });
  for (const t of ["Summary", "Flags & Evidence", "Verification", "Compliance", "Infrastructure", "Timeline", "Audit"]) expect(screen.getByRole("tab", { name: t })).toBeTruthy();
  const flag = await screen.findByRole("option", { name: /MODIFIED_AFTER_SIGNING/ });
  expect(flag).toBeTruthy();
  await waitFor(() => expect(document.querySelector(".bbox")).toBeTruthy()); // evidence box drawn on the document page
  const accept = screen.getByRole("button", { name: "Accept finding" }) as HTMLButtonElement;
  expect(accept.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Confirmed against the original record" } });
  expect(accept.disabled).toBe(false);
  fireEvent.click(screen.getByRole("option", { name: /TAMPER_SUSPECTED/ }));
  expect(await screen.findAllByText(/Preliminary indicator/)).toBeTruthy();
  expect(screen.queryByText(/reject application/i, { selector: "button" })).toBeNull();
});
