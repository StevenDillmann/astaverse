import type { DatasetColumn } from "./types";

export function DatasetSchemaTable({
  columns,
  descriptions,
  editable = false,
  onDescriptionChange,
}: {
  columns: DatasetColumn[];
  descriptions?: Record<string, string>;
  editable?: boolean;
  onDescriptionChange?: (columnName: string, value: string) => void;
}) {
  return (
    <div className="preview-table-wrap">
      <table className="hypothesis-table preview-table schema-table">
        <thead>
          <tr>
            <th>Column</th>
            <th>Type</th>
            <th>Range / samples</th>
            <th>Unique</th>
            <th>Missing</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((column) => (
            <tr key={column.name}>
              <td>
                <code>{column.name}</code>
              </td>
              <td>{column.dtype}</td>
              <td>{formatRange(column)}</td>
              <td className="numeric-cell">{column.num_unique_values ?? "—"}</td>
              <td className="numeric-cell">{column.n_missing ?? 0}</td>
              <td className="description-cell">
                {editable ? (
                  <textarea
                    rows={2}
                    value={descriptions?.[column.name] ?? column.description ?? ""}
                    placeholder="What does this column measure?"
                    onChange={(event) => onDescriptionChange?.(column.name, event.target.value)}
                  />
                ) : (
                  column.description || descriptions?.[column.name] || "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatRange(column: DatasetColumn) {
  if (column.min != null && column.max != null) {
    return `${column.min} – ${column.max}`;
  }
  const samples = (column.samples || [])
    .filter((value) => value != null)
    .slice(0, 3)
    .map(String)
    .join(", ");
  return samples ? `e.g. ${samples}` : "—";
}
