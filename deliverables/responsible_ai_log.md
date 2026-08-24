# Responsible AI Evaluation Log

## Purpose

This document records how the AI diagnosis part of NetSage AI was evaluated.

NetSage AI is not designed to let an AI model make network changes on its own. The deterministic rule checker runs first, Gemini is used to explain and prioritize the findings, and a human reviews the result before it is treated as the final recommendation.

The main purpose of this evaluation was to check whether the Gemini response stayed consistent with the case evidence and the deterministic findings, and to record situations where human review found a meaningful problem.

The evaluation was carried out using the 30 cases in the project's authoritative dataset.

---

## Evaluation Approach

Each case was processed through the normal application workflow:

1. The case and its Cisco/networking evidence were loaded.
2. The deterministic rule checker was run.
3. The deterministic findings were reviewed as the grounded first-pass result.
4. Gemini was used to generate the structured diagnosis.
5. The Gemini response was compared with the original case evidence and deterministic finding.
6. The response was classified as acceptable or requiring human intervention.
7. When a meaningful issue was found, the correction and reason were recorded.

The review looked at:

- Root cause
- Evidence used by the AI
- OSI layer
- Confidence
- Next diagnostic command
- Suggested fix
- Agreement with the deterministic finding
- Whether the response matched the selected case
- Whether the AI introduced assumptions not supported by the evidence
- Whether the suggested diagnostic action was appropriate

Small differences in wording were not treated as failures. An intervention was recorded only when the issue was technically meaningful or could reasonably lead a user toward an incorrect diagnosis or action.

---

## Deterministic Evaluation Result

Before reviewing the AI responses, the deterministic checker was run against all 30 cases.

| Measure | Result |
|---|---:|
| Total cases | 30 |
| Correct deterministic detections | 30 |
| Missed cases | 0 |
| Mismatched cases | 0 |
| Deterministic accuracy | 100.0% |

This result applies specifically to the 30 cases in the project's evaluation dataset. It should not be interpreted as 100% accuracy for arbitrary real-world network configurations.

The deterministic and AI evaluations are separate. The deterministic layer provides the initial grounded finding, while Gemini provides explanation and synthesis around that finding.

---

## AI Review Result

All 30 cases were also reviewed after generating a Gemini diagnosis.

| Review outcome | Cases | Percentage |
|---|---:|---:|
| Accepted without significant correction | 26 | 86.7% |
| Required meaningful human intervention | 4 | 13.3% |
| Total evaluated | 30 | 100% |

The 86.7% figure is **not a formal model accuracy score**. It comes from a practical review of one fixed 30-case project dataset. It was not a blinded statistical benchmark.

The more useful result is the type of problems found during review. The AI was generally useful for explaining the deterministic findings, but the four intervention cases showed that a technically plausible response can still contain an unsuitable fix, unsupported assumptions, a case-grounding error, or an inappropriate diagnostic command.

---

# Cases Requiring Human Intervention

## NET-002 — Incorrect DHCP Remediation

### Expected fault

DHCP scope/pool exhaustion.

### Deterministic finding

The deterministic checker correctly identified that the DHCP address pool was exhausted.

### What Gemini returned

Gemini correctly identified DHCP pool exhaustion and explained that all available addresses were already leased.

The problem was in the suggested remediation. The response suggested using an excluded address range as a way to reclaim unused addresses.

### Problem found

An excluded address range does not reclaim addresses that are already leased. Adding exclusions would actually reduce the number of addresses available from the pool.

The root-cause diagnosis was therefore useful, but part of the recommended fix was technically unsuitable.

### Human review

The remediation was flagged for correction. A better approach is to first verify why the pool is exhausted and then decide whether the address pool needs to be expanded or otherwise reconfigured based on the actual network requirements.

### What this showed

A correct root-cause diagnosis does not automatically mean that every remediation step produced by the AI is correct.

---

## NET-004 — Diagnosis from the Wrong Case

### Expected fault

OSPF hello timer mismatch.

### Deterministic finding

The deterministic checker correctly identified an OSPF hello/dead timer mismatch.

### What Gemini returned

Gemini returned a diagnosis about:

```text
GigabitEthernet0/0.10
```

being administratively shut down.

That diagnosis belonged to a different troubleshooting scenario rather than the selected NET-004 case.

### Problem found

The response was not grounded in the selected case. As a result, the root cause, evidence, diagnostic command, and suggested fix did not address the OSPF timer mismatch being evaluated.

### Human review

The diagnosis was rejected rather than edited field-by-field because the response was fundamentally associated with the wrong scenario.

### What this showed

An answer can be technically valid in isolation and still be completely wrong if it is based on the wrong case or evidence.

This is one of the reasons the application keeps the selected case and deterministic findings visible during review.

---

## NET-007 — Remediation Went Beyond the Supplied Evidence

### Expected fault

Overly permissive ACL on the Guest VLAN.

### Deterministic finding

The deterministic checker identified an ACL rule allowing traffic from the Guest VLAN to any destination.

### What Gemini returned

Gemini correctly recognized the security problem and explained that guest traffic could reach internal networks.

