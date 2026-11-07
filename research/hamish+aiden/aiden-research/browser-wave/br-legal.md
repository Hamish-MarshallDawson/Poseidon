# br-legal: in-house legal automation

*Research agent br-legal, 7 Nov 2026. Sources in §9; unconfirmed items marked **(unverified)**. The prior wave's legal report (`../wordsmith-wave/ws-legal.md`) covered public registers and UK filings; this report does not repeat it.*

## 1. Bottom line

1. **The structural reason in-house legal work needs a browser: you are a guest in someone else's system.** APIs are sold to the tenant owner. Counsel spends the day inside *counterparties'* systems — the buyer's Coupa, the seller's data room, the customer's CLM, the other side's e-signature account — where they hold a seat, not a key. Every portal I checked sells an API to the owner and gives the invited guest a UI. That is a defensible case for browser automation, and it is not the same claim as "this public website has no API".
2. **Every workflow below has the same shape: the guest seat is the constraint, not the click.** The hard parts are the invitation (a link in an email), the login (SSO or a one-time code to a shared mailbox), guest roles, and proving afterwards what the guest did.
3. **E-signature and CLM are not browser problems for the owner.** DocuSign, Adobe Acrobat Sign, Ironclad, Datasite and Intralinks all ship APIs, and Datasite launched an MCP server in April 2026 (vendor claim) so assistants work in live data rooms under the room's own permissions. A demo built on an account we own would survive the browser being removed. Say so; it buys credibility.
4. **Free sandboxes exist, mostly on the guest side**: SAP Business Network supplier Standard account (free), Coupa Supplier Portal (free to suppliers), DocuSign developer account (free), Adobe Acrobat Sign Developer Edition (free, watermarked). Coupa and Ariba *buyer* tenants are not freely available, so a real buyer portal cannot be a demo dependency.
5. **The multi-person problem in legal is confidentiality, not tab collisions.** Two agents on one matter is fine; two agents on *adverse* matters sharing a browser profile can waive privilege or create a conflict. A shared legal browser needs matter-scoped profiles and an audit trail that survives a regulator's question.

## 2. Findings

### 2.1 The guest-seat pattern

| System | API position | What the in-house guest gets |
|---|---|---|
| Coupa Supplier Portal | Buyer-side Coupa APIs exist for the customer tenant **(unverified this wave)** | Free supplier account, UI for invoice/PO/ASN; cXML or CSV for some flows |
| SAP Business Network (Ariba) | Ariba developer portal and sandbox, for customer/partner organisations | Free Standard supplier account; UI for PO confirmation, invoices, questionnaires; cXML but buyer-configured |
| DocuSign | Full eSignature REST API, free developer account | Recipient of someone else's envelope: signing UI only |
| Adobe Acrobat Sign | Full API, free Developer Edition | Recipient signing UI only |
| Ironclad | CLM API, OAuth, sandbox mode | Counterparty review link in their UI |
| Datasite / Intralinks | Public API programmes; Datasite MCP server | Participant UI, Q&A, permissioned viewer |
| OneTrust | Developer portal and APIs; sandbox is an account type | Vendor questionnaire, DSAR form |

**The API is a tenancy feature.** A lawyer is invited into dozens of other companies' tenancies a year and holds a key to none. MCP inherits the same permissions — Datasite says its server "operates entirely within Datasite's existing access controls" — so it does not close the gap for the invited outsider. The opening follows from how SaaS permissions work, not from a vendor being slow.

### 2.2 Real pain

- A SaaS company reports **manually uploading invoices to more than 100 supplier portals every month** and asks whether anything automates it (r/procurement, Jan 2024). No product answer in the thread.
- RPA practitioners automating Ariba invoice creation report the page **navigating away mid-flow** after search or submit (UiPath forum, Feb 2025) — "the selector was right yesterday", on a portal that has an API for its owner.
- Data-room Q&A runs on **roles**: an Answer Coordinator gatekeeps, Experts propose but cannot submit, Approvers sign off (Firmex). Genuinely multi-person, coordinated inside the counterparty's tool.
- CLM sandboxes are gated: Ironclad's sandbox comes with a subscription, OneTrust's is an account type. An in-house team cannot stand up a counterparty's environment to test against.

### 2.3 What can be legitimately automated in a demo

