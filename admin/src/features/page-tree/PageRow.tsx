import type { PageNode } from "../../api/types";
import { Link } from "../../router/Link";
import { paths } from "../../router/router";
import { it } from "../../text/it";
import { needsPublishToTrash, statusLabels } from "./tree";

export type RowAction = "up" | "down" | "move" | "address" | "trash" | "trash-blocked";

interface Props {
  node: PageNode;
  siteUrl: string;
  canUp: boolean;
  canDown: boolean;
  canPublish: boolean;
  /** Un'azione è in corso o l'elenco è incompleto: niente modifiche all'albero. */
  locked: boolean;
  onAction: (action: RowAction, node: PageNode) => void;
}

interface ActionProps {
  label: string;
  enabled: boolean;
  danger?: boolean;
  onPress: () => void;
}

/** aria-disabled invece di disabled: il pulsante resta raggiungibile e non perde il focus. */
function Action({ label, enabled, danger = false, onPress }: ActionProps) {
  return (
    <button
      type="button"
      className={`button button--small${danger ? " button--danger" : ""}`}
      aria-disabled={!enabled}
      onClick={() => {
        if (enabled) onPress();
      }}
    >
      {label}
    </button>
  );
}

export function PageRow({ node, siteUrl, canUp, canDown, canPublish, locked, onAction }: Props) {
  const trashBlocked = needsPublishToTrash(node) && !canPublish;
  const online = node.status === "published";
  const act = (action: RowAction) => () => onAction(action, node);
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
            <Action label={it.tree.up} enabled={canUp && !locked} onPress={act("up")} />
            <Action label={it.tree.down} enabled={canDown && !locked} onPress={act("down")} />
            <Action label={it.tree.move} enabled={!locked} onPress={act("move")} />
            <Action label={it.tree.address} enabled={!locked} onPress={act("address")} />
          </>
        )}
        <a
          className="button button--small"
          href={`/_preview/${node.id}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {it.tree.preview}
        </a>
        {online && (
          <a
            className="button button--small"
            href={siteUrl + node.path}
            target="_blank"
            rel="noopener noreferrer"
          >
            {it.tree.viewOnline}
          </a>
        )}
        {!node.is_home && (
          <Action
            label={it.tree.trash}
            danger
            enabled={!locked}
            onPress={act(trashBlocked ? "trash-blocked" : "trash")}
          />
        )}
      </div>
    </div>
  );
}
