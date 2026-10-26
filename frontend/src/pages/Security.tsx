import { FormEvent, useState } from "react";
import { api, J, post, User } from "../api";
import { ErrorBox } from "../ui";

export default function Security({ user, onChange }: { user: User; onChange: (u: User) => void }) {
  const [setup, setSetup] = useState<J>(null);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(user.mfa_enabled);
  const start = () => post("/mfa/setup").then(setSetup).catch((e) => setError(e.message));
  const verify = async (e: FormEvent) => {
    e.preventDefault();
    try { await post("/mfa/verify", { otp }); setDone(true); onChange(await api<User>("/auth/me")); } catch (err) { setError((err as Error).message); }
  };
  return (
    <div className="card narrow">
      <h2>Security</h2>
      <p>Account: <strong>{user.email}</strong> ({user.role})</p>
      {done ? <p className="ok">Two-factor authentication (TOTP) is enabled. You will be asked for a code at every sign-in.</p> : (
        <>
          <p>Add an authenticator app (any TOTP app). Officers should enable this.</p>
          {!setup ? <button className="primary" onClick={start}>Start setup</button> : (
            <form onSubmit={verify} className="stack">
              <img alt="Scan this QR code with your authenticator app" src={`data:image/png;base64,${setup.qr_png_base64}`} width={180} height={180} />
              <p className="muted">Or enter this key manually: <code>{setup.secret}</code></p>
              <label>6-digit code<input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" required /></label>
              <button className="primary" type="submit">Verify and enable</button>
            </form>
          )}
        </>
      )}
      <ErrorBox message={error} />
    </div>
  );
}
