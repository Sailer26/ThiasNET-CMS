import { useCallback, useEffect, useState } from "react";
import { createUser, listUsers, resetTotp, updateUser } from "../../api/admin";
import { ApiError, errorMessage } from "../../api/client";
import type { User } from "../../api/types";
import { Link } from "../../router/Link";
import { paths } from "../../router/router";
import { useSession } from "../../session/context";
import { at } from "../../text/admin";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { formatZurich } from "../editor/schedule/siteTime";
import { generatePassword } from "./password";
import { PasswordField } from "./PasswordField";

const MIN_PASSWORD = 12;

type Dialog = { kind: "create" } | { kind: "edit" | "toggle" | "password" | "totp"; user: User };
type EditableRole = "admin" | "editor";

/** Utenti (D-123): l'owner sceglie il ruolo, l'admin crea solo editor; nessuna eliminazione. */
export function UsersScreen() {
  const { user: me } = useSession();
  const isOwner = me.role === "owner";
  const [users, setUsers] = useState<User[] | null>(null);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<EditableRole>("editor");
  const [canPublish, setCanPublish] = useState(false);
  const [password, setPassword] = useState("");

  const reload = useCallback(
    () =>
      listUsers().then(
        (found) => setUsers(found.items),
        (error: unknown) => setNotice({ kind: "error", text: errorMessage(error) }),
      ),
    [],
  );

  useEffect(() => {
    void reload();
  }, [reload]);

  function open(next: Dialog) {
    const target = next.kind === "create" ? null : next.user;
    setEmail(target?.email ?? "");
    setRole(target?.role === "admin" ? "admin" : "editor");
    setCanPublish(target?.can_publish ?? false);
    setPassword(next.kind === "create" || next.kind === "password" ? generatePassword() : "");
    setNotice(null);
    setDialog(next);
  }

  async function done(text: string) {
    setDialog(null);
    setPassword("");
    setNotice({ kind: "success", text });
    await reload();
  }

  const roleField = isOwner && (
    <label className="field">
      <span>{at.users.role}</span>
      <select value={role} onChange={(event) => setRole(event.target.value === "admin" ? "admin" : "editor")}>
        <option value="editor">{at.users.roles.editor}</option>
        <option value="admin">{at.users.roles.admin}</option>
      </select>
    </label>
  );
  const publishField = role === "editor" && (
    <div className="field field--check">
      <label>
        <input type="checkbox" checked={canPublish} onChange={(event) => setCanPublish(event.target.checked)} />
        {at.users.canPublish}
      </label>
    </div>
  );

  async function create() {
    const address = email.trim();
    try {
      await createUser({
        email: address,
        password,
        role: isOwner ? role : "editor",
        can_publish: (isOwner ? role : "editor") === "editor" && canPublish,
      });
    } catch (error) {
      if (error instanceof ApiError && error.code === "email_taken") {
        throw new ApiError(error.status, error.code, `${error.message} ${at.users.emailTaken}`);
      }
      throw error;
    }
    await done(at.users.created(address));
  }

  async function edit(target: User) {
    const changes: Parameters<typeof updateUser>[1] = {};
    const address = email.trim();
    if (address !== target.email) changes.email = address;
    if (isOwner && role !== target.role) changes.role = role;
    if (role === "editor" && canPublish !== target.can_publish) changes.can_publish = canPublish;
    if (Object.keys(changes).length > 0) await updateUser(target.id, changes);
    await done(at.users.saved);
  }

  return (
    <section className="screen" aria-labelledby="users-title">
      <div className="screen__head">
        <h1 id="users-title" tabIndex={-1}>
          {at.users.title}
        </h1>
        <button type="button" className="button button--primary" onClick={() => open({ kind: "create" })}>
          {at.users.newUser}
        </button>
      </div>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      {users === null && <p role="status">{at.loading}</p>}
      {users && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{at.users.email}</th>
                <th scope="col">{at.users.role}</th>
                <th scope="col">{at.users.canPublish}</th>
                <th scope="col">{at.users.status}</th>
                <th scope="col">{at.users.totp}</th>
                <th scope="col">{at.users.lastLogin}</th>
                <th scope="col">
                  <span className="visually-hidden">{at.users.edit}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <UserRow key={user.id} user={user} self={user.id === me.id} onAction={open} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialog?.kind === "create" && (
        <FormDialog
          title={at.users.newUser}
          submitLabel={at.users.create}
          canSubmit={email.trim().length > 0 && password.length >= MIN_PASSWORD}
          onClose={() => setDialog(null)}
          onSubmit={create}
        >
          <label className="field">
            <span>{at.users.email}</span>
            <input type="email" autoComplete="off" maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          {roleField}
          {publishField}
          <PasswordField value={password} onChange={setPassword} />
        </FormDialog>
      )}
      {dialog?.kind === "edit" && (
        <FormDialog
          title={`${at.users.edit}: ${dialog.user.email}`}
          submitLabel={at.users.save}
          canSubmit={email.trim().length > 0}
          onClose={() => setDialog(null)}
          onSubmit={() => edit(dialog.user)}
        >
          <label className="field">
            <span>{at.users.email}</span>
            <input type="email" autoComplete="off" maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          {roleField}
          {publishField}
        </FormDialog>
      )}
      {dialog?.kind === "toggle" && (
        <FormDialog
          title={`${dialog.user.active ? at.users.deactivate : at.users.reactivate}: ${dialog.user.email}`}
          submitLabel={dialog.user.active ? at.users.deactivate : at.users.reactivate}
          danger={dialog.user.active}
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await updateUser(dialog.user.id, { active: !dialog.user.active });
            await done(at.users.saved);
          }}
        >
          {dialog.user.active && <p>{at.users.deactivateText(dialog.user.email)}</p>}
        </FormDialog>
      )}
      {dialog?.kind === "password" && (
        <FormDialog
          title={`${at.users.newPassword}: ${dialog.user.email}`}
          submitLabel={at.users.save}
          canSubmit={password.length >= MIN_PASSWORD}
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await updateUser(dialog.user.id, { password });
            await done(at.users.saved);
          }}
        >
          <p>{at.users.newPasswordText}</p>
          <PasswordField value={password} onChange={setPassword} />
        </FormDialog>
      )}
      {dialog?.kind === "totp" && (
        <FormDialog
          title={`${at.users.resetTotp}: ${dialog.user.email}`}
          submitLabel={at.users.confirm}
          danger
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await resetTotp(dialog.user.id);
            await done(at.users.saved);
          }}
        >
          <p>{at.users.resetTotpText}</p>
        </FormDialog>
      )}
    </section>
  );
}

