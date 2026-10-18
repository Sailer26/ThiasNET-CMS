import { useState, type FormEvent } from "react";
import { login, loginTotp } from "../api/auth";
import { ApiError, errorMessage } from "../api/client";
import { it } from "../text/it";

interface Props {
  initialEmail?: string;
  lockEmail?: boolean;
  onLoggedIn: () => Promise<void>;
}

const CODE_RE = /^[0-9]{6}$/;

export function LoginForm({ initialEmail = "", lockEmail = false, onLoggedIn }: Props) {
  const [step, setStep] = useState<"password" | "totp">("password");
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (failure) {
      if (failure instanceof ApiError && failure.code === "totp_expired") {
        setStep("password");
        setCode("");
      }
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  function submitPassword(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const result = await login(email.trim(), password);
      setPassword("");
      if (result.totpRequired) {
        setStep("totp");
        return;
      }
      await onLoggedIn();
    });
  }

  function submitCode(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      await loginTotp(code.trim());
      await onLoggedIn();
    });
  }

  if (step === "totp") {
    return (
      <form className="form" onSubmit={submitCode} noValidate>
        <h2>{it.login.totpTitle}</h2>
        <p className="hint">{it.login.totpHelp}</p>
        <label className="field">
          <span>{it.login.totpLabel}</span>
          <input
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            required
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
        </label>
        {error && <p className="form__error" role="alert">{error}</p>}
        <div className="form__actions">
          <button type="submit" className="button button--primary" disabled={busy || !CODE_RE.test(code.trim())}>
            {it.login.totpSubmit}
          </button>
          <button type="button" className="button" onClick={() => setStep("password")}>
            {it.login.back}
          </button>
        </div>
      </form>
    );
  }

  return (
    <form className="form" onSubmit={submitPassword} noValidate>
      <label className="field">
        <span>{it.login.email}</span>
        <input
          name="email"
          type="email"
          autoComplete="username"
          required
          readOnly={lockEmail}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </label>
      <label className="field">
        <span>{it.login.password}</span>
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>
      {error && <p className="form__error" role="alert">{error}</p>}
      <div className="form__actions">
        <button type="submit" className="button button--primary" disabled={busy || !email.trim() || !password}>
          {it.login.submit}
        </button>
      </div>
      <p className="hint">{it.login.forgot}</p>
    </form>
  );
}
