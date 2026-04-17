const ExcelJS = require('exceljs');

const DEFAULT_PARSE_LIMITS = {
  maxSheets: 25,
  maxRowsPerSheet: 10000,
  maxColsPerRow: 250,
  maxTotalCells: 750000,
};

async function parseExcelBuffer(buffer, limits = DEFAULT_PARSE_LIMITS) {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(buffer);

  const sheets = [];
  let totalCells = 0;

  if (workbook.worksheets.length > limits.maxSheets) {
    throw new Error(`Excel parse limit exceeded: too many sheets (${workbook.worksheets.length})`);
  }

  workbook.eachSheet((worksheet) => {
    const rows = [];
    const merges = [];
    let processedRows = 0;

    if (worksheet.merges) {
      for (const merge of Object.values(worksheet.merges)) {
        merges.push(merge.model);
      }
    }

    worksheet.eachRow({ includeEmpty: true }, (row, rowNumber) => {
      processedRows += 1;
      if (processedRows > limits.maxRowsPerSheet) {
        throw new Error(`Excel parse limit exceeded: too many rows in worksheet "${worksheet.name}"`);
      }

      const cells = [];
      let processedCols = 0;
      row.eachCell({ includeEmpty: true }, (cell, colNumber) => {
        processedCols += 1;
        if (processedCols > limits.maxColsPerRow) {
          throw new Error(`Excel parse limit exceeded: too many columns in worksheet "${worksheet.name}"`);
        }

        totalCells += 1;
        if (totalCells > limits.maxTotalCells) {
          throw new Error('Excel parse limit exceeded: too many cells');
        }

        let value = cell.value;

        if (value && typeof value === 'object') {
          if (value.result !== undefined) value = value.result;
          else if (value.text) value = value.text;
          else if (value.richText) value = value.richText.map(r => r.text).join('');
          else if (value instanceof Date) value = value.toLocaleDateString('en-US');
          else value = String(value);
        }

        const cellData = { value: value ?? '', col: colNumber };

        if (cell.style) {
          const style = {};
          if (cell.font) {
            if (cell.font.bold) style.bold = true;
            if (cell.font.size) style.fontSize = cell.font.size;
            if (cell.font.color && cell.font.color.argb) {
              style.color = '#' + cell.font.color.argb.slice(2);
            }
          }
          if (cell.fill && cell.fill.fgColor && cell.fill.fgColor.argb) {
            style.bgColor = '#' + cell.fill.fgColor.argb.slice(2);
          }
          if (cell.alignment) {
            if (cell.alignment.horizontal) style.align = cell.alignment.horizontal;
          }
          if (Object.keys(style).length > 0) cellData.style = style;
        }

        cells.push(cellData);
      });
      rows.push({ rowNumber, cells });
    });

    sheets.push({
      name: worksheet.name,
      rowCount: worksheet.rowCount,
      columnCount: worksheet.columnCount,
      rows,
      merges,
    });
  });

  return { sheetCount: sheets.length, sheets };
}

module.exports = { parseExcelBuffer };
