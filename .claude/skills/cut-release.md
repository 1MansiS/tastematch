# Skill: Cut a Release

Invoke when a version milestone is ready to ship (e.g. "cut v0.2", "ship v1.0").

## Steps

1. **Verify all tests pass**
   ```bash
   pytest tests/ -v
   ```
   Do not proceed if any tests fail.

2. **Check README is current**
   - Roadmap items checked off correctly?
   - Supported providers / input types / venue types accurate?
   - Project structure matches actual files?


3. **Review MEMORY.md**
   - Any session learnings worth promoting permanently to CLAUDE.md?

4. **Commit**
   ```bash
   git add -A
   git commit -m "release: vX.X — [one line summary]"
   ```

5. **Tag**
   ```bash
   git tag vX.X
   git push origin main --tags
   ```

6. **Write GitHub release note**
   - Tag: vX.X
   - Title: "vX.X — [capability added]"
   - Body: 3–5 bullets covering what's new, what's fixed, what's next

7. **Website check**
   - v0.2+: Is project page at 1mansis.github.io/projects/tastematch updated?
   - v1.0: Full page with architecture diagram, demo output, design decisions?
   - Post on HackerNews "Show HN" at v1.0 when ready
