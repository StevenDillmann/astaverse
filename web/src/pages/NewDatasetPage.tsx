import { ArrowLeft, Check, FileUp, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ErrorState, Loading, PageHeader } from "../components";
import { DatasetSchemaTable } from "../DatasetSchemaTable";
import { navigate } from "../hooks";
import type { DatasetPreview } from "../types";

function slugifyName(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function NewDatasetPage() {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [columnDescriptions, setColumnDescriptions] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const resolvedName = useMemo(() => slugifyName(name), [name]);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      setPreviewError(null);
      return;
    }

    let current = true;
    const timer = window.setTimeout(() => {
      setPreviewing(true);
      api
        .previewDataset({
          file,
          name: resolvedName || undefined,
          description: description || undefined,
        })
        .then((next) => {
          if (!current) return;
          setPreview(next);
          setPreviewError(null);
          setColumnDescriptions((previous) => {
            const merged: Record<string, string> = {};
            for (const column of next.columns) {
              merged[column.name] = previous[column.name] ?? column.description ?? "";
            }
            return merged;
          });
        })
        .catch((reason: unknown) => {
          if (!current) return;
          setPreview(null);
          setPreviewError(reason instanceof Error ? reason.message : String(reason));
        })
        .finally(() => {
          if (current) setPreviewing(false);
        });
    }, 350);

    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [file, resolvedName, description]);

  const onFileChange = (next: File | null) => {
    setFile(next);
    setSubmitError(null);
    setSaved(false);
    setColumnDescriptions({});
    if (next && !name.trim()) {
      setName(next.name.replace(/\.csv$/i, ""));
    }
  };

  const importDataset = async () => {
    if (!file || !resolvedName) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createDataset({
        file,
        name: resolvedName,
        description: description || undefined,
        column_descriptions: columnDescriptions,
      });
      setSaved(true);
      window.setTimeout(() => navigate(`/datasets/${encodeURIComponent(created.name)}`), 500);
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSubmitting(false);
    }
  };

  const canImport =
    Boolean(file && resolvedName && preview && preview.available && !previewError && !previewing);

  return (
    <>
      <button className="back-link" onClick={() => navigate("/datasets")}>
        <ArrowLeft size={15} /> Datasets
      </button>
      <PageHeader
        title="New dataset"
        description="Upload a CSV and review its dataset and column metadata before importing."
      />

      <div className="builder-form dataset-import-form">
        <section className="form-section">
          <div className="section-heading">
            <div>
              <span className="section-label">Step 1</span>
              <h2>Upload CSV</h2>
            </div>
          </div>
          <label className="upload-dropzone">
            <input
              type="file"
              accept=".csv,text/csv"
              hidden
              onChange={(event) => onFileChange(event.target.files?.[0] || null)}
            />
            <FileUp size={18} />
            <strong>{file ? file.name : "Choose a CSV file"}</strong>
            <small>Header row required. Maximum size 50MB.</small>
          </label>
        </section>

        {file && (
          <>
            <section className="form-section">
              <div className="section-heading">
                <div>
                  <span className="section-label">Step 2</span>
                  <h2>Metadata</h2>
                </div>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>Dataset name</span>
                  <input
                    value={name}
                    placeholder="hurricane"
                    onChange={(event) => setName(event.target.value)}
                  />
                  <small>
                    Stored as <code>{resolvedName || "…"}</code>
                    {preview && !preview.available ? " · name already in use" : ""}
                  </small>
                </label>
                <label className="field span-2">
                  <span>Description</span>
                  <textarea
                    rows={3}
                    value={description}
                    placeholder="What does this dataset measure?"
                    onChange={(event) => setDescription(event.target.value)}
                  />
                </label>
              </div>
            </section>

            <section className="form-section">
              <div className="section-heading">
                <div>
                  <span className="section-label">Step 3</span>
                  <h2>Columns</h2>
                </div>
              </div>
              {previewing ? (
                <Loading label="Profiling dataset" />
              ) : previewError ? (
                <ErrorState message={previewError} />
              ) : preview ? (
                <>
                  <div className="metric-strip">
                    <Metric label="Rows" value={preview.n_rows?.toLocaleString() || "—"} />
                    <Metric label="Columns" value={preview.n_columns} />
                    <Metric label="Name" value={preview.name} />
                  </div>
                  <DatasetSchemaTable
                    columns={preview.columns}
                    descriptions={columnDescriptions}
                    editable
                    onDescriptionChange={(columnName, value) =>
                      setColumnDescriptions((previous) => ({ ...previous, [columnName]: value }))
                    }
                  />
                </>
              ) : null}
            </section>

            <section className="form-section">
              <div className="import-actions">
                <button
                  className="button primary"
                  disabled={!canImport || submitting}
                  onClick={() => void importDataset()}
                >
                  {saved ? <Check size={16} /> : <Upload size={16} />}
                  {saved ? "Imported" : submitting ? "Importing…" : "Import dataset"}
                </button>
                {submitError ? <p className="form-error">{submitError}</p> : null}
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
    </div>
  );
}