However, the suggested fix went further and proposed:

- Blocking RFC 1918 ranges
- Explicitly permitting internet-bound traffic
- Explicitly permitting services such as DHCP and DNS

### Problem found

The supplied case established that the Guest VLAN ACL was too permissive. It did not establish the complete network security policy or prove that all RFC 1918 ranges should be blocked.

The AI therefore introduced configuration assumptions that were not directly supported by the evidence.

### Human review

The remediation was refined to be policy-driven:

1. Review the intended Guest VLAN access policy.
2. Identify the internal networks that guests must not reach.
3. Modify the ACL to deny access to those protected networks.
4. Permit only the traffic required by the documented policy.
5. Verify the resulting ACL.

### What this showed

The AI can correctly identify a fault while still making assumptions about how the network should be configured.

The final policy decision has to remain with the network administrator.

---

## NET-018 — Inappropriate Diagnostic Command

### Expected fault

RADIUS shared secret mismatch.

### Deterministic finding

The deterministic checker identified a RADIUS shared secret mismatch.

### What Gemini returned

Gemini correctly identified the shared secret mismatch and recommended correcting the RADIUS configuration.

However, it suggested:

```text
test aaa group radius user password
```

as the next diagnostic command.

### Problem found

The command contains placeholder credentials and performs an authentication test rather than directly inspecting the relevant RADIUS configuration.

For this case, a read-only inspection of the RADIUS configuration is a more appropriate next step.

### Human correction

The diagnostic command was changed to:

```text
show running-config | section radius
```

This allows the reviewer to inspect the relevant configuration without attempting an authentication operation.

### What this showed

Even when the root cause is correct, the next diagnostic action still needs to be checked for relevance, safety, and suitability for the actual environment.

---

# Accepted Cases

Not every Gemini response required intervention.

The remaining 26 cases were reviewed as acceptable for the purposes of this project:

- NET-001 — Administratively down sub-interface
- NET-003 — DNS resolution disabled/misconfigured
- NET-005 — ACL blocking HTTP traffic
- NET-006 — Missing NAT overload/PAT
- NET-008 — VLAN missing from trunk allowed list
- NET-009 — Incorrect host default gateway
- NET-010 — Management SVI shutdown
- NET-011 — Inter-switch link configured as access
- NET-012 — OSPF passive interface on active link
- NET-013 — Wrong access VLAN
- NET-014 — Missing DHCP relay helper address
- NET-015 — Unreachable static-route next hop
- NET-016 — Missing FTP control-port permit
- NET-017 — Missing NAT inside direction
- NET-019 — Native VLAN mismatch
- NET-020 — Gateway outside host subnet
- NET-021 — Missing OSPF redistribution `subnets` keyword
- NET-022 — ACL blocking HTTPS
- NET-023 — Duplicate IP address
- NET-024 — VTP domain mismatch
- NET-025 — DAI trust missing on uplink
- NET-026 — Port-security violation
- NET-027 — HSRP timer mismatch
- NET-028 — Missing 802.1Q encapsulation
- NET-029 — IPv6 Router Advertisements suppressed
- NET-030 — CDP disabled globally

These cases are useful as a control group. The review did not assume that an AI response was wrong simply because it came from Gemini.

---

# Main AI Failure Patterns

The four intervention cases fall into a few clear categories.

## 1. Remediation accuracy

NET-002 showed that the model can identify the correct fault but still suggest a configuration change that is not appropriate.

This means the root cause and the proposed fix need to be reviewed separately.

## 2. Case and evidence grounding

NET-004 showed that the model can produce a technically plausible answer that belongs to another scenario.

The response therefore has to be checked against the actual selected case, not just judged on whether the networking explanation sounds correct.

## 3. Unsupported assumptions

NET-007 showed that the model can apply general networking knowledge beyond what the supplied evidence establishes.

A human still needs to confirm the actual network policy before accepting a configuration recommendation.

## 4. Diagnostic-command suitability

NET-018 showed that a command can be related to the problem without necessarily being the best next diagnostic step.

A recommended command should be checked for:

- Relevance to the fault
- Read-only suitability where required
- Cisco IOS/platform compatibility
- Whether it depends on information that was not supplied
- Whether it could have an operational side effect

---

# Why Human Review Is Necessary

The evaluation is one of the main reasons NetSage AI uses a human-in-the-loop design.

The deterministic checker provides a grounded first-pass signal, but the AI layer can still make mistakes in:

- Interpretation
- Case association
- Explanation
- Diagnostic commands
- Remediation steps
- Assumptions about network policy

For this reason, the application requires the reviewer to choose one of three actions:

- **Approve**
- **Edit**
- **Reject**

A diagnosis is not considered final until one of these review actions has been completed.

The application also never executes Cisco configuration commands automatically. It only displays recommendations for a human to evaluate and apply if appropriate.

---

# Relationship Between the Deterministic Checker and AI

The evaluation also shows why NetSage AI uses both deterministic checks and AI instead of relying on an LLM alone.

