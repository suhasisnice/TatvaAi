export function TierBadge({ tier }: { tier: string | null }) {
  if (!tier) return <span className="tier-badge" style={{ background: "#eee", color: "#777" }}>DRAFT</span>;
  const label = tier === "GREEN" ? "No risk" : tier === "AMBER" ? "Medium risk" : "High risk";
  return <span className={`tier-badge tier-${tier}`}>{tier} &middot; {label}</span>;
}

export function SevBadge({ severity }: { severity: string }) {
  return <span className={`sev-badge sev-${severity}`}>{severity}</span>;
}
