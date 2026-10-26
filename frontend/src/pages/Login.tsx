import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { api } from "../lib/api";

export default function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [email, setEmail] = useState("officer@tatva.test");
  const [password, setPassword] = useState("Tatva@2026");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const session = await api.login(email, password);
      onLoggedIn();
      if (session.role === "institution") navigate("/institution");
      else if (session.role === "officer") navigate("/officer");
      else navigate("/inspector");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <ShieldCheck size={28} color="#0d5c9e" />
        <h1>TatvaAI</h1>
        <p className="sub">TatvaAI &mdash; AI-powered application validation, document authentication &amp;
          regulatory compliance verification for AICTE (SIH26261)</p>

        <label>Email</label>
        <input value={email} onChange={e => setEmail(e.target.value)} type="email" required />
        <label>Password</label>
        <input value={password} onChange={e => setPassword(e.target.value)} type="password" required />
        {error && <div className="error">{error}</div>}
        <button className="btn" style={{ width: "100%", marginTop: 18, justifyContent: "center" }} disabled={loading}>
          {loading ? "Signing in..." : "Sign in"}
        </button>

        <div className="demo-accounts">
          Demo password for every account: <code>Tatva@2026</code><br />
          <code>inst-aurora@tatva.test</code> &middot; <code>inst-bhavani@tatva.test</code> &middot; <code>inst-chandra@tatva.test</code><br />
          <code>officer@tatva.test</code> &middot; <code>inspector@tatva.test</code>
        </div>
      </form>
    </div>
  );
}