interface RowProps {
  user: User;
  self: boolean;
  onAction: (dialog: Dialog) => void;
}

function UserRow({ user, self, onAction }: RowProps) {
  const publishes = user.role !== "editor" || user.can_publish;
  return (
    <tr>
      <td>{user.email}</td>
      <td>{at.users.roles[user.role]}</td>
      <td>{publishes ? at.users.yes : at.users.no}</td>
      <td>{user.active ? at.users.active : at.users.inactive}</td>
      <td>{user.totp_enabled ? at.users.yes : at.users.no}</td>
      <td>{user.last_login_at ? formatZurich(user.last_login_at) : at.users.never}</td>
      <td>
        {self && (
          <span>
            {at.users.you} · <Link to={paths.profile}>{at.users.yourProfile}</Link>
          </span>
        )}
        {!self && user.role !== "owner" && (
          <div className="row-actions" role="group" aria-label={at.users.actions(user.email)}>
            <button type="button" className="button button--small" onClick={() => onAction({ kind: "edit", user })}>
              {at.users.edit}
            </button>
            <button type="button" className="button button--small" onClick={() => onAction({ kind: "toggle", user })}>
              {user.active ? at.users.deactivate : at.users.reactivate}
            </button>
            <button type="button" className="button button--small" onClick={() => onAction({ kind: "password", user })}>
              {at.users.newPassword}
            </button>
            {user.totp_enabled && (
              <button type="button" className="button button--small" onClick={() => onAction({ kind: "totp", user })}>
                {at.users.resetTotp}
              </button>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}
