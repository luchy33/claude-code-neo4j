# EkteMat_repo – organised project material for "Ekte Mat Online"

Created 2026-10-22 from the 17 client files in `../EkteMat_project_inbox/`.
The inbox was **not** moved, modified or deleted; every file here is a byte-identical copy (checked with SHA-256).

> **Confidentiality:** the material is marked as synthetic data for INFO212 Lab 7, but treat it as client material anyway.
> File names use roles (owner, head chef, corporate customer) instead of personal or company names.
> This README contains no customer names, e-mail addresses or e-mail contents. Keep the repository private.

## Naming convention

`<phase>_<type>_<short-description>_<YYYY-MM-DD>.<ext>`

- **phase** = the number of the destination folder (00, 01, 02, 03, 04, 99)
- **type** = interview, minutes, plan, todo, note, vision, process, benchmark, landscape, dataset, reference
- **date** = the most reliable date available, by source:
  - **Content**: a date written inside the file (interviews, meeting notes, GDPR note, as-is process).
  - **xlsx metadata**: the workbook's embedded "created" property, 2026-09-27 (the export date).
  - **File modified time**: 2026-10-20, the date the files landed in the inbox. All 17 inbox files share it, so it records **receipt, not authorship**. It is used only where no better date exists.
  - **Rejected**: the .docx "created" property (2013-12-23) is a default value from the python-docx tool, not a real date.

## File table

| New filename | Original filename | Destination folder | Description | Reason for placement | Date source |
|---|---|---|---|---|---|
| 00_minutes_kickoff-meeting_2026-08-12.txt | notes meeting 12 aug FINAL.txt | 00_Project_management | Kick-off meeting: goal, integrations, customer groups, sprints, actions | Records project decisions, roles and actions | Content |
| 00_plan_budget-and-constraints_2026-10-20.txt | budget and constraints.txt | 00_Project_management | Budget 450 000 NOK, running costs < 3 000 NOK/month, go-live 2027-03-01, team | Budget, deadline and team set-up are project-management constraints | File modified time |
| 00_todo_sprint0-setup_2026-10-20.txt | untitled.txt | 00_Project_management | Team to-do: set up Git repo, board, Definition of Done (plus a printer-ink reminder) | Sprint 0 planning task | File modified time |
| 01_interview_owner_2026-08-14.txt | interview_Ingrid_owner.txt | 01_Requirements/sources | Interview 1 – owner: problems, priorities, deposit, payment, budget | Primary stakeholder requirements source | Content |
| 01_interview_event-coordinator_2026-08-15.txt | interview_Sunniva_event_coordinator.txt | 01_Requirements/sources | Interview 2 – event coordinator: current workflow, capacity, invoicing, allergies | Primary stakeholder requirements source | Content |
| 01_interview_head-chef_2026-08-15.txt | interview_Mateo_head_chef.txt | 01_Requirements/sources | Interview 3 – head chef: kitchen screen, menus, prep list, offline need | Primary stakeholder requirements source | Content |
| 01_interview_corporate-customer_2026-08-19.txt | interview_Fjordtek_customer.txt | 01_Requirements/sources | Interview 4 – corporate customer: company login, approval limit, EHF invoicing | Primary stakeholder requirements source | Content |
| 01_note_gdpr-consultant_2026-08-20.txt | GDPR note from consultant.txt | 01_Requirements/sources | GDPR advice: health data, retention, access/deletion, data processing agreement | Legal constraints become non-functional requirements | Content |
| 01_vision_draft-v0.3_2026-10-20.docx | vision_draft_v0.3.docx | 01_Requirements/sources | Draft vision statement v0.3 | The vision sets the scope that requirements are traced to | File modified time |
| 02_process_as-is-order-handling_2026-08-15.md | asis_order_process.md | 02_Analysis_and_models | 12-step description of today's order process | Direct input for an as-is process model (e.g. BPMN) | Content |
| 02_benchmark_competitor-links_2026-10-20.txt | competitor links.txt | 02_Analysis_and_models | Links to four competitor caterers' public websites | Material for competitor and market analysis | File modified time |
| 03_landscape_current-it_2026-10-20.txt | current_IT_landscape.txt | 03_Architecture | Current systems (Wix, Google Workspace, Fiken, Vipps, Excel) and constraints | Shows the systems and integrations the architecture must fit | File modified time |
| 04_dataset_customer-emails_2026-10-20.csv | customer_emails_export.csv | 04_Data | Export of 30 customer e-mails (2026-05-04 to 2026-08-31) | Raw dataset containing personal data | File modified time |
| 04_dataset_orders-2024-2025_2026-09-27.xlsx | orders_2024_2025_export.xlsx | 04_Data | Order export: 820 order rows plus a README sheet | Raw historical dataset | xlsx metadata |
| 04_reference_lunch-menu-autumn_2026-10-20.txt | lunch menu autumn.txt | 04_Data | Draft autumn menu with prices in NOK and the allergens to label | Reference data (dishes, prices, allergens) for the data model | File modified time |
| 99_note_logo-ideas_2026-10-20.txt | logo ideas.txt | 99_Not_relevant | Logo brainstorm | The file itself says it is not relevant to system development | File modified time |

`05_Lab_submission/` contains only a `.gitkeep` placeholder. None of the client files belong there.

## Source files inspected (17)

asis_order_process.md · budget and constraints.txt · competitor links.txt · current_IT_landscape.txt · customer_emails_export.csv · GDPR note from consultant.txt · interview_Fjordtek_customer.txt · interview_Ingrid_owner.txt · interview_Mateo_head_chef.txt · interview_Sunniva_event_coordinator.txt · Kopi av interview Sunniva (2).txt · logo ideas.txt · lunch menu autumn.txt · notes meeting 12 aug FINAL.txt · orders_2024_2025_export.xlsx · untitled.txt · vision_draft_v0.3.docx

## Duplicates skipped (1)

| Skipped file | Identical to (copied) | SHA-256 |
|---|---|---|
| Kopi av interview Sunniva (2).txt | interview_Sunniva_event_coordinator.txt | e4f92056eeff7658fe2528e90e785e9fb16af67663b41d96f77363cbec73d218 |

All other 15 files have distinct hashes. No files were skipped for being merely similar.

## Files copied (16)

The 16 files in the table above. Each copy's SHA-256 matches its original.

## Files that could not be processed

None. All 17 files were read, including the .csv, .xlsx and .docx files.

## Open points

- **Real authoring dates:** 9 file names carry the receipt date 2026-10-20. If the client can supply real authoring dates, rename those files.
- **Mixed content:** `00_todo_sprint0-setup` mixes a private reminder (printer ink) with a sprint 0 task. It is kept unchanged as a copy.
