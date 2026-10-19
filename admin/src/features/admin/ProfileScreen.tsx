import { useState, type FormEvent } from "react";
import { changePassword, totpDisable, totpEnable, totpSetup } from "../../api/admin";
import { errorMessage } from "../../api/client";
import { useSession } from "../../session/context";
import { at } from "../../text/admin";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { useAction } from "../../ui/useAction";

const MIN_PASSWORD = 12;
const CODE_RE = /^[0-9]{6}$/;

function groups(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

interface CodeProps {
  code: string;
  password: string;
  onCode: (value: string) => void;
  onPassword: (value: string) => void;
}

function CodeFields({ code, password, onCode, onPassword }: CodeProps) {
  return (
    <>
      <label className="field">
        <span>{at.profile.code}</span>
        <input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => onCode(event.target.value)} />
      </label>
      <label className="field">
        <span>{at.profile.confirmPassword}</span>
        <input type="password" autoComplete="current-password" value={password} onChange={(event) => onPassword(event.target.value)} />
      </label>
    </>
  );
}

/** Profilo (D-125): password, codice a 6 cifre, uscita da tutti i dispositivi. */
export function ProfileScreen() {
  const { user, logoutEverywhere } = useSession();
  const [totpOn, setTotpOn] = useState(user.totp_enabled);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [disabling, setDisabling] = useState(false);
  const [starting, setStarting] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const passwordForm = useAction();
  const totpForm = useAction();

  function submitPassword(event: FormEvent) {
    event.preventDefault();
    if (next !== repeat) {
      setNotice({ kind: "error", text: at.profile.mismatch });
      return;
    }
    void passwordForm.run(async () => {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setRepeat("");
      setNotice({ kind: "success", text: at.profile.changed });
    });
  }

  function startTotp() {
    if (starting) return; // un doppio clic creerebbe due chiavi diverse
    setStarting(true);
    setCode("");
    setPassword("");
    totpSetup()
      .then(setSetup, (error: unknown) => setNotice({ kind: "error", text: errorMessage(error) }))
      .finally(() => setStarting(false));
  }

  function enableTotp(event: FormEvent) {
    event.preventDefault();
    void totpForm.run(async () => {
      await totpEnable(code.trim(), password);
      setSetup(null);
      setCode("");
      setPassword("");
      setTotpOn(true); // confermato dal server: niente seconda richiesta che potrebbe fallire
      setNotice({ kind: "success", text: at.profile.enabled });
    });
  }

  function copySecret(secret: string) {
    const clipboard = navigator.clipboard as Clipboard | undefined;
    clipboard?.writeText(secret).catch(() => undefined); // la chiave resta comunque visibile
  }

  return (
    <section className="screen profile" aria-labelledby="profile-title">
      <div className="screen__head">
        <h1 id="profile-title" tabIndex={-1}>
          {at.profile.title}
        </h1>
      </div>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />

      <section className="card" aria-labelledby="profile-account">
        <h2 id="profile-account">{at.profile.account}</h2>
        <p>
          <strong>{user.email}</strong>
        </p>
        <p className="hint">{at.profile.emailNote}</p>
      </section>

      <section className="card" aria-labelledby="profile-password">
        <h2 id="profile-password">{at.profile.password}</h2>
        <form className="form" onSubmit={submitPassword} noValidate>
          <label className="field">
            <span>{at.profile.current}</span>
            <input type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} />
          </label>
          <label className="field">
            <span>{at.profile.next}</span>
            <input type="password" autoComplete="new-password" maxLength={128} value={next} onChange={(event) => setNext(event.target.value)} />
          </label>
          <label className="field">
            <span>{at.profile.repeat}</span>
            <input type="password" autoComplete="new-password" maxLength={128} value={repeat} onChange={(event) => setRepeat(event.target.value)} />
          </label>
          {passwordForm.error && (
            <p className="form__error" role="alert">
              {passwordForm.error}
            </p>
          )}
          <div className="form__actions">
            <button type="submit" className="button button--primary" disabled={passwordForm.busy || !current || next.length < MIN_PASSWORD}>
              {at.profile.change}
            </button>
          </div>
        </form>
      </section>

      <section className="card" aria-labelledby="profile-totp">
        <h2 id="profile-totp">{at.profile.totp}</h2>
        <p>{totpOn ? at.profile.totpOn : at.profile.totpOff}</p>
        {!totpOn && !setup && (
          <button type="button" className="button" onClick={startTotp} disabled={starting}>
            {at.profile.enable}
          </button>
        )}
        {!totpOn && setup && (
          <form className="form" noValidate onSubmit={enableTotp}>
            <p className="hint">{at.profile.secretHelp}</p>
            <p>
              {at.profile.secret}: <code className="secret">{groups(setup.secret)}</code>{" "}
              <button type="button" className="button button--small" onClick={() => copySecret(setup.secret)}>
                {at.users.copy}
              </button>
            </p>
            {setup.otpauth_uri.startsWith("otpauth://") && (
              <p>
                <a href={setup.otpauth_uri}>{at.profile.openApp}</a>
              </p>
            )}
            <CodeFields code={code} password={password} onCode={setCode} onPassword={setPassword} />
            {totpForm.error && (
              <p className="form__error" role="alert">
                {totpForm.error}
              </p>
            )}
            <div className="form__actions">
              <button type="submit" className="button button--primary" disabled={totpForm.busy || !CODE_RE.test(code.trim()) || !password}>
                {at.profile.enable}
              </button>
            </div>
          </form>
        )}
        {totpOn && (
          <button
            type="button"
            className="button"
            onClick={() => {
              setCode("");
              setPassword("");
              setDisabling(true);
            }}
          >
            {at.profile.disable}
          </button>
        )}
      </section>

      <section className="card" aria-labelledby="profile-devices">
        <h2 id="profile-devices">{at.profile.devices}</h2>
        <button type="button" className="button button--danger" onClick={() => setLeaving(true)}>
          {at.profile.logoutAll}
        </button>
      </section>

      {disabling && (
        <FormDialog
          title={at.profile.disable}
          submitLabel={at.profile.disable}
          danger
          canSubmit={CODE_RE.test(code.trim()) && password.length > 0}
          onClose={() => setDisabling(false)}
          onSubmit={async () => {
            await totpDisable(code.trim(), password);
            setDisabling(false);
            setCode("");
            setPassword("");
            setTotpOn(false);
            setNotice({ kind: "success", text: at.profile.disabled });
          }}
        >
          <CodeFields code={code} password={password} onCode={setCode} onPassword={setPassword} />
        </FormDialog>
      )}
      {leaving && (
        <FormDialog title={at.profile.logoutAll} submitLabel={at.profile.logoutAll} danger onClose={() => setLeaving(false)} onSubmit={logoutEverywhere}>
          <p>{at.profile.logoutAllText}</p>
        </FormDialog>
      )}
    </section>
  );
}
