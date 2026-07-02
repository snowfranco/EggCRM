---
doc_title: Workflow Automation
doc_type: feature_guide
---

# Workflow Automation

Workflow automation requires the **Professional** plan or higher. It is not available on Starter.

## Creating an automation
Go to **Settings > Workflows > New Automation**. An automation has three parts: a **trigger**
(what starts it), optional **conditions** (filters that must be true), and one or more **actions**
(what it does). Give the automation a name, build the rule, then toggle it **Active**. New
automations are created inactive so you can review them before they run.

## Triggers
Available triggers include: a contact is created or updated, a contact enters or leaves a segment,
a deal is created, a deal changes stage, a deal is marked Won or Lost, a date field is reached
(for example, renewal date in 30 days), or a form is submitted. Each automation has exactly one
trigger.

## Conditions
Conditions filter which records the automation acts on — for example, "deal amount > 5000" or
"contact tag is `vip`". Conditions use the same fields as segments, including custom fields.
Combine conditions with AND/OR groups.

## Actions
Available actions include: send a templated email, create a task and assign it to a user, update
a field on the record, add or remove a tag, move a deal to a stage, send a Slack message
(requires the Slack integration, Professional+), and call a webhook (custom webhooks are
Enterprise-only). An automation can run several actions in order.

## Testing and monitoring
Use **Test run** to simulate an automation against a sample record without sending real emails.
Once active, each execution is recorded in the automation's **Run history** with the record it
acted on and the outcome of each action, so you can confirm it is firing as intended.

## Limits
There is no hard cap on the number of automations on Professional or Enterprise. Email-sending
actions are subject to your plan's email-sending limits; very high-volume sends should use a
segment plus a scheduled campaign rather than a per-record automation.
