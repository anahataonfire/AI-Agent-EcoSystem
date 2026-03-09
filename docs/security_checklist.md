# Security Checklist for Commit Gate Validation

> Pre-commit security validation based on OWASP 2025 and vulnerability scanning principles.

---

## Quick Checklist

Run before any commit that modifies security-sensitive code:

### Access Control (OWASP A01)
- [ ] All endpoints have authentication checks
- [ ] Authorization verified for each action
- [ ] No IDOR vulnerabilities (direct object references)
- [ ] SSRF protections in place for external requests

### Configuration Security (OWASP A02)
- [ ] No hardcoded secrets in code
- [ ] Security headers configured
- [ ] Debug mode disabled in production
- [ ] Default credentials changed

### Supply Chain (OWASP A03)
- [ ] Lock files committed (`package-lock.json`, `requirements.lock`)
- [ ] Dependencies audited for vulnerabilities
- [ ] No typosquatting in package names
- [ ] Versions pinned (no `latest` or `*`)

### Cryptographic Practices (OWASP A04)
- [ ] Secrets stored in environment variables
- [ ] No weak algorithms (MD5, SHA1 for security)
- [ ] TLS enforced for all external connections
- [ ] Tokens signed with strong secret

### Injection Prevention (OWASP A05)
- [ ] No string concatenation in queries
- [ ] Parameterized queries used
- [ ] User input sanitized before use
- [ ] No `eval()`, `exec()`, or dynamic code execution

### Fail-Closed Patterns (OWASP A10)
- [ ] Auth errors → Deny access (not allow)
- [ ] Parsing failures → Reject input (not accept)
- [ ] No catch-all exception handlers that ignore errors
- [ ] Rate limiting on sensitive endpoints

---

## High-Risk Code Patterns

| Pattern | Risk | Look For |
|---------|------|----------|
| String concat in queries | Injection | `"SELECT * FROM " + user_input` |
| Dynamic code execution | RCE | `eval()`, `exec()`, `Function()` |
| Unsafe deserialization | RCE | `pickle.loads()`, `unserialize()` |
| Path manipulation | Traversal | User input in file paths |
| Disabled security | Various | `verify=False`, `--insecure` |

---

## Secret Detection Patterns

| Type | Indicators |
|------|-----------|
| API Keys | `api_key`, `apikey`, high entropy strings |
| Tokens | `token`, `bearer`, `jwt` |
| Credentials | `password`, `secret`, `key` |
| Cloud | `AWS_`, `AZURE_`, `GCP_` prefixes |

---

## Severity Classification

| Severity | Examples | Action |
|----------|----------|--------|
| **CRITICAL** | RCE, auth bypass, mass data exposure | Block commit |
| **HIGH** | Data exposure, privilege escalation | Block commit |
| **MEDIUM** | Limited scope, requires conditions | Review required |
| **LOW** | Informational, best practice | Log for later |

---

## Integration with CommitGate

The `src/control_plane/commit_gate.py` performs these checks programmatically:

1. **Pre-write validation** - Check eligibility
2. **Firewall validation** - Inter-agent trust
3. **Evidence integrity** - Source verification
4. **This security checklist** - OWASP compliance

> **Principle:** Fail-secure. On error, deny the commit.
