---
doc_title: Dashboard Performance Troubleshooting
doc_type: troubleshooting
---

# Dashboard Performance Troubleshooting

## Known issue: slow dashboards during peak hours
EggCRM has a **known issue**: dashboards and large reports can load slowly during peak hours,
approximately **9–11 AM ET**, when aggregate query load is highest. This is a recognized
performance degradation and a fix is scheduled for an **upcoming release**. If a customer reports
slowness specifically in that window, identify it as this known issue rather than opening a new
bug — but still capture details if the slowness is severe or outside that window.

## Workarounds while the fix ships
1. **Narrow the date range** on the report or dashboard — aggregating fewer records is faster.
2. **Reduce widgets per dashboard** — split a heavy dashboard into two.
3. **Run heavy reports outside 9–11 AM ET** where the timing is flexible.
4. **Export to CSV** for large pulls instead of rendering them on screen.

## When it's NOT the known issue
Treat it as a separate problem (and gather details for a ticket) when slowness:
- happens **outside** the 9–11 AM ET window, or
- affects core navigation/record pages, not just dashboards, or
- coincides with errors rather than slow loads.

## Details to collect for a ticket
If you do file a bug, collect: browser and version, the specific dashboard/report, the time and
timezone it occurred, the approximate record volume, and any error messages. Set ticket priority
by impact. See **Service Levels & Support** for priorities and channels.

## Checking for incidents
Before filing, check the EggCRM **status page** for any active incident that could explain
broader slowness or errors.
