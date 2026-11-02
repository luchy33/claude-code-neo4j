# BPMN models: AS-IS and TO-BE order process (2026-10-22)

Project: Ekte Mat Online (INFO212). Models built from `02_process_as-is-order-handling_2026-08-15.md`, the four stakeholder interviews and `01_Requirements/EkteMat_backlog_v1.xlsx`.

## Files

| File | Content |
|---|---|
| `02_bpmn_as-is-order-process_2026-10-22.bpmn` | AS-IS diagram source (BPMN 2.0 XML; opens in Camunda Modeler or demo.bpmn.io) |
| `02_bpmn_as-is-order-process_2026-10-22.svg` / `.png` | AS-IS rendered image |
| `02_bpmn_to-be-order-process_2026-10-22.bpmn` | TO-BE diagram source |
| `02_bpmn_to-be-order-process_2026-10-22.svg` / `.png` | TO-BE rendered image |
| `02_bpmn_build_2026-10-22.py` | Generator and checks (layout, labels, quotes, story IDs) |
| `02_bpmn_render_2026-10-22.js` | Renders .bpmn to .svg/.png with bpmn-js 17.11.1 in headless Chromium |

## Notation choices

- **Pools and lanes:** *Customer* is its own pool because message flows may only connect different pools. *Ekte Mat AS* is one pool with the lanes Event coordinator, Kitchen, Driver and Owner; in TO-BE it also has the lane *Ekte Mat Online*.
- **External services:** Vipps and Fiken are collapsed (black-box) pools in TO-BE.
- **Elements used:** start events (message, timer, none), end events, tasks, exclusive gateways (split with labelled Yes/No flows and unlabelled merges), event-based gateways (waiting for a reply), intermediate message and timer catch events, sequence flows inside a pool and message flows between pools.
- **Problem marking (AS-IS):** red tasks labelled P1-P12. The monthly reconciliation and the driver's delivery are not marked because no stakeholder reports a problem there (see annotations).
- **Sources:** every element carries a `documentation` entry naming its source file and step/question. Open an element's properties in a BPMN tool to see it.

## Problems in the AS-IS process and the user stories that fix them

