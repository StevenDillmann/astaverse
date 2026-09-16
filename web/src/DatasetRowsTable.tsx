export function DatasetRowsTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: string[][];
}) {
  return (
    <div className="preview-table-wrap rows-table-wrap">
      <table className="hypothesis-table preview-table rows-table">
        <thead>
          <tr>
            <th className="row-index-cell" aria-label="Row number">#</th>
            {columns.map((column, index) => (
              <th key={`${column}-${index}`}>
                <code>{column}</code>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              <td className="row-index-cell numeric-cell">{rowIndex + 1}</td>
              {columns.map((_, columnIndex) => {
                const value = row[columnIndex];
                return (
                  <td key={columnIndex}>
                    {value == null || value === "" ? <span className="empty-cell">—</span> : value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
