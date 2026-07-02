---
doc_title: Contact Management
doc_type: feature_guide
---

# Contact Management

Contact management is available on every EggCRM plan, including Starter.

## Adding contacts
Add a single contact from **Contacts > New Contact**. Each contact stores a name, company,
email, phone, owner (the team member responsible), tags, and a free-form notes field. Every
contact has an activity **timeline** that automatically records emails, notes, and deal changes.

## Importing contacts
Bulk-import from **Contacts > Import** using a CSV file. Map your CSV columns to EggCRM fields
during import; unmatched columns can be created as custom fields. Imports are de-duplicated by
email address — a row whose email already exists updates the existing contact instead of creating
a duplicate.

## Organizing with tags and segments
Apply **tags** to group contacts (for example, `lead`, `vip`, `newsletter`). Build **segments**
from filters on tags, company, owner, or custom fields. Segments are dynamic — a contact enters
or leaves a segment automatically as its fields change. Segments are the audience selectors used
by workflow automation.

## Custom fields
Create custom fields under **Settings > Data > Custom Fields**. Supported types: text, number,
date, dropdown (single/multi-select), and boolean. Custom fields are available for contacts and
deals and can be used in segment filters and automation conditions.

## Email integration
When you connect your email under **Settings > Integrations**, messages to and from a contact
are automatically logged to that contact's timeline. Email integration is available on every
plan. See **Integrations Overview** for connecting Gmail (Professional+) or generic IMAP/SMTP.