| ID | AS-IS step | Problem | Stakeholder evidence (verbatim) | Fixed by user story | TO-BE step | Evidence status |
|---|---|---|---|---|---|---|
| P1 | Customer: Send request by e-mail, phone or web form | Requests are lost (spam folder, failing web form, unanswered phone). | 01_interview_owner_2026-08-14.txt [Q1]: "Last December we found three julebord requests in the spam folder after the date had passed."<br>04_dataset_customer-emails_2026-10-20.csv [E023]: "I tried the contact form on your website three times and got an error."<br>04_dataset_customer-emails_2026-10-20.csv [E003]: "I called yesterday but nobody picked up." | **US-02**: to send a booking request online at any hour<br>**US-09**: to register and manage all orders, including orders received by phone or e-mail, in one system | Submit booking request online; stored in one order record | DIRECT |
| P2 | Coordinator: Read request | Replies take 1-2 days, up to a week in peak season; customers go elsewhere. | 01_interview_event-coordinator_2026-08-15.txt [Q2]: "On a normal week one or two days. In December and in May it can be a week. People get annoyed."<br>04_dataset_customer-emails_2026-10-20.csv [E006]: "I sent a request 6 days ago and have not heard back." | **US-02**: to send a booking request online at any hour<br>**US-04**: an automatic confirmation and a visible status for my order | Request stored instantly; automatic receipt | DIRECT |
| P3 | Coordinator: Check capacity in Google Calendar | Capacity is judged by gut feeling; risk of overbooking. | 02_process_as-is-order-handling_2026-08-15.md [step 3]: "If the day is "full" (gut feeling), she proposes another date."<br>01_interview_event-coordinator_2026-08-15.txt [Q4]: "A calendar that shows how many guests we already have per day, so I do not overbook." | **US-10**: a calendar showing booked guests per day against kitchen capacity<br>**US-03**: to see which dates are available | Capacity check and calendar; customers see available dates | DIRECT |
| P4 | Coordinator: Write quote in Word and e-mail as PDF | Manual quotes delay customers who need prices quickly. | 02_process_as-is-order-handling_2026-08-15.md [step 4]: "Coordinator writes a quote in Word from a template and e-mails it as PDF."<br>04_dataset_customer-emails_2026-10-20.csv [E015]: "We need a quote for a seminar lunch 80 people by Friday for internal approval." | **US-01**: to see current menus and prices online at any time | Customers browse menus and prices online | INFERRED (that online prices reduce the need for quotes) |
| P5 | Customer: Accept quote by e-mail | No confirmation is sent after acceptance; customers do not know if the order is confirmed. | 04_dataset_customer-emails_2026-10-20.csv [E011]: "Is our order for tomorrow confirmed? We never got a confirmation e-mail."<br>01_interview_corporate-customer_2026-08-19.txt [Q1]: "Sometimes it arrives Monday morning, which is too late for me." | **US-04**: an automatic confirmation and a visible status for my order | Confirm order and notify customer | DIRECT |
| P6 | Coordinator: Add row to Excel sheet | Double entry in Excel; the sheet and printouts get out of sync. | 01_interview_event-coordinator_2026-08-15.txt [Q1]: "when they say yes I add a row in "Bestillinger 2025.xlsx""<br>01_interview_event-coordinator_2026-08-15.txt [Q1]: "I have to remember to update both the sheet and the printout." | **US-09**: to register and manage all orders, including orders received by phone or e-mail, in one system | One order record in the system | DIRECT |
| P7 | Coordinator: Send Vipps deposit request | The deposit request is sometimes forgotten; no-shows at weddings. | 02_process_as-is-order-handling_2026-08-15.md [step 6]: "For weddings, the coordinator sends a Vipps payment request for a deposit (sometimes forgotten)."<br>01_interview_owner_2026-08-14.txt [Q2]: "We have had too many no-shows at weddings." | **US-22**: a deposit to be required for defined booking types | Request deposit via Vipps (scope UNRESOLVED, ISS-01) | UNRESOLVED |
| P8 | Coordinator: Print order and pin on kitchen board | Paper orders must be re-printed after every change. | 01_interview_event-coordinator_2026-08-15.txt [Q1]: "Then I print the order and put it on the kitchen board."<br>01_interview_head-chef_2026-08-15.txt [Q1]: "One screen in the kitchen." | **US-15**: a daily overview on a kitchen wall tablet showing orders, portions per dish and allergies in red<br>**US-09**: to register and manage all orders, including orders received by phone or e-mail, in one system | Show order on kitchen overview | DIRECT |
| P9 | Customer: Report changes by phone/e-mail; Coordinator: Update Excel and re-print | Changes arrive by phone and are sometimes not updated. | 01_interview_event-coordinator_2026-08-15.txt [Q1]: "Changes in guest numbers come by phone, and I have to remember to update both the sheet and the printout. Sometimes I forget."<br>04_dataset_customer-emails_2026-10-20.csv [E003]: "we need to change from 40 to 55 guests for our event next Thursday." | **US-11**: to change the number of guests and allergy information for my order online<br>**US-09**: to register and manage all orders, including orders received by phone or e-mail, in one system | Customer changes online; system updates order and kitchen overview | DIRECT |
| P10 | Coordinator: Phone customer 7 days before | Final numbers are only confirmed if the coordinator has time. | 02_process_as-is-order-handling_2026-08-15.md [step 9]: "7 days before the event the coordinator phones the customer to confirm final numbers (if she has time)."<br>01_interview_event-coordinator_2026-08-15.txt [Q4]: "automatic reminders to customers about final guest numbers seven days before the event." | **US-12**: customers to get an automatic reminder seven days before the event to confirm final guest numbers | Automatic 7-day reminder | DIRECT |
| P11 | Kitchen: Prepare food from the printed order | Allergies and diets can be missed (2024 nut incident, missing vegan dish). | 01_interview_event-coordinator_2026-08-15.txt [Q5]: "We had a nut incident in 2024 - nobody was hurt, but it was close."<br>04_dataset_customer-emails_2026-10-20.csv [E017]: "The vegan dish was missing on the delivery yesterday (order for 30)." | **US-15**: a daily overview on a kitchen wall tablet showing orders, portions per dish and allergies in red<br>**US-16**: the kitchen to confirm that it has seen each order's allergy information<br>**US-07**: to record allergies and diets per guest group in my order | Kitchen overview with allergies in red; kitchen confirms allergies | DIRECT |
| P12 | Coordinator: Create invoice in Fiken or Vipps request manually | Manual invoicing; PDF invoices rejected by corporate customers. | 02_process_as-is-order-handling_2026-08-15.md [step 11]: "After the event the coordinator creates an invoice in Fiken manually"<br>04_dataset_customer-emails_2026-10-20.csv [E004]: "Last invoice was a PDF by e-mail and was rejected."<br>01_interview_corporate-customer_2026-08-19.txt [Q3]: "One EHF invoice per month, with our cost-centre code on each line." | **US-24**: invoices for orders to be created in Fiken from the order data<br>**US-23**: one EHF invoice per month with my reference (cost centre or PO number) on each line<br>**US-21**: to pay with Vipps and get a receipt by e-mail | Create invoice in Fiken or capture Vipps payment | DIRECT |

## Coverage

- User stories shown in the TO-BE diagram (19): US-01, US-02, US-03, US-04, US-05, US-06, US-07, US-09, US-10, US-11, US-12, US-14, US-15, US-16, US-20, US-21, US-22, US-23, US-24.
- Not shown (12): US-08, US-13, US-17, US-18, US-19, US-25, US-26, US-27, US-28, US-29, US-30, US-31. These are menu/supplier administration, corporate account functions, privacy requests or cancellation, which run outside the single-order flow. US-13 (cancellation) is omitted because cancellation terms are missing (ISS-04).

## Simplifications and open points

- **Changes (AS-IS):** customer changes are drawn at one point in the flow (gateway *Changes received?*); in reality they can arrive at any time.
- **Decline branch:** the customer's *Decline quote* path is INFERRED; the source only describes acceptance.
- **Coordinator review (TO-BE):** a coordinator review step is an ASSUMPTION; whether requests are confirmed automatically is not decided (US-02, US-10).
- **Deposit gateway (TO-BE):** the scope (all bookings or weddings only) is unresolved (ISS-01).
- **Deposit payment:** the customer pays in the Vipps app; this is simplified to a message from Ekte Mat Online.
- **Owner lane (TO-BE):** the lane is intentionally empty of tasks.

## Validation performed

- `bpmnlint` 10.3.1 with the `bpmnlint:recommended` rule set: 0 problems for both diagrams (the linter was also shown to flag a deliberately broken copy).
- Import into `bpmn-js` 17.11.1: 0 import warnings for both diagrams.
- Generator checks: no sequence or message flow crosses another element, annotation or explicit label; every element has a source entry; every story ID exists in the backlog; every quote in the table occurs verbatim in its source.
- Visual check of the rendered PNGs.
- Not checked: opening the files in Camunda Modeler or Signavio.
