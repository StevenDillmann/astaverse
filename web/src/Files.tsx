/** Everything on disk for a run: artifacts, the emitted task, what the agent
 * actually wrote, and artifact sets superseded by re-running an earlier stage.
 *
 * The stage panels render the current result. This is for going back — reading
 * the agent's own analysis.py, or comparing against a decision space you have
 * since replaced.
 */

import { useEffect, useState } from "react";
import { getHistory, listFiles, readFile } from "./api";
import type { HistoryEntry, RunFile } from "./api";

const ORDER = ["artifact", "agent output", "history", "task", "universes", "job"];

function human(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function Files({ runId }: { runId: string }) {
  const [files, setFiles] = useState<RunFile[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setOpen(null);
    setContent("");
    listFiles(runId).then(setFiles).catch((e) => setError(e.message));
    getHistory(runId).then(setHistory).catch(() => setHistory([]));
  }, [runId]);

  async function show(path: string) {
    setOpen(path);
    setContent("");
    try {
      const { content } = await readFile(runId, path);
      setContent(content);
    } catch (e) {
      setContent(`Could not read this file: ${(e as Error).message}`);
    }
  }

  const groups = ORDER.filter((c) => files.some((f) => f.category === c));

  return (
    <>
      {error && <div className="error">{error}</div>}

      {history.length > 0 && (
        <>
          <p className="eyebrow">Superseded by re-running a stage</p>
          {history.map((h) => (
            <p key={h.directory} className="empty" style={{ marginBottom: 6 }}>
              <span className="tag">{h.superseded_by}</span> archived {h.stages.join(", ")} ·{" "}
              <code>history/{h.directory}</code>
            </p>
          ))}
          <p className="empty" style={{ margin: "8px 0 24px" }}>
            Nothing is deleted when you re-run — the old artifacts are below under history.
          </p>
        </>
      )}

      <div className="files-grid">
        <div className="file-list">
          {groups.map((category) => (
            <div key={category}>
              <p className="eyebrow" style={{ marginTop: 14 }}>
                {category}
              </p>
              {files
                .filter((f) => f.category === category)
                .map((f) => (
                  <button
                    key={f.path}
                    className="file-item"
                    aria-current={open === f.path}
                    onClick={() => show(f.path)}
                    title={f.path}
                  >
                    <span className="file-name">{f.name}</span>
                    <span className="file-size">{human(f.bytes)}</span>
                  </button>
                ))}
            </div>
          ))}
          {files.length === 0 && !error && <p className="empty">No files yet.</p>}
        </div>

        <div className="file-view">
          {open ? (
            <>
              <p className="eyebrow" style={{ wordBreak: "break-all" }}>
                {open}
              </p>
              <pre>{content || "Loading…"}</pre>
            </>
          ) : (
            <p className="empty">Select a file to read it.</p>
          )}
        </div>
      </div>
    </>
  );
}
