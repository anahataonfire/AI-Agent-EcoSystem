# Skill: Enhanced Planning

> Structured approach to breaking down tasks, with mandatory discovery phase for complex requests.

---

## 🛑 Socratic Gate (MANDATORY for Complex Requests)

Before implementing complex features, new projects, or vague requirements:

### 1. STOP - Do NOT start coding
### 2. ASK - Minimum 3 questions:
   - 🎯 **Purpose**: What problem are you solving?
   - 👥 **Users**: Who will use this?
   - 📦 **Scope**: Must-have vs nice-to-have?
### 3. WAIT - Get response before proceeding

| Pattern | Action |
|---------|--------|
| "Build/Create/Make [thing]" without details | 🛑 ASK 3 questions |
| Complex feature or architecture | 🛑 Clarify before implementing |
| Vague requirements | 🛑 Ask purpose, users, constraints |

---

## Task Breakdown Principles

### 1. Small, Focused Tasks
- Each task should take 2-5 minutes
- One clear outcome per task
- Independently verifiable

### 2. Clear Verification
- How do you know it's done?
- What can you check/test?
- What's the expected output?

### 3. Be SPECIFIC, Not Generic

| ❌ Wrong | ✅ Right |
|----------|----------|
| "Set up project" | "Run `npx create-next-app`" |
| "Add authentication" | "Install next-auth, create `/api/auth/[...nextauth].ts`" |
| "Style the UI" | "Add Tailwind classes to `Header.tsx`" |

### 4. Keep It SHORT

| ❌ Wrong | ✅ Right |
|----------|----------|
| 50 tasks with sub-sub-tasks | 5-10 clear tasks max |
| Every micro-step listed | Only actionable items |
| Verbose descriptions | One-line per task |

> **Rule:** If plan is longer than 1 page, it's too long. Simplify.

---

## Plan Structure

```
# [Task Name]

## Goal
One sentence: What are we building/fixing?

## Tasks
- [ ] Task 1: [Specific action] → Verify: [How to check]
- [ ] Task 2: [Specific action] → Verify: [How to check]
- [ ] Task 3: [Specific action] → Verify: [How to check]

## Done When
- [ ] [Main success criteria]
```

---

## For RSS Pipeline Tasks

Break user queries into structured actions:

1. **Analyze** the query for:
   - Target topic/domain
   - Desired output format
   - Time constraints

2. **Plan Actions** - ALWAYS fetch from MULTIPLE sources:
   - `DataFetchRSS` #1: Fetch from Google News (25 items)
   - `DataFetchRSS` #2: Fetch from Reddit for discussion
   - `CompleteTask`: Write report with all evidence

### Output Format

```json
{
  "action_type": "tool_call",
  "tool_name": "<DataFetchRSS|CompleteTask>",
  "params": { ... },
  "success_criteria": ["..."]
}
```

### Dynamic Search (Topic-Specific)

Use `url: "google_news"` with `search_query: "<topic>"` for specific topics.

---

## Report Structure

1. **Executive Summary** (2-3 sentences)
2. **Key Developments** (main news items with citations)
3. **Analysis & Trends** (patterns observed)
4. **Key Players** (companies, people involved)
5. **Outlook** (future implications)

## Citation Rules (CRITICAL)

- **EVERY** factual claim MUST have a citation: `[EVID:ev_123]`
- Do NOT write facts without citations
- **FAILING TO CITE WILL CAUSE MISSION FAILURE**

---

## Constraints

- Max 25 items per fetch
- Prefer recent articles (24h window)
- Reports should be 500+ words with structured sections
- If ANY source returns an error, proceed with existing evidence

---

## Anti-Patterns (AVOID)

| Anti-Pattern | Why |
|--------------|-----|
| Jumping to solutions before understanding | Wastes time on wrong problem |
| Assuming requirements without asking | Creates wrong output |
| Over-engineering first version | Delays value delivery |
