# ADR-004: Next.js Full-Stack on Vercel, Stateless by Design

**Status:** Superseded by [ADR-006](./ADR-006-fastapi-react-render.md)
**Date:** 2026-06-10

## Context

Deliverables are a source repository and a publicly accessible deployed URL. The prototype is explicitly standalone — no COLA integration, no federal authorization process, and IT guidance was "don't store anything sensitive for this exercise."

The agency's production network blocks egress to many external domains (a prior vendor's ML endpoints were firewalled). However, the prototype is evaluated from the public internet, not from inside the TTB network.

The user base spans extremes of technical comfort ("agents who print emails" to recent CS graduates); the UI bar set by stakeholders is "something my 73-year-old mother could figure out."

## Decision

- **Framework:** Next.js (React frontend + API routes) as a single codebase and single deployment unit.
- **Hosting:** Vercel — one-command deploy, free tier sufficient, satisfies the deployed-URL deliverable with zero infrastructure work.
- **State:** Fully stateless. Images are processed in memory and never persisted; no database, no auth, no retention. This is both the simplest design and the most compliance-friendly posture given PII/retention concerns raised by IT.
- **Secrets:** Anthropic API key held server-side in environment variables; the browser never talks to the model API directly.

### Production path (documented, not built)

The egress-firewall constraint is real for any production deployment. The documented path is inference inside a government-authorized boundary — e.g., Claude via AWS Bedrock in GovCloud (FedRAMP High) or an equivalent Azure Government endpoint — so model traffic never leaves the authorized perimeter. This prototype deliberately does not simulate that constraint; doing so (e.g., local OCR models) would sacrifice accuracy and velocity to solve a problem the prototype doesn't have.

## Alternatives Considered

1. **FastAPI backend + separate React frontend.** Viable; rejected for prototype scope — two deployments, CORS, more moving parts, no capability gain.
2. **Local/self-hosted vision model to respect the firewall constraint now.** Rejected: large accuracy and effort cost to satisfy a production constraint that is out of scope by the IT stakeholder's own framing ("a standalone proof-of-concept").
3. **Adding a database for result history.** Rejected: contradicts the no-retention guidance, adds PII surface, and serves no evaluation scenario.

## Consequences

- (+) Minimal operational surface; evaluators get a URL that just works.
- (+) Statelessness converts a compliance risk into a design feature.
- (−) No persistence means batch results live only in the browser session; acceptable for a prototype, noted as future work (export to CSV is a cheap mitigation).
- (−) Vercel serverless function limits (duration/payload) constrain batch design — addressed in ADR-005.
