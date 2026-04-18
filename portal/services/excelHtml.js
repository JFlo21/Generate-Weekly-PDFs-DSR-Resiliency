/**
 * Render a parsed workbook (output of excel.parseExcelBuffer) as a
 * standalone, self-contained HTML document suitable for embedding in an
 * <iframe srcdoc> on the frontend.
 *
 * Styling intent: preserve the visual fidelity of the source sheet — bold,
 * color, fill, alignment, frozen header row — without shipping Excel-as-art.
 * The surrounding chrome (tabs, toolbar) stays with the React wrapper.
 */

function escapeHtml(v) {
  if (v === null || v === undefined) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function styleString(s) {
  if (!s) return '';
  const parts = [];
  if (s.bold) parts.push('font-weight:600');
  if (s.fontSize) parts.push(`font-size:${Number(s.fontSize) || 12}px`);
  if (s.color) parts.push(`color:${s.color}`);
  if (s.bgColor) parts.push(`background-color:${s.bgColor}`);
  if (s.align) parts.push(`text-align:${s.align}`);
  return parts.join(';');
}

function renderSheet(sheet) {
  if (!sheet || !sheet.rows || sheet.rows.length === 0) {
    return '<div class="empty">This sheet is empty.</div>';
  }

  // Figure out column span so empty-cell rows still render as a grid.
  const maxCol = Math.max(
    1,
    ...sheet.rows.map((r) =>
      r.cells && r.cells.length ? Math.max(...r.cells.map((c) => c.col || 1)) : 1
    )
  );

  const colLetters = [];
  for (let i = 1; i <= maxCol; i++) {
    let n = i;
    let label = '';
    while (n > 0) {
      const mod = (n - 1) % 26;
      label = String.fromCharCode(65 + mod) + label;
      n = Math.floor((n - 1) / 26);
    }
    colLetters.push(label);
  }

  let headerCells = '<th class="gutter"></th>';
  for (const l of colLetters) headerCells += `<th class="colhead">${l}</th>`;

  let bodyRows = '';
  for (const row of sheet.rows) {
    const byCol = new Map();
    for (const c of row.cells || []) byCol.set(c.col, c);
    let tr = `<tr><td class="gutter">${row.rowNumber}</td>`;
    for (let col = 1; col <= maxCol; col++) {
      const cell = byCol.get(col);
      const style = cell ? styleString(cell.style) : '';
      const val = cell ? escapeHtml(cell.value) : '';
      tr += `<td${style ? ` style="${style}"` : ''}>${val}</td>`;
    }
    tr += '</tr>';
    bodyRows += tr;
  }

  return `<table>
    <thead><tr>${headerCells}</tr></thead>
    <tbody>${bodyRows}</tbody>
  </table>`;
}

function renderHtml(parsed, { sheet } = {}) {
  if (!parsed || !parsed.sheets || parsed.sheets.length === 0) {
    return '<!doctype html><html><body><p>No sheets found.</p></body></html>';
  }
  const target = sheet
    ? parsed.sheets.find((s) => s.name === sheet) || parsed.sheets[0]
    : parsed.sheets[0];

  const body = renderSheet(target);

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>${escapeHtml(target.name)}</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #f8fafc; color: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    font-size: 13px; line-height: 1.4;
  }
  .wrap { padding: 16px; overflow: auto; }
  table { border-collapse: separate; border-spacing: 0; background: #fff;
    border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
  }
  thead th { position: sticky; top: 0; z-index: 2; background: #f1f5f9;
    border-bottom: 1px solid #e2e8f0; padding: 6px 10px; font-weight: 600;
    color: #475569; text-align: center; font-size: 11px; letter-spacing: 0.02em;
  }
  th.gutter, td.gutter { position: sticky; left: 0; z-index: 1; background: #f1f5f9;
    color: #94a3b8; text-align: right; font-variant-numeric: tabular-nums;
    min-width: 44px; padding: 4px 8px; border-right: 1px solid #e2e8f0;
    font-size: 11px;
  }
  thead th.gutter { z-index: 3; }
  tbody td { padding: 6px 10px; border-bottom: 1px solid #f1f5f9;
    border-right: 1px solid #f1f5f9; white-space: nowrap; vertical-align: middle;
  }
  tbody tr:hover td:not(.gutter) { background: #f8fafc; }
  .empty { padding: 32px; text-align: center; color: #64748b; background: #fff;
    border: 1px dashed #e2e8f0; border-radius: 8px;
  }
</style>
</head>
<body><div class="wrap">${body}</div></body>
</html>`;
}

module.exports = { renderHtml };
