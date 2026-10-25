// Forme dei dati restituiti da /api/admin (vedi app/services/users.py e page_views.py).

export type Role = "owner" | "admin" | "editor";
export type PageStatus = "draft" | "published" | "scheduled";

export interface User {
  id: number;
  email: string;
  role: Role;
  active: boolean;
  can_publish: boolean;
  totp_enabled: boolean;
  last_login_at: string | null;
  tour_completed_at: string | null;
  created_at: string;
}

export interface Me extends User {
  permissions: string[];
}

export interface Site {
  name: string;
  url: string;
  locales: string[];
  default_locale: string;
  default_layout: string;
  home_layout: string;
  /** Le raccolte del tema (7b): una voce di menu ciascuna, es. le notizie. */
  collections: { key: string; label: string }[];
}

export interface Page {
  id: number;
  parent_id: number | null;
  locale: string;
  slug: string;
  path: string;
  is_home: boolean;
  title: string;
  layout: string;
  status: PageStatus;
  publish_at: string | null;
  published_at: string | null;
  sort: number;
  version: number;
  has_draft: boolean;
  /** Programmazione in attesa (solo nel dettaglio della pagina, D-122). */
  schedule?: {
    publish_at: string;
    revision_id: number;
    author_name: string;
    draft_newer: boolean;
  } | null;
  updated_at: string | null;
  updated_by: number | null;
  deleted_at: string | null;
}

export interface PageNode extends Page {
  children: PageNode[];
}

export interface ConflictDetails {
  current_version: number;
  updated_by: number | null;
  updated_by_name: string;
  updated_at: string | null;
}
