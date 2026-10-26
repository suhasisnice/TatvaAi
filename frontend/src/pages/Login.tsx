import { FormEvent, useState } from "react";
import { login, User } from "../api";

const DEMO = ["inst-a", "inst-b", "inst-c", "officer", "inspector"].map((u) => `${u}@pramaan.test`);

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [needOtp, setNeedOtp] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      onLogin(await login(email, password, otp));
    } catch (err) {
      const msg = (err as Error).message;
      if (msg === "MFA_REQUIRED") setNeedOtp(true);
      else setError(msg);
    }
  }

  return (
    <form className="card login" onSubmit={submit}>
      <h1>PramaanAI</h1>
      <p className="muted">Verified disclosure for AICTE approvals. Prototype with synthetic data only.</p>
      <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required list="demo-users" autoComplete="username" /></label>
      <datalist id="demo-users">{DEMO.map((d) => <option key={d} value={d} />)}</datalist>
      <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></label>
      {needOtp && <label>Authenticator code<input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" autoFocus autoComplete="one-time-code" /></label>}
      {error && <p role="alert" className="err">{error}</p>}
      <button type="submit" className="primary">Sign in</button>
    </form>
  );
}
