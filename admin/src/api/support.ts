// "Chiedi a Thias" (D-134): il destinatario lo decide il server, mai il pannello.
import { request } from "./client";

export async function askThias(body: { message: string; page_id: number | null; screen: string }): Promise<{ sent: boolean }> {
  return (await request<{ sent: boolean }>("POST", "/support-requests", body)).data;
}
