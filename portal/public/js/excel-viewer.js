(function () {
  'use strict';

  window.ExcelViewer = { render };

  function render(sheets, tabsEl, bodyEl) {
    tabsEl.innerHTML = '';
    bodyEl.innerHTML = '';

    sheets.forEach((sheet, idx) => {
      const tab = document.createElement('button');
      tab.className = 'viewer-tab' + (idx === 0 ? ' active' : '');
      tab.textContent = sheet.name || `Sheet ${idx + 1}`;
      tab.addEventListener('click', () => {
        tabsEl.querySelectorAll('.viewer-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        renderSheet(sheet, bodyEl);
      });
      tabsEl.appendChild(tab);
    });

    renderSheet(sheets[0], bodyEl);
  }

  function renderSheet(sheet, bodyEl) {
    if (!sheet.rows || sheet.rows.length === 0) {
      bodyEl.innerHTML = '<div class="empty-state"><p>This sheet is empty.</p></div>';
      return;
    }

    const maxCol = Math.max(...sheet.rows.map(r =>
      r.cells.length > 0 ? Math.max(...r.cells.map(c => c.col)) : 0
    ));

    const table = document.createElement('table');
    table.className = 'excel-table';

    for (const row of sheet.rows) {
      const tr = document.createElement('tr');
      const cellMap = {};
      for (const cell of row.cells) {
        cellMap[cell.col] = cell;
      }

      for (let col = 1; col <= maxCol; col++) {
        const cell = cellMap[col];
        const td = document.createElement('td');
        td.textContent = cell ? formatValue(cell.value) : '';

        if (cell && cell.style) {
          applyStyle(td, cell.style);
        }

        tr.appendChild(td);
      }
      table.appendChild(tr);
    }

    bodyEl.innerHTML = '';
    bodyEl.appendChild(table);
  }

  function formatValue(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'number') {
      if (Number.isInteger(val)) return val.toLocaleString('en-US');
      return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return String(val);
  }

  function applyStyle(el, style) {
    if (style.bold) el.style.fontWeight = '700';
    if (style.fontSize) el.style.fontSize = style.fontSize + 'pt';
    if (style.color) el.style.color = style.color;
    if (style.bgColor && style.bgColor !== '#000000') el.style.backgroundColor = style.bgColor;
    if (style.align) el.style.textAlign = style.align;
  }
})();