| System | Free/sandbox route | Verdict |
|---|---|---|
| DocuSign eSignature | Free developer account, isolated demo environment ([link](https://developers.docusign.com/platform/account/)) | **Yes** — API-first; use it as the *counterparty's* system |
| Adobe Acrobat Sign | Free Developer Edition, separate instance, watermarked ([link](https://www.adobe.com/acrobat/business/developer-form.html)) | Yes; pick one e-sign vendor |
| SAP Business Network supplier | Free Standard account, but registration needs real company details ([link](https://www.sap.com/products/business-network/suppliers/pricing.html)) | **No sign-up tonight** (rules forbid it); mock it, cite the free tier |
| Coupa Supplier Portal | Free for suppliers; registration is a real account ([link](https://compass.coupa.com/en-us/products/product-documentation/supplier-resources/for-suppliers/coupa-supplier-portal)) | Same: mock, cite the docs |
| Ironclad / OneTrust / Datasite / Intralinks | Account or partner relationship required | Cite as evidence of the pattern; don't depend on them |
| Government/regulator portals | Prior wave: WebFiling works, IPO Cloudflare-blocked | Prior wave owns this |

**Demo rule:** build the mock counterparty portal ourselves, seed it with the *observable* behaviour of the real ones (Coupa's invoice fields, Ariba's PO acknowledgement, VDR Q&A roles), label it a mock. Automating a real third party's portal with a borrowed credential is what a legal-track judge would mark down.

### 2.4 Several people, one matter

- **Shared credentials.** A company holds one supplier-portal account with several named users. An agent logging in as "the company" erases the distinction between people that an audit trail exists to preserve.
- **Sequential gates.** Signature order, Q&A approval and approval chains mean an agent acting early creates a legally wrong artefact: an envelope sent before approval, an answer published before review.
- **Stale state.** Two people or agents editing one contract record; a VDR answer made wrong by a new document version; a duplicate invoice after two agents retry.

### 2.5 Fitting Wordsmith's Receive, Route, Resolve, Record

Receive: the request arrives in Slack or email, with the portal link and the counterparty's instructions. Route: to the right matter, person and approval chain — the guest seat and the matter wall decide who may act. Resolve: the agent does the portal work; humans supply credentials and approvals. Record: the evidence bundle — the counterparty's own status page, hashed — which fits "Record" better than a chat transcript. The browser is the Resolve step and the source of Record; it changes nothing about the first three.

## 3. Workflow table

| # | Who does the work | What they're trying to do | Where APIs/MCP fail | What the browser adds | What goes wrong with several people/agents | Evidence |
|---|---|---|---|---|---|---|
| L1 | In-house counsel + finance, on a customer's Coupa/Ariba portal | Acknowledge a PO, upload insurance certificates, submit the contract-referenced invoice | Buyer-side API belongs to the buyer; supplier gets UI plus optional cXML | Guest-seat automation with field-level read-back and a submission receipt | Shared company account; finance and legal editing one invoice; duplicate on retry | Coupa CSP docs; SAP pricing; r/procurement; UiPath |
| L2 | In-house counsel + counterparty legal team | Execute an NDA inside the *other side's* CLM or e-sign account | Owner's API; guest gets a review/sign link | Walks the guest review flow, checks the rendered document, captures the completion certificate | Signature order; approver acts before legal approves; two signers, one envelope | Ironclad API/sandbox docs; DocuSign dev account |
| L3 | Deal team + outside counsel, seller's data room | Ask and answer diligence questions to a deadline | Datasite/Intralinks APIs and MCP serve the room owner; participants use the UI | Q&A submission, role-aware answering, version checks | Coordinator gatekeeping; duplicate questions; stale answers after a version bump | Firmex Q&A roles; Intralinks Q&A |
| L4 | DPO/legal + IT + HR | Answer one DSAR across a privacy platform and processor portals | OneTrust API needs a tenant; processors have per-portal logins | Intake, identity verification, portal-by-portal retrieval | Same request worked twice; identity evidence mis-filed; 30-day clock | OneTrust developer portal; prior wave W7 |
| L5 | Commercial counsel + procurement | Onboard a supplier: questionnaire, checks, contract, registration | Questionnaire and registration are UI-only | Fills and files the questionnaire, registers, verifies acceptance | Both teams registering one supplier; resubmission after timeout | Coupa/Ariba registration docs; prior wave W2/W9 |
| L6 | Company secretary + regulator portal | File a change and prove the register changed | WebFiling is browser-only; reads have an API | Filing plus post-state verification | 2FA and auth code belong to one person | Prior wave W1 |
| L7 | In-house counsel + business unit | Handle "review our MSA in our CLM", arriving as a bare link | No API for the guest | Opens the link, extracts the document, answers in their UI | Two requests, one link; wrong matter; privilege leak | Guest-API pattern; mock |

## 4. Removal test

| # | Without a browser | Recommendation |
|---|---|---|
| L1 | **Stops.** No supplier-side API for the guest; a human retypes it. | Keep — strongest |
| L2 | **Mostly survives** if we own the e-sign account: send by API, sign in a tab. As a guest, it stops. | Keep only as the guest variant |
| L3 | **Partly survives.** Datasite's MCP server and bulk Q&A import serve the owner; guest answering is UI. | Breadth, not spine |
| L4 | **Partly survives.** OneTrust is API-rich for its tenant; browser covers intake and processor portals. | Demote |
| L5 | **Stops** at questionnaire and registration. | Sub-step of L1 |
| L6 | **Stops** at filing (prior wave). | Don't repeat |
| L7 | **Stops.** A link in an email is the entire interface. | Narrative frame |

**L1 is the only workflow where removing the browser removes the work end to end.** L2 survives if we own the account, so "we can send an envelope by API" belongs on a slide, not in the spine.

## 5. Shared browser requirements (legal view)

1. **Matter-scoped identity, not machine-scoped.** Each matter gets its own profile, cookie jar, downloads and memory namespace. Adverse matters never share a profile; closing a matter deletes it.
2. **Act-as, not shared login.** Record which person the agent acts for and which portal account it used; where a portal supports one company login, serialise access per account.
3. **Leases on portal accounts and records, not just tabs.** A supplier account, a Q&A thread and a contract record each need an owner, expiry and handoff — those are what collide.
4. **Read-back before "done".** Re-open the portal's own status view; record screenshot, URL, timestamp and hash. Never trust the agent's success claim.
5. **Redaction before storage.** History, downloads and DOM snapshots hold privileged material and personal data; capture only the evidence spans, under the matter's retention rule.
6. **No credential handling by the agent.** The human enters password, SSO and 2FA; the agent resumes.
7. **A pre-fixed approval gate for anything that binds the company**, plus an exportable per-matter evidence bundle: steps, sources, hashes, approvals and a "could not verify" list.

## 6. One end-to-end workflow: "guest in their portal"

*Hedged Bets sells software to a buyer who insists the contract be executed and the supplier onboarded through **their** procurement portal. Counsel owns the contract, finance the invoice, procurement the questionnaire; the buyer's own agent sits on the other side.*

| Step | Actor | What happens | Confirmable evidence |
|---|---|---|---|
| 1 | Business owner | Asks in Slack (mock) for the deal to be closed | Request card |
| 2 | Legal agent | Reads the buyer's onboarding email; extracts portal link, PO number, required documents | Extracted fields + source link |
| 3 | Buyer's mock portal | Agent opens it; MFA challenge | Screenshot; agent stops |
| 4 | Human (counsel) | Enters the one-time code; approves the binding actions | Approval record: person, time |
| 5 | Agent | Completes the questionnaire from the CLM record, uploads the insurance certificate, re-reads every saved value | Field-by-field read-back; portal "submitted" status |
| 6 | Agent + buyer's agent | Uploads the contract; buyer's agent countersigns | Status "fully executed" + certificate of completion |
| 7 | Agent | Confirms PO acknowledged, submits the invoice against it | Portal invoice number + status |
| 8 | Finance human | Approves the invoice submission | Approval record |
| 9 | Verifier | Re-opens the portal as a fresh reader, hashes the three status pages, writes the bundle | Bundle: URLs, hashes, timestamps, "could not verify" list |

**End state:** supplier active, contract executed, PO acknowledged, invoice accepted — all inside the counterparty's system, none reachable through an API we hold.
**Judge check in a minute:** the bundle shows the portal's own status page for each of the three, hashed and timestamped, plus two human approvals and the MFA stop. Change the insurance expiry date and watch the read-back catch it.
**Multi-agent element:** the buyer's agent is seeded to change the PO reference mid-run, forcing a detected conflict instead of a silent overwrite.

## 7. Risks and unknowns

- **Sandbox reality (unverified):** whether DocuSign's developer account allows enough envelopes for a multi-signer demo, and whether Adobe's watermark is acceptable on screen.
- **Coupa/Ariba buyer-side access** is unobtainable tonight; label every buyer-tenant reference as a mock.
- **Terms of service.** Supplier portals are private services with acceptable-use terms. Automating a mock is fine; automating a real account on someone else's tenant at a hackathon is not.
- **Legal-advice boundary.** The agent extracts, files, verifies and flags. It does not conclude on enforceability, liability or compliance, and files nothing with a court or regulator.
- **Privilege and confidentiality** are the real risk of a shared browser: one profile across two matters can waive privilege.
- **Unverified:** exactly what Datasite's MCP server exposes (JavaScript-rendered docs; the launch is a vendor claim).

## 8. Three openings

**O1 — "Guest mode": a browser that logs in as an invited outsider.**
*New:* treat the counterparty seat as a first-class primitive — invitation link → MFA handoff → role-aware UI → read-back → evidence, per matter. Nothing I found packages the guest seat; RPA and browser agents treat every site as anonymous or owned.
*Nearby:* Playwright/agent-browser for driving, Browserbase/Steel for isolation, RPA for clicking without evidence.
*Evidence:* §2.1; Coupa/Ariba/VDR guest roles; the 100-portal invoice post.

**O2 — Matter walls as a product feature.**
*New:* a shared browser whose unit of isolation is the *matter*, with an audit trail of who acted for whom. It generalises to any confidential multi-client work.
*Nearby:* browser pools give session isolation but no notion of a matter; CLMs give matter records but no browser.
*Evidence:* Q&A role models, supplier accounts with multiple named users, professional confidentiality duties.

**O3 — "File it, then prove the other side recorded it."**
*New:* not the filing (prior wave), but the counterparty's acknowledgement — PO acknowledged, contract executed, invoice accepted, answer published. Each is a status page in someone else's system, and that page is the demo's receipt.
*Nearby:* Wordsmith drafts and messages; e-sign vendors prove a signature, not the business state around it.
*Evidence:* portal status views in Coupa/Ariba docs, certificates of completion, the read-back pattern.

## 9. Sources

| URL | Recency | Supported |
|---|---|---|
| https://developers.docusign.com/platform/account/ | current | Free DocuSign developer/demo account, isolated environment |
| https://www.adobe.com/acrobat/business/developer-form.html | current | Free Acrobat Sign Developer Edition; watermarked, not a sandbox (community, 2021) |
| https://docs.coupa.com/en/supplier-documentation/coupa-for-suppliers/the-coupa-supplier-portal-or-csp/features-and-processes-in-the-coupa-supplier-portal/invoices/about-invoices | current | Supplier invoice routes: CSP UI, cXML, email/PDF |
| https://compass.coupa.com/en-us/products/product-documentation/supplier-resources/for-suppliers/coupa-supplier-portal | current | CSP free for suppliers; UI tasks: PO, invoice, ASN, catalog |
| https://www.sap.com/products/business-network/suppliers/pricing.html | current | Supplier Standard account; multiple users per account |
| https://community.sap.com/t5/spend-management-q-a/what-is-the-difference-between-sandbox-api-sap-com-and-openapi-ariba-com/qaq-p/12756420 | 20 Jun 2023 | Ariba sandbox API vs test tenant; app + API access request |
| https://help.sap.com/doc/2fbe520459be441d96f9292813c61374/cloud/en-US/980edbc352864b4ba7a252a30075da9e.pdf | current | Ariba Developer Portal is for customers/partners |
| https://www.reddit.com/r/procurement/comments/1918qi5/uploading_invoices_to_supplier_portals/ | 8 Jan 2024 | Manual upload to 100+ supplier portals monthly |
| https://forum.uipath.com/t/facing-issues-while-automating-invoice-creation-process-in-ariba-portal/870223 | 13 Feb 2025 | Ariba invoice automation fails mid-flow |
| https://support.firmex.com/hc/en-us/articles/204467698-Questions-and-Answers-Q-A | current | VDR Q&A roles: Answer Coordinator, Expert, Approver |
| https://support.intralinks.com/hc/en-us/articles/39205778917147-Q-A-for-buyers-DealCentre-AI | current | Q&A import by spreadsheet; DealCentre AI |
| https://developer.ironcladapp.com/docs/launch-a-workflow | current | Ironclad API and sandbox mode |
| https://support.ironcladapp.com/hc/en-us/articles/12269963678487-Use-Sandbox-Mode | current | Sandbox is an account feature, not a public sandbox |
| https://developer.onetrust.com/ | current | OneTrust developer portal: APIs and SDKs |
| https://my.onetrust.com/s/article/UUID-058e5b33-fdb8-dd39-58bf-f5aa45f9187a?language=en_US | current | Sandbox vs UAT are account types |
| https://www.datasite.com/en/company/news/datasite-becomes-the-first-vdr-provider-to-connect-ai-assistants-directly-to-live-deal-content-with-mcp-server-launch | 28 Apr 2026 | Datasite MCP server launch; Claude/ChatGPT/Copilot in live data rooms (**vendor claim**) |
| https://www.datasite.com/en/resources/ai-at-datasite/datasite-mcp | current | MCP operates within existing access controls; audit trail (**vendor claim**) |
| https://www.datasite.com/en/legal/api-program-terms | effective 24 Apr 2026 | Datasite "MCP Server and API Program" terms |
| https://www.intralinks.com/why-intralinks/apis-deployment | current | Intralinks APIs and interactive test environment |
