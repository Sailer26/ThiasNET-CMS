import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, expect } from "vitest";
import { forgetCatalog } from "../api/catalog";
import { setCsrfToken } from "../api/client";
import { unexpectedCalls } from "./fakeApi";

// jsdom non implementa <dialog>: basta aprirlo e chiuderlo con i suoi attributi.
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

afterEach(() => {
  cleanup();
  setCsrfToken(null);
  forgetCatalog();
  const unexpected = unexpectedCalls.splice(0);
  expect(unexpected, "chiamate all'API senza risposta preparata").toEqual([]);
});