The deterministic checker correctly identified the expected fault in all 30 evaluation cases.

When the AI response needed correction, the deterministic finding remained available to the reviewer as a reference point.

The workflow can therefore be thought of as:

```text
Case evidence
      |
      v
Deterministic checker
      |
      v
Grounded finding
      |
      +--------------------+
      |                    |
      v                    v
   AI diagnosis       Human can inspect
      |              deterministic evidence
      v                    |
      +---------+----------+
                |
                v
         Human review
        /      |       \
   Approve    Edit    Reject
```

This separation is important because it gives the reviewer something concrete to compare the AI response against.

---

# Prompt and Grounding Controls

The diagnosis prompt places several restrictions on the AI output.

Gemini is instructed to:

- Use only the supplied symptom, topology note, Cisco evidence, and deterministic findings.
- Treat deterministic findings as strong evidence.
- Separate evidence from inference.
- Provide a confidence score.
- Provide exactly one practical diagnostic command.
- Give concrete fix steps without claiming that they were executed.
- State uncertainty in `caveats` when the evidence is incomplete.
- Return the required structured JSON format.

The deterministic checker also runs before the AI request. This means Gemini is not asked to diagnose the network from a blank prompt; it receives the structured findings produced by the application.

These controls do not guarantee a correct response, but they make the output easier to review and give the human reviewer a clear evidence trail.

---

# Human-in-the-Loop Controls

Every diagnosis goes through the review section in the application.

### Approve

The reviewer accepts the diagnosis as presented.

### Edit

The reviewer changes the diagnosis where necessary. The application keeps the original diagnosis as well as the edited version.

### Reject

The reviewer rejects the diagnosis and provides a reason.

No configuration command is automatically executed after any of these actions.

This is important because the system is intended to support a network engineer or student, not replace their judgment.

---

# Failure Handling

The AI layer is not required for the application to remain usable.

If Gemini is not configured, the application produces a deterministic-only diagnosis.

If a Gemini request fails because of a timeout, authentication problem, network issue, or provider error, the application falls back to the deterministic result.

If Gemini returns malformed JSON, the application attempts to recover and validate the response. If it still cannot be validated, the deterministic diagnosis is used instead.

This means an AI-provider failure does not prevent the troubleshooting application from producing a useful first-pass result.

---

# Audit Trail

Human review decisions are stored in the append-only audit log:

```text
outputs/audit_log.jsonl
```

The audit record contains information such as:

- Case ID
- Symptom
- Deterministic findings
- Generated diagnosis
- Human action
- Edited diagnosis, when applicable
- Rejection reason, when applicable
- Confidence
- AI provider

For edited responses, the original and edited diagnoses can be compared. For rejected responses, the reviewer's reason is retained.

This makes it possible to look back at previous decisions and identify recurring problems in either the deterministic rules or the AI layer.

---

# Limitations of the Evaluation

## Fixed dataset

The evaluation uses the project's 30 supplied cases. It does not show how the system performs on arbitrary real-world Cisco configurations.

## Limited sample size

Thirty cases are useful for a project evaluation, but they are not enough to make broad statistical claims about model reliability.

## Single evaluation run

The results reflect the Gemini responses observed during this evaluation. Model behavior can change between runs or model versions.

## No formal blinded study

This was a practical engineering evaluation rather than a controlled study involving multiple independent reviewers.

## Human classification

The decision about whether an AI response needed intervention was based on manual technical review. Another reviewer could reasonably disagree about a borderline case.

## Deterministic checker scope

The 100% deterministic result applies to the supplied 30-case dataset. It should not be interpreted as 100% accuracy for general network troubleshooting.

## External AI dependency

Gemini is an external service. Availability, rate limits, model behavior, and provider-side changes can affect the AI diagnosis layer.

---

# Audit and Future Improvement

The intervention cases are useful beyond this evaluation. They can be used to improve the system over time.

For example:

- Repeated remediation mistakes can lead to changes in the diagnosis prompt.
- Repeated unsupported recommendations can lead to stricter evidence-grounding rules.
- Repeated case-matching problems can lead to clearer case identifiers and context in the AI request.
- Repeated diagnostic-command issues can lead to a small catalogue of validated read-only commands.
- Repeated deterministic misses in future cases can be used to add or improve rules in `src/checker.py`.

The aim is not simply to make the AI produce more answers. The aim is to make the complete troubleshooting process easier to verify and more reliable.

---

# Overall Conclusion

The evaluation supports the basic architecture used by NetSage AI.

The deterministic checker correctly identified the expected fault in all 30 cases in the supplied evaluation dataset. Gemini was generally useful for turning those findings into readable, structured diagnoses, but the review also found four cases where human intervention was necessary.

The four intervention types were:

1. Incorrect remediation
2. Incorrect case grounding
3. Unsupported remediation assumptions
4. Inappropriate diagnostic action

These cases reinforce the main design principle of the project:

> **The AI recommends, the deterministic checker provides grounded evidence, and a human makes the final decision.**

For that reason, NetSage AI is deliberately built as a decision-support tool rather than an autonomous network configuration system.
