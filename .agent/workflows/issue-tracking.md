---
description: Mandatory issue tracking before any fix work
---

## Before ANY debugging or fix work:

1. **Create/update ISSUES.md** in artifacts directory
2. List EVERY problem user reported (use verbatim quotes)
3. For each issue, record:
   - Issue description (exact user words)
   - Expected behavior
   - Actual behavior  
   - **Verification method** (HOW will user confirm fix works?)

4. **Do NOT touch code until ALL issues are logged**

5. After EACH fix:
   - Check off the item in ISSUES.md
   - Verify from USER's perspective (not just API)
   - If UI change: use browser_subagent to screenshot

## Issue Template

```markdown
## Issue: [Short description]
- **User said:** "[exact quote]"
- **Expected:** [what should happen]
- **Actual:** [what is happening]
- **Verification:** [how user will confirm - e.g., "Refresh Library page, see 4 items"]
- **Status:** [ ] Not started / [/] In progress / [x] Fixed and verified
```
