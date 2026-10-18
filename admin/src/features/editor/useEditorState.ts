// Stato dell'editor: storia (annulla/ripristina) e blocco selezionato.
import { useCallback, useReducer } from "react";
import type { PageDocument } from "./model/document";
import { commit, redo, startHistory, undo, type History } from "./model/history";

interface State {
  history: History;
  selected: string | null;
}

type Action =
  | { type: "edit"; doc: PageDocument; key: string | null; select?: string | null }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "replace"; doc: PageDocument }
  | { type: "select"; uid: string | null };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "edit":
      return {
        history: commit(state.history, action.doc, action.key, Date.now()),
        selected: action.select === undefined ? state.selected : action.select,
      };
    case "undo":
      return { ...state, history: undo(state.history) };
    case "redo":
      return { ...state, history: redo(state.history) };
    case "replace":
      return { history: startHistory(action.doc), selected: null };
    case "select":
      return { ...state, selected: action.uid };
  }
}

export function useEditorState(initial: PageDocument) {
  const [state, dispatch] = useReducer(reducer, initial, (doc) => ({ history: startHistory(doc), selected: null }));
  const edit = useCallback(
    (doc: PageDocument, key: string | null = null, select?: string | null) => dispatch({ type: "edit", doc, key, ...(select !== undefined ? { select } : {}) }),
    [],
  );
  return {
    doc: state.history.present,
    selected: state.selected,
    canUndo: state.history.past.length > 0,
    canRedo: state.history.future.length > 0,
    edit,
    undo: useCallback(() => dispatch({ type: "undo" }), []),
    redo: useCallback(() => dispatch({ type: "redo" }), []),
    replace: useCallback((doc: PageDocument) => dispatch({ type: "replace", doc }), []),
    select: useCallback((uid: string | null) => dispatch({ type: "select", uid }), []),
  };
}
