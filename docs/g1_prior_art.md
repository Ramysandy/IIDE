# G1 prior-art memo

Sweep date: 2026-10-28. Authoritative spec: `IIDE_EXECUTION_SPEC.md` §18 Phase 0 / Gate G1.
Structured extract: [`g1_matrix.yaml`](g1_matrix.yaml). Local unpublished PDFs in this folder stay gitignored.

This memo does **not** set `configs/gates.yaml`. Operator sign-off 2026-10-28 set G1 to
**PASSED**; claim restrictions below still apply.

## Decision

**Recommended decision: GO** for the combination claim (E1 + E2 + E3).

G1 asks: does any existing study already measure **product detection loss by attack replay under instruction-wording counterfactuals**? In this sweep, no occupying study was found. Overlap on single elements is expected and is not a kill.

That is a search result, not a proof of absence. See Limitations.

## Combination test

| Element | Meaning | Already exists? | IIDE claim |
|---|---|---|---|
| E1 | Harm = lost detectability of product attacks | Adjacent (OpenAI incident; IFG “degrading logging”; agent-trace tampering) | Novel only as a **measured outcome** on product telemetry |
| E2 | Instruction wording as cause (ambiguous / scoped / neutral) | Yes as a method (Overeager, SecDrift, prompt-structure papers) | **Not** a method contribution |
| E3 | Attack-replay oracle vs frozen detection | Yes as detection-engineering practice (Sigma / Atomic Red Team) | **Not** a technique contribution |
| E4 | Latent erosion (LEI) | No match found | Most distinctive measure |
| E5 | Disclosure gap + CAI | DG adjacent (OpenAI denial); CAI no direct match | CAI stays exploratory (spec 0.12) |

The defensible paper is **ordinary instructions → product attacks become invisible → measured by frozen-rule replay**, with LEI as the extra measure. Individual elements do not carry a novelty claim.

## Matrix (short)

Full rows, URLs, and read-depth are in `g1_matrix.yaml`. `occupies_g1_gap` is `false` for every row.

| Work | Read | E1 | E2 | E3 | Why it is not IIDE |
|---|---|---|---|---|---|
| Overeager Coding Agents, arXiv:2605.18583 | full HTML | — | overlap | — | Out-of-scope actions on benign tasks; oracle is filesystem/shell, not SIEM fire/miss |
| SNARE, arXiv:2605.28122 | full HTML | — | adjacent | — | Overeager elicitation follow-on |
| Trace tampering, arXiv:2609.30266 | full HTML | adjacent | — | — | Agent’s own traces, not product telemetry |
| WeSCE, arXiv:2608.15092 | full HTML | — | adjacent | — | SAST/fuzz vulnerability drift under functional edits |
| SecDrift, arXiv:2607.25225 | full HTML | — | overlap | — | Sector-framed prompts; Bandit∪Semgrep rates |
| IaC CIS regression, arXiv:2608.13404 | full HTML | — | — | — | Checkov check regression in repair loops |
| IFG monitor, arXiv:2607.14570 | full HTML | adjacent | — | — | Sabotage monitor (incl. degrading logging); candidate baseline, not IIDE’s outcome |
| Towards Secure Logging, arXiv:2604.20211 | abstract | — | — | — | Dangerous logs, not missing logs |
| ASPI, arXiv:2605.17324 | full HTML | — | adjacent | — | Ambiguity amplifies prompt injection |
| AgentTelemetry, AIware 2026 | full PDF | — | — | — | Observes the agent, not the product detector |
| AlertGuardian, arXiv:2601.14912 | full HTML | — | — | — | Defender-side alert noise reduction |
| OpenAI alignment report, 2026-10-20 | full HTML | adjacent | adjacent | — | Real incident; not a replay-oracle experiment |
| Sigma / Atomic regression (industry) | web | — | — | overlap | Oracle technique already exists |
| SLEIGHT-Bench, arXiv:2605.16626 | full HTML | adjacent | adjacent | — | Evasion of *agent* monitors |
| Prompt Structure Redistributes, arXiv:2608.24857 | full PDF | — | overlap | — | Prompt variants change SAST CWE mix |

## What was actually read

Primary local sources (PDF extract): IIDE proposal, novelty check (excerpt-based, score 7/10), proposal review. The novelty check told Week 1 to read Overeager, trace-tampering, SecDrift, and WeSCE in full and to search for monitoring-evasion / telemetry-removal / detection-coverage regression. This sweep did that, plus IFG, the IaC CIS paper, SNARE, ASPI, AlertGuardian, AgentTelemetry, SLEIGHT-Bench, and the OpenAI incident report.

The proposal review’s concern that some 2026 arXiv IDs were unread is closed for the named neighbors above. Towards Secure Logging remains abstract-only.

## Search log

Queries (web + arXiv HTML, 2026-10-28) are listed under `searches` in `g1_matrix.yaml`. Spec-required phrases that were run: telemetry-removal evaluation; detection-coverage regression; observability regression; detection-as-code testing; log-removal refactoring; instruction-wording counterfactuals; plus “monitoring evasion evaluation”, “telemetry removal coding agent”, “silent detection failure agent”.

No returned paper combined E1+E2+E3 on **product** telemetry.

## Scoop risk (does not change GO today)

1. OpenAI is building evaluations for monitoring evasion after the Oct 2026 incidents. If that eval uses wording pairs and a frozen product-detection pipeline, G1 becomes **NARROW** (center LEI and DG).
2. Overeager could add a “telemetry” trap category. That would overlap E1+E2 but still lack E3 unless they replay attacks against product rules.
3. IFG already names degrading logging as sabotage. It is a **monitor**, not an IIDE measurement. Keep it as a comparison baseline when it can be run fairly (Phase 5 recorded it UNAVAILABLE).

## Claim restrictions

- Do not claim paired instruction variants (E2) as a method contribution.
- Do not claim attack replay against frozen rules (E3) as a technique contribution.
- Do not claim lost detectability (E1) as an unseen phenomenon.
- Lead with the combination and with LEI. Keep CAI exploratory.
- Do not cite this memo as “novelty established.” Cite it as “no occupying study found in the recorded sweep.”

## Limitations

- No exhaustive Google Scholar / ACM DL / IEEE Xplore crawl. Paywalled venues beyond the fetched AgentTelemetry PDF were not searched page-by-page.
- Preprints after 2026-10-28 are out of scope of this file.
- “No occupying study” is weaker than “the gap is verified.”
- Towards Secure Logging was not read past the abstract.

## What a human must still do

1. Read this memo and `g1_matrix.yaml`.
2. Spot-check at least Overeager, Qin et al. (2609.30266), WeSCE, SecDrift, IFG, and the OpenAI report.
3. G1 was set to PASSED on 2026-10-28. Re-open it if an occupying paper appears.
4. If an occupying paper is found, set G1 to `FAILED` or keep `OPEN` and change `recommended_decision` to `NARROW` / `NO_GO`.
