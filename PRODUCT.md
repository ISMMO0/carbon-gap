# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python + FastAPI backend (uv), static front-end served by FastAPI. Mockup first as a single HTML file with fake data, then a real front-end. Deploy target open (Aiven App Runtime used on a previous project). All AI features use the OpenAI API.

## Users

Primary: climate journalists and NGO researchers investigating who emits what, and whether declared emissions match reality. They explore a country or sector, find suspicious gaps, and need a sourced dossier they can publish or act on.
Secondary: regulators, ESG investors, the wider public. Demo audience: the OpenAI Paris DevDay hackathon jury.

## Product Purpose

Carbon Gap compares what countries and companies declare they emit with what independent data observes (satellite and asset-level estimates), shows the gap on an interactive globe, and values it at the price of carbon. An AI analyst answers questions, drives the map, and writes sourced reports. Today this reconciliation is done by hand and takes months or years; Carbon Gap keeps it continuous.

## Positioning

Existing projects (Climate TRACE, Kayrros, Carbon Mapper) produce emissions data. Carbon Gap uses them as sources and adds the reconciliation: declared vs observed, the gap in tonnes and euros, and an AI analyst that explains and documents it.

## Operating Context

Desktop browser, investigation sessions. Drill-down: globe → country → sector → site/company. Questions in natural language to the analyst; results appear on the map. Output is a report (PDF/shareable) with sources and confidence.

## Capabilities and Constraints

- Global coverage at country level; Europe in depth at company/site level (EU ETS).
- Real-time only where data is truly real-time (e.g. power plants); elsewhere "continuous".
- Gaps are "to investigate", with a confidence level and sources, never accusations.
- Hackathon timeline: 24–25 Oct 2026, 2-minute pitch video required.
- App language: English.

## Brand Commitments

Name: Carbon Gap.

## Evidence on Hand

None yet. The mockup uses synthetic data and must be labelled as such. No invented real-world claims about named companies.

## Product Principles

1. Every number shows its source and confidence.
2. The map is the interface; the AI acts on it, not beside it.
3. Gap first: the difference between declared and observed is the headline, not raw totals.
4. Honest framing: "gap to investigate", never "fraud".
