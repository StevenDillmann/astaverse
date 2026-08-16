/** Everything on disk for an analysis: artifacts, the emitted task, what the
 *  agent actually wrote, and artifact sets superseded by re-running a stage.
 *
 *  The stage panels show the current result. This is for going back — reading
 *  the agent's own analysis.py, or comparing against a decision space you
 *  have since replaced.
 */

import { useEffect, useState } from "react";
import { getHistory, listFiles, readFile } from "./api";
import type { HistoryEntry, RunFile } from "./api";
import { Empty, ErrorNote, Eyebrow, Tag, cn } from "./ui";

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
  const [content, setContent] = useState("");
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
      setContent((await readFile(runId, path)).content);
    } catch (e) {
      setContent(`Could not read this file: ${(e as Error).message}`);
    }
  }

  const groups = ORDER.filter((c) => files.some((f) => f.category === c));

  return (
    <>
      {error && <ErrorNote>{error}</ErrorNote>}

      {history.length > 0 && (
        <div className="mb-5 rounded-md border border-border bg-muted/40 px-3 py-2.5">
          <Eyebrow className="mb-1.5">Superseded by re-running a stage</Eyebrow>
          {history.map((h) => (
            <p key={h.directory} className="text-xs text-muted-foreground">
              <Tag>{h.superseded_by}</Tag> archived {h.stages.join(", ")}
            </p>
          ))}
          <p className="mt-1.5 text-xs text-muted-foreground">
            Nothing is deleted when you re-run — the old artifacts are below, under history.
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="max-h-[620px] overflow-y-auto">
          {groups.map((category) => (
            <div key={category} className="mb-3">
              <Eyebrow className="mb-1.5">{category}</Eyebrow>
              {files
                .filter((f) => f.category === category)
                .map((f) => (
                  <button
                    key={f.path}
                    onClick={() => show(f.path)}
                    title={f.path}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 rounded px-2 py-1 text-left text-xs transition-colors",
                      open === f.path
                        ? "bg-accent text-foreground"
                        : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                    )}
                  >
                    <span className="truncate font-mono">{f.name}</span>
                    <span className="shrink-0 font-mono text-[11px] opacity-70">
                      {human(f.bytes)}
                    </span>
                  </button>
                ))}
            </div>
          ))}
          {files.length === 0 && !error && <Empty>No files yet.</Empty>}
        </div>

        <div className="min-w-0">
          {open ? (
            <>
              <Eyebrow className="mb-2 break-all">{open}</Eyebrow>
              <pre className="max-h-[620px] overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-[11px] leading-relaxed">
                {content || "Loading…"}
              </pre>
            </>
          ) : (
            <Empty>Select a file to read it.</Empty>
          )}
        </div>
      </div>
    </>
  );
}
