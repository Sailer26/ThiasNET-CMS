import { useId } from "react";
import type { PageNode } from "../../api/types";
import { Link } from "../../router/Link";
import { paths } from "../../router/router";
import { it } from "../../text/it";
import { needsPublishToTrash, statusLabels } from "./tree";

export type RowAction = "up" | "down" | "move" | "address" | "trash";

interface Props {
  node: PageNode;
  siteUrl: string;
  canUp: boolean;
  canDown: boolean;
  canPublish: boolean;
  onAction: (action: RowAction, node: PageNode) => void;
}

export function PageRow({ node, siteUrl, canUp, canDown, canPublish, onAction }: Props) {
  const reasonId = useId();
  const trashBlocked = needsPublishToTrash(node) && !canPublish;
  const online = node.status === "published";
  return (
    <div className="row">
      <div className="row__main">
        <Link className="row__title" to={paths.page(node.id)}>
          {node.title}
        </Link>
        <code className="row__path">{node.path}</code>
        <span className="row__badges">
          {statusLabels(node).map((label) => (
            <span key={label} className={`badge badge--${node.status}`}>
              {label}
            </span>
          ))}
        </span>
      </div>
      <div className="row__actions" role="group" aria-label={it.tree.actions(node.title)}>
        {!node.is_home && (
          <>
            <button type="button" className="button button--small" disabled={!canUp} onClick={() => onAction("up", node)}>
              {it.tree.up}
            </button>
            <button type="button" className="button button--small" disabled={!canDown} onClick={() => onAction("down", node)}>
              {it.tree.down}
            </button>
            <button type="button" className="button button--small" onClick={() => onAction("move", node)}>
              {it.tree.move}
            </button>
            <button type="button" className="button button--small" onClick={() => onAction("address", node)}>
              {it.tree.address}
            </button>
          </>
        )}
        <a className="button button--small" href={`/_preview/${node.id}`} target="_blank" rel="noopener noreferrer">
          {it.tree.preview}
        </a>
        {online && (
          <a className="button button--small" href={siteUrl + node.path} target="_blank" rel="noopener noreferrer">
            {it.tree.viewOnline}
          </a>
        )}
        {!node.is_home && (
          <>
            <button
              type="button"
              className="button button--small button--danger"
              disabled={trashBlocked}
              aria-describedby={trashBlocked ? reasonId : undefined}
              onClick={() => onAction("trash", node)}
            >
              {it.tree.trash}
            </button>
            {trashBlocked && (
              <span id={reasonId} className="visually-hidden">
                {it.tree.trashNeedsPublish}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}
