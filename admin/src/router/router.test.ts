import { act, renderHook } from "@testing-library/react";
import { describe, expect, it as test } from "vitest";
import { navigate, parseRoute, paths, useRoute } from "./router";

describe("router del pannello", () => {
  test("riconosce le schermate", () => {
    expect(parseRoute("/admin/")).toEqual({ name: "pages" });
    expect(parseRoute("/admin")).toEqual({ name: "pages" });
    expect(parseRoute("/admin/pagine/")).toEqual({ name: "pages" });
    expect(parseRoute("/admin/cestino")).toEqual({ name: "trash" });
    expect(parseRoute(paths.page(12))).toEqual({ name: "page", id: 12 });
    expect(parseRoute("/admin/pagine/abc")).toEqual({ name: "not-found" });
    expect(parseRoute("/admin/altro")).toEqual({ name: "not-found" });
  });

  test("navigate cambia la schermata e indietro torna alla precedente", async () => {
    window.history.replaceState(null, "", "/admin/pagine");
    const { result } = renderHook(() => useRoute());
    await act(async () => {
      await navigate(paths.trash);
    });
    expect(result.current).toEqual({ name: "trash" });
    expect(window.location.pathname).toBe("/admin/cestino");
    await act(async () => {
      window.history.back();
      await new Promise((resolve) => window.addEventListener("popstate", resolve, { once: true }));
    });
    expect(result.current).toEqual({ name: "pages" });
  });
});
