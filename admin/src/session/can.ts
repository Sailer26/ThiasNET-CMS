// Nomi dei permessi del server (app/services/permissions.py). Il server decide sempre:
// qui servono solo a non mostrare pulsanti inutili.
export const Permission = {
  edit: "content.edit",
  publish: "content.publish",
  usersView: "users.view",
  auditView: "audit.view",
  usersManage: "users.manage",
  messagesView: "messages.view",
  settingsEdit: "settings.edit",
} as const;

export type PermissionName = (typeof Permission)[keyof typeof Permission];
