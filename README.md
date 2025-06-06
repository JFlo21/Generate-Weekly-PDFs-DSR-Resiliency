# 📄 Smartsheet Weekly PDF Generator Automation

This project automates the generation of **weekly PDF summaries** from Smartsheet data. It pulls rows grouped by `Foreman`, `Work Request #`, and `Weekly Referenced Logged Date`, fills out a PDF template using those values, calculates a total, and uploads the PDF back to the corresponding row on Smartsheet.

---

## 🚀 Features

- ✅ Group rows by: `Foreman`, `Work Request #`, and week ending date
- 🗂️ Auto-generates a single PDF per group with up to 38 line items
- 📆 Week ending is calculated based on Sunday of each logged week
- 🧾 Fills a provided fillable `template.pdf` with field-aligned data
- 💲 Calculates and fills `PricingTOTAL` with the sum of all line item pricing
- 🔁 Skips uploading if identical PDF already exists
- 🔄 Updates existing attachments using Smartsheet's version history
- 🖋️ Smart formatting for dates (`MM/DD/YY`), whole numbers, and currency (`$X,XXX.XX`)

---

## 📂 Files

```plaintext
📄 generate_weekly_pdfs.py   # Main automation logic
📄 template.pdf              # Fillable form used for PDF generation
📄 requirements.txt          # Required Python packages
📁 .github/workflows/        # GitHub Actions automation (optional)
📁 docs/                     # React UI for browsing generated PDFs
```

The `docs` folder exposes a polished web app built with **React** and **Bootstrap 5**.
It loads `metadata.json` and displays the PDFs in a responsive interface with:

- a navigation bar with links and branding
- an optional sidebar for filtering files
- search and pagination controls
- download buttons for each PDF

This makes it easy for billers and accountants to browse and retrieve weekly
reports from any device.
