# Post Types

Each recurring post type has a recommended structure. All still obey the problem-first rule.

## 1. Release announcement

For a new version (e.g. v3.5) or new capability.
- **Hook:** the pain the new feature kills, not "v3.5 is out."
- Recap in one line what QAI already did, then "with vX.Y, ...".
- 2-4 new capabilities, each concrete.
- Differentiator line (deterministic / grounded / keyless / transparent).
- CTA: live app + MCP install.
- Source of truth for what's actually new: `CHANGELOG.md` and the Roadmap in `CLAUDE.md`. Never invent features.

## 2. Educational QA tip

Pure value, product mentioned lightly at the end. Great for authority and reach.
- **Hook:** a common QA mistake or misconception.
- Teach one specific, useful thing (e.g. what makes a test "flaky" vs "failing", why risk needs evidence, what an audit actually checks).
- Tie back: "this is exactly the kind of thing QAI's [feature] does for you," soft CTA.
- These build trust with test managers and the community. Pull substance from the knowledge-base topics in `CLAUDE.md` (ISTQB, OWASP, risk-based testing, test pyramid, EU AI Act).

## 3. Milestone

Registry listing, awesome-mcp-servers merge, PyPI publish, X stars, first N users, visit counter, etc.
- **Hook:** frame the milestone as validation of the *problem being real*, not as bragging. "Turns out a lot of teams have the 'document nobody trusts' problem."
- Short, genuine, grateful. Community-facing.
- Link to the relevant listing.
- Good for the "building in public" voice.

## 4. Case study / use case

A concrete scenario (real or illustrative) of QAI solving a problem.
- **Hook:** the situation before (the mess).
- Walk through: fed it X, got Y, here's what changed.
- Keep it honest and specific. If illustrative, don't imply it's a named real client without permission.
- Strong for decision makers.

## 5. Behind-the-scenes / building-in-public

How something was built, a design decision, a hard bug, the MCP restraint principle.
- **Hook:** the interesting problem or decision.
- First person, candid, craft-focused.
- Resonates most with the dev/OSS/MCP audience.
- The "server doesn't try to out-write your assistant" principle (see messaging-foundation.md) is a repeatable winner here.

## Cadence suggestions (if Gabi asks for a plan)

- Release posts: on every meaningful version.
- Educational tips: the steady drumbeat between releases, ~1-2 per week, cheap to produce and best for reach.
- Milestones: whenever they genuinely happen.
- Behind-the-scenes: opportunistic, when a decision or fix is genuinely interesting.
- Case study: heavier, occasional, high-impact for decision makers.
