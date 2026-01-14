---
description: Verify UI after any backend/API change
---

## After ANY change that affects what user sees:

// turbo
1. Restart API server if code changed:
   ```bash
   pkill -f "uvicorn api.main"; sleep 1; .venv/bin/uvicorn api.main:app --port 8000 &
   ```

2. **Use browser_subagent** to navigate to affected page

3. **Capture screenshot** of the result

4. Verify:
   - [ ] Data loads (not empty unless expected)
   - [ ] Counts match DB queries
   - [ ] No error messages visible
   - [ ] Page renders without console errors

5. **If verification fails:**
   - DO NOT claim fix is complete
   - Debug further
   - Repeat verification

6. **Only report success after UI confirmation**

## Key Rule
Testing API via `curl` is NOT sufficient.
User sees UI, not curl output.
Always verify what USER sees.
