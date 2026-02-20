const ExcelJS = require('exceljs');

async function parseExcelBuffer(buffer) {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(buffer);

  const sheets = [];

  workbook.eachSheet((worksheet) => {
    const rows = [];
    const merges = [];

    if (worksheet.merges) {
      for (const merge of Object.values(worksheet.merges)) {
        merges.push(merge.model);
      }
    }

    worksheet.eachRow({ includeEmpty: true }, (row, rowNumber) => {
      const cells = [];
      row.eachCell({ includeEmpty: true }, (cell, colNumber) => {
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
