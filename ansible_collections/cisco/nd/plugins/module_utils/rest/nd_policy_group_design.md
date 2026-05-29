# `nd_policy` — Policy Groups Integration Design

## API Endpoints

| Operation | Individual Policies | Policy Groups |
|-----------|-------------------|---------------|
| List      | `GET .../policies` | `GET .../policyGroups` |
| Get by ID | `GET .../policies/{policyId}` | `GET .../policyGroups/{policyGroupId}` |
| Create    | `POST .../policies` (`{policies: [...]}`) | `POST .../policyGroups` (`{policyGroups: [...]}`) |
| Update    | `PUT .../policies/{policyId}` | `PUT .../policyGroups/{policyGroupId}` |
| Mark-delete | `POST .../policyActions/markDelete` | `POST .../policyGroups/actions/markDelete` |
| Push config | `POST .../policyActions/pushConfig` | **No group pushConfig endpoint** |
| Remove    | `POST .../policyActions/remove` | `POST .../policyGroups/actions/remove` |
| Delete    | `DELETE .../policies/{policyId}` | `DELETE .../policyGroups/{policyGroupId}` |

Individual policies use `switchId` (single string). Policy groups use `switchIds` (list of strings).

---

## Option A — Both `config` and `groups` in the Same Task

Both individual policies and policy groups can be provided in a **single task**. Two independent
pipelines execute sequentially within one module invocation.

### Argument Spec Changes

```
fabric_name:       str   (required)
state:             str   (merged | deleted | gathered)
deploy:            bool  (default: true)
use_desc_as_key:   bool  (default: false)
ticket_id:         str   (optional)
cluster_name:      str   (optional)
config:            list  (optional — individual policies, existing schema, unchanged)
groups:            raw   (optional — bool or list, default: None)
```

The `groups` parameter accepts two forms:

| Value | Meaning |
|-------|--------|
| Not provided / `None` | No group operations (default) |
| `true` | Gathered state: fetch all groups. Merged/deleted: ❌ rejected (need entries) |
| `false` | Same as not provided |
| `[...]` (list) | Operate on these specific policy groups |

Each entry in `groups:` list accepts:

```
name:                    str   (template name or POLICY-GROUP-xxxxx ID)
description:             str   (default: "")
priority:                int   (1–2000, default: 500)
create_additional_policy: bool (default: true)
template_inputs:         dict  (default: {})
switch:                  list  (required for merged; each element has serial_number)
```

### Return Values

```yaml
# For state: merged / deleted
changed: true/false
before:             # individual policies before
after:              # individual policies after
before_groups:      # policy groups before
after_groups:       # policy groups after

# For state: gathered
gathered:           # individual policies (playbook-ready format)
gathered_groups:    # policy groups (playbook-ready format)
```

---

### Examples

#### A.1 — Create individual policies only (unchanged behavior)

```yaml
- name: Create individual policies on switches
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    deploy: true
    config:
      - name: feature_enable
        description: "Enable LACP"
        create_additional_policy: false
        template_inputs:
          featureName: lacp

      - name: switch_freeform
        description: "Enable BFD"
        create_additional_policy: false
        template_inputs:
          CONF: |
            feature bfd

      - switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"
```

#### A.2 — Create policy groups only

```yaml
- name: Create policy groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    deploy: true
    groups:
      - name: feature_enable
        description: "Enable NX-API on all spines"
        priority: 500
        template_inputs:
          featureName: nxapi
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"
          - serial_number: "{{ switch3 }}"

      - name: switch_freeform
        description: "SNMP config for spines"
        priority: 500
        template_inputs:
          CONF: |
            snmp-server community public ro
            snmp-server contact ops@example.com
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch3 }}"
```

#### A.3 — Mixed: individual policies + per-switch overrides + groups (same task)

```yaml
# Result on the controller:
#
#   Individual policies:
#     switch1: feature_enable/lacp(500), switch_freeform/bfd(500), switch_freeform/ntp(101)
#     switch2: feature_enable/lacp(500), switch_freeform/bfd(500)
#     switch3: feature_enable/lacp(500), switch_freeform/bfd(999), feature_enable/lldp(300)
#                                              ↑ overridden priority         ↑ extra policy
#
#   Policy groups:
#     POLICY-GROUP-xxx: feature_enable/nxapi → [switch1, switch2, switch3]
#     POLICY-GROUP-yyy: switch_freeform/snmp → [switch1, switch3]

- name: Create individual policies and policy groups together
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    deploy: true

    config:
      # Globals — applied to every switch below
      - name: feature_enable
        description: "Enable LACP"
        create_additional_policy: false
        template_inputs:
          featureName: lacp

      - name: switch_freeform
        description: "Enable BFD"
        priority: 500
        create_additional_policy: false
        template_inputs:
          CONF: |
            feature bfd

      # Switch list + per-switch overrides
      - switch:
          - serial_number: "{{ switch1 }}"
            policies:
              - name: switch_freeform
                description: "NTP on switch1 only"
                priority: 101
                create_additional_policy: false
                template_inputs:
                  CONF: |
                    ntp server 10.1.1.1
          - serial_number: "{{ switch2 }}"
          - serial_number: "{{ switch3 }}"
            policies:
              - name: switch_freeform
                description: "BFD with higher priority for switch3"
                priority: 999
                create_additional_policy: false
                template_inputs:
                  CONF: |
                    feature bfd
              - name: feature_enable
                description: "LLDP on switch3 only"
                priority: 300
                create_additional_policy: false
                template_inputs:
                  featureName: lldp

    groups:
      - name: feature_enable
        description: "Enable NX-API on all spines"
        priority: 500
        template_inputs:
          featureName: nxapi
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"
          - serial_number: "{{ switch3 }}"

      - name: switch_freeform
        description: "SNMP config for spines"
        priority: 500
        template_inputs:
          CONF: |
            snmp-server community public ro
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch3 }}"
```

#### A.4 — Update a policy group by ID

```yaml
- name: Update policy group — add switch4 and change priority
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    deploy: true
    groups:
      - name: POLICY-GROUP-143310
        description: "Enable NX-API — updated"
        priority: 100
        template_inputs:
          featureName: nxapi
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"
          - serial_number: "{{ switch3 }}"
          - serial_number: "{{ switch4 }}"
```

#### A.5 — Update a policy group using description as key

```yaml
- name: Update policy group using description as key
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    use_desc_as_key: true
    state: merged
    deploy: true
    groups:
      - name: feature_enable
        description: "Enable NX-API on all spines"
        priority: 200
        template_inputs:
          featureName: nxapi
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"
          - serial_number: "{{ switch3 }}"
          - serial_number: "{{ switch4 }}"
```

#### A.6 — Delete policy groups by ID (full removal)

```yaml
- name: Delete specific policy groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: deleted
    deploy: true
    groups:
      - name: POLICY-GROUP-143310
      - name: POLICY-GROUP-143320
```

#### A.7 — Delete policy groups by template name

```yaml
# Deletes ALL policy groups on the fabric that use this template.
- name: Delete all feature_enable policy groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: deleted
    deploy: true
    groups:
      - name: feature_enable
```

#### A.8 — Delete policy groups using description as key

```yaml
- name: Delete policy groups using description as key
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    use_desc_as_key: true
    state: deleted
    deploy: true
    groups:
      - name: feature_enable
        description: "Enable NX-API on all spines"
```

#### A.9 — Mark-delete only (no deploy)

```yaml
- name: Mark policy groups for deletion (no deploy)
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: deleted
    deploy: false
    groups:
      - name: POLICY-GROUP-143310
      - name: POLICY-GROUP-143320
```

#### A.10 — Delete both individual policies AND policy groups (same task)

```yaml
- name: Delete individual policies and policy groups together
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: deleted
    deploy: true

    config:
      - name: feature_enable
      - name: switch_freeform
      - switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"

    groups:
      - name: POLICY-GROUP-143310
      - name: feature_enable
```

#### A.11 — Gather everything (individual policies + policy groups)

```yaml
# groups: true alongside state: gathered fetches both pipelines in one task
- name: Gather everything
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    groups: true
  register: full_export

# full_export.gathered        ← all individual policies
# full_export.gathered_groups ← all policy groups
```

#### A.12 — Gather with filters on both

```yaml
- name: Gather specific policies and groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    config:
      - name: feature_enable
      - switch:
          - serial_number: "{{ switch1 }}"
    groups:
      - name: feature_enable
  register: result

# result.gathered        ← matching individual policies
# result.gathered_groups ← matching policy groups
```

#### A.13 — Gather individual policies only (backward compatible default)

```yaml
# When groups is omitted, only individual policies are gathered (existing behavior)
- name: Gather all individual policies
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
  register: result

# result.gathered ← all individual policies
```

#### A.14 — Roundtrip: gather then re-apply

```yaml
- name: Gather from source fabric
  cisco.nd.nd_policy:
    fabric_name: "{{ source_fabric }}"
    state: gathered
    groups: true
  register: export

# Must map TWO return keys to TWO input parameters
- name: Re-create on target fabric
  cisco.nd.nd_policy:
    fabric_name: "{{ target_fabric }}"
    state: merged
    deploy: true
    config: "{{ export.gathered }}"
    groups: "{{ export.gathered_groups }}"
```

#### A.15 — Change control ticket

```yaml
- name: Create policy groups with change control
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    deploy: true
    ticket_id: "CHG-20260409-001"
    groups:
      - name: feature_enable
        description: "Enable LACP"
        template_inputs:
          featureName: lacp
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"
```

---

### Option A — Pros and Cons

| Pros | Cons |
|------|------|
| One task to express full desired state | **Partial failure**: individual pipeline succeeds, group pipeline fails → `changed: true` but task failed, controller in mixed state |
| Convenient for "I want everything in one place" | **`deploy: true` asymmetry**: pushConfig exists for individual policies but NOT for groups — same flag, different behavior |
| Single module name to learn | **`use_desc_as_key` dual scope**: applies to two different API namespaces, uniqueness checked independently |
| | `changed: true` doesn't tell you WHAT changed (individuals vs groups) |
| | Gathered roundtrip requires mapping two return keys (`gathered` + `gathered_groups`) to two input keys (`config` + `groups`) |
| | DOCUMENTATION nearly doubles — every option needs "for individuals X, for groups Y" caveats |
| | Testing matrix is combinatorial: 3 states × individual scenarios × group scenarios × mixed combinations |
| | Error messages must carry pipeline context ("failed in group pipeline" vs "failed in individual pipeline") |
| | Same template name in `config` + `groups` — no guardrail against accidental overlap |

---

## Option B — Single Module, Mutually Exclusive (`config` XOR `groups` per Task)

Both individual policies and policy groups are supported in the **same module**, but a single task
can use **either** `config` **or** `groups`, **never both**. Providing both fails immediately
at validation before any API calls.

### Argument Spec Changes

Same as Option A, with one added constraint:

```
fabric_name:       str   (required)
state:             str   (merged | deleted | gathered)
deploy:            bool  (default: true)
use_desc_as_key:   bool  (default: false)
ticket_id:         str   (optional)
cluster_name:      str   (optional)
config:            list  (optional — individual policies, existing schema, unchanged)
groups:            raw   (optional — bool or list, default: None)

# CONSTRAINT: config and groups are mutually exclusive for merged/deleted.
# Both can be provided together for gathered (read-only, no mutation risk).
```

The `groups` parameter accepts the same two forms as Option A (`true` or list).
Each entry in `groups:` list accepts (same as Option A):

```
name:                    str   (template name or POLICY-GROUP-xxxxx ID)
description:             str   (default: "")
priority:                int   (1–2000, default: 500)
create_additional_policy: bool (default: true)
template_inputs:         dict  (default: {})
switch:                  list  (required for merged; each element has serial_number)
```

### Validation Logic

```python
config = module.params.get("config")
groups = module.params.get("groups")

# For mutations: config and groups are mutually exclusive
if config and groups and state != "gathered":
    module.fail_json(
        msg="'config' and 'groups' are mutually exclusive for state='{0}'. "
            "Use separate tasks for individual policies and policy groups.".format(state)
    )

# groups: true is only valid for gathered (shorthand for "fetch all groups")
if groups is True and state != "gathered":
    module.fail_json(
        msg="'groups: true' is only valid for state='gathered'. "
            "For state='{0}', provide a list of group entries.".format(state)
    )

if not config and not groups and state != "gathered":
    module.fail_json(
        msg="Either 'config' or 'groups' is required for state='{0}'.".format(state)
    )
```

### Return Values

```yaml
# When config is active (individual policies):
changed: true/false
before: [...]           # individual policies before
after: [...]            # individual policies after
gathered: [...]         # for state=gathered

# When groups is active (policy groups):
changed: true/false
before: [...]           # policy groups before
after: [...]            # policy groups after
gathered_groups: [...]  # for state=gathered

# When both are gathered (state=gathered with config + groups: true):
gathered: [...]          # individual policies
gathered_groups: [...]   # policy groups
```

---

### Examples

> All group-only operations (create, update by ID, update by description, delete by ID,
> delete by template name, delete by description, mark-delete) are **identical** to Option A
> examples A.2 through A.9. Only the differences are shown below.

#### B.1 — REJECTED: both config and groups in same task

```yaml
# ❌ This FAILS immediately at validation — no API calls are made.

- name: This will fail
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    config:
      - name: feature_enable
        template_inputs:
          featureName: lacp
      - switch:
          - serial_number: "{{ switch1 }}"
    groups:
      - name: feature_enable
        template_inputs:
          featureName: nxapi
        switch:
          - serial_number: "{{ switch1 }}"

# Error: "'config' and 'groups' are mutually exclusive.
#         Use 'config' for individual per-switch policies,
#         or 'groups' for policy groups. Use separate tasks for both."
```

#### B.2 — Mixed: individual policies AND groups (separate tasks)

```yaml
# Task 1: Individual policies
- name: Create individual policies
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    deploy: true
    config:
      - name: feature_enable
        description: "Enable LACP"
        create_additional_policy: false
        template_inputs:
          featureName: lacp
      - switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"

# Task 2: Policy groups (separate task — cannot combine with config)
- name: Create policy groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: merged
    deploy: true
    groups:
      - name: feature_enable
        description: "Enable NX-API on all spines"
        template_inputs:
          featureName: nxapi
        switch:
          - serial_number: "{{ switch1 }}"
          - serial_number: "{{ switch2 }}"
          - serial_number: "{{ switch3 }}"
```

#### B.3 — Gathered: combined (convenience) and separate

Since `state: gathered` is read-only, the mutual exclusivity is relaxed — `groups: true`
can be used alongside `config` (or alone) to fetch both pipelines in a single task.

```yaml
# Combined gather — fetches both in one task
- name: Gather everything
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    groups: true
  register: everything

# everything.gathered        ← all individual policies
# everything.gathered_groups ← all policy groups
```

Alternatively, gather each type separately (consistent with B's per-task model):

```yaml
- name: Gather all individual policies
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
  register: individual_policies

- name: Gather all policy groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    groups: true
  register: policy_groups
```

#### B.4 — Roundtrip: gather → re-apply (split required)

> **Important:** Even when gathered output is produced in a single task, the re-apply
> **must** be split into separate tasks because `config` and `groups` are mutually
> exclusive for `state: merged`. The gathered output is not "single-task merged-ready."

```yaml
# Step 1: Gather both in one task
- name: Gather everything from source
  cisco.nd.nd_policy:
    fabric_name: "{{ source_fabric }}"
    state: gathered
    groups: true
  register: export

# Step 2: Re-apply as TWO separate tasks (mutually exclusive for mutations)
- name: Re-create individual policies on target
  cisco.nd.nd_policy:
    fabric_name: "{{ target_fabric }}"
    state: merged
    config: "{{ export.gathered }}"

- name: Re-create policy groups on target
  cisco.nd.nd_policy:
    fabric_name: "{{ target_fabric }}"
    state: merged
    groups: "{{ export.gathered_groups }}"
```

> **Why the asymmetry?** Gathering is read-only — combining both pipelines carries
> zero risk. Mutations are not — combining them would reintroduce partial-failure
> risk, deploy asymmetry, and ambiguous `changed` flags (the exact cons that
> Option B is designed to avoid). So we relax the constraint for reads but
> enforce it for writes.

---

### Option B — Pros and Cons

| Pros | Cons |
|------|------|
| **No partial failure risk** — only one pipeline runs per task | Mixed scenarios require two tasks instead of one |
| **No `deploy` asymmetry** — when groups active, deploy means group semantics only | `nd_policy_resources.py` grows to handle both codepaths |
| **`use_desc_as_key` unambiguous** — applies to exactly one namespace per task | Documentation still grows (but structured as two clean sections) |
| **`changed` flag is unambiguous** — refers to exactly one resource type | User must know `groups:` parameter exists |
| **`gathered` can combine both** — one task to fetch everything | Gathered roundtrip is asymmetric: 1 task to gather, 2 tasks to re-apply |
| **`groups: true` for gathered** — intuitive, gathers both in one task | |
| **Zero changes to existing individual policy codepath** | |
| **Testing: no mixed-mode combinations** — each state tested per-mode | |
| **Backward compatible** — existing playbooks work unchanged | |
| Same module name — single import, single docs page | |

---

## Enhancement: `scope` Parameter for Gathered State

With `scope`, the `groups: true` bool shorthand is no longer needed. The `groups`
parameter becomes strictly a **list** (for filtered operations), and `scope` handles
the "what to gather" question explicitly. This eliminates the `type="raw"` complexity
and all bool-vs-list inference rules.

### Argument Spec (with `scope`)

```
groups:  list   (optional — list of group entries for merged/deleted/gathered-with-filter)
scope:   str    (optional — "policies" | "groups" | "all", default: "policies")
                Only valid for state: gathered. Rejected for merged/deleted.
```

> **Key simplification:** `groups` is always a list, never a bool. `scope` replaces
> `groups: true` entirely. No `type="raw"`, no bool detection, no dual-meaning parameter.

### Behavior Matrix

| `config` | `groups` | `scope` | What gets gathered |
|----------|----------|---------|-------------------|
| omitted  | omitted  | omitted | All individual policies (backward compatible default) |
| omitted  | omitted  | `policies` | All individual policies (explicit, same as default) |
| omitted  | omitted  | `groups` | All policy groups |
| omitted  | omitted  | `all` | All individual policies + all policy groups |
| provided | omitted  | omitted | Filtered individual policies (existing behavior) |
| provided | omitted  | `policies` | Filtered individual policies (explicit) |
| omitted  | provided | omitted | Filtered policy groups (scope inferred from `groups` presence) |
| omitted  | provided | `groups` | Filtered policy groups (explicit) |
| provided | provided | `all` | Filtered individuals + filtered groups |

### Validation

```python
scope = module.params.get("scope")
config = module.params.get("config")
groups = module.params.get("groups")

if scope and state != "gathered":
    module.fail_json(
        msg="'scope' is only valid for state='gathered', not state='{0}'.".format(state)
    )

# Reject contradictions: scope says one pipeline but filter provided for the other
if scope == "policies" and groups:
    module.fail_json(
        msg="scope='policies' but 'groups' filter provided. "
            "Use scope='all' or scope='groups' instead."
    )
if scope == "groups" and config:
    module.fail_json(
        msg="scope='groups' but 'config' filter provided. "
            "Use scope='all' or scope='policies' instead."
    )
```

### Examples

```yaml
# Gather only policy groups — explicit, no ambiguity
- name: Gather all policy groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    scope: groups
  register: group_export

# group_export.gathered_groups ← all policy groups
# group_export.gathered        ← absent / empty (not requested)

# Gather only individual policies — explicit
- name: Gather all individual policies
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    scope: policies
  register: policy_export

# policy_export.gathered ← all individual policies

# Gather everything — explicit
- name: Gather everything
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    scope: all
  register: everything

# everything.gathered        ← all individual policies
# everything.gathered_groups ← all policy groups

# Scope with filters — scope controls which pipelines run,
# config/groups list provides the filters within that pipeline
- name: Gather filtered groups only
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    scope: groups
    groups:
      - name: feature_enable
  register: result

# result.gathered_groups ← only feature_enable groups

# Gather filtered individuals + all groups
- name: Gather specific policies and all groups
  cisco.nd.nd_policy:
    fabric_name: "{{ fabric_name }}"
    state: gathered
    scope: all
    config:
      - name: feature_enable
      - switch:
          - serial_number: "{{ switch1 }}"
  register: result

# result.gathered        ← matching individual policies only
# result.gathered_groups ← all policy groups (no groups filter → all)
```

### What This Replaces

| Before (`groups: true`) | After (`scope`) |
|-------------------------|-----------------|
| `groups: true` + `state: gathered` | `scope: groups` or `scope: all` |
| `groups` type = `raw` (bool or list) | `groups` type = `list` (always) |
| `groups is True and state != "gathered"` → reject | Not needed — `groups` is always a list |
| "does `groups: true` mean groups-only or both?" | `scope: groups` = groups-only, `scope: all` = both |

### When `scope` Conflicts with `config`/`groups`

| Scenario | Behavior |
|----------|----------|
| `scope: policies` + `groups: [list]` | ❌ Rejected — scope says "policies only" but groups filter provided |
| `scope: groups` + `config: [list]` | ❌ Rejected — scope says "groups only" but config filter provided |
| `scope: all` + `config: [list]` + `groups: [list]` | ✅ OK — filter both pipelines |
| `scope: all` + no config + no groups | ✅ OK — fetch everything unfiltered |
| `scope: policies` + `config: [list]` | ✅ OK — filter individuals only |
| `scope: groups` + `groups: [list]` | ✅ OK — filter groups only |

### Trade-offs

| Pros | Cons |
|------|------|
| **`groups` is always a list** — no `type="raw"`, no bool detection | One more parameter to learn |
| **Unambiguous** — `scope` says exactly what to gather | Adds validation (scope × config × groups conflicts) |
| **No inference rules** — no "groups: true means X in this state" | |
| **Backward compatible** — omitting `scope` defaults to `policies` (existing behavior) | |
| Works identically in both Option A and Option B | |

---

## Comparison Summary

| Criteria | Option A (both in same task) | Option B (mutually exclusive) |
|----------|:---:|:---:|
| Partial failure risk | ❌ Yes — two pipelines, one can fail | ✅ No — one pipeline per task |
| `deploy: true` semantics | ❌ Asymmetric (pushConfig exists for individuals, not groups) | ✅ Clear — deploy means one thing per task |
| `use_desc_as_key` scope | ❌ Two namespaces under one flag | ✅ One namespace per task |
| `changed` clarity | ❌ Ambiguous | ✅ Unambiguous |
| Roundtrip simplicity | ✅ Gather 1 task → re-apply 1 task (symmetric) | ⚠️ Gather 1 task → re-apply 2 tasks (asymmetric) |
| Express full state in one task | ✅ Yes | ⚠️ Two tasks for mutations, one task for gathered |
| Backward compatibility | ✅ | ✅ |
| Existing code impact | Medium (two pipelines in manage_state) | Low (clean branch at top of manage_state) |
| Testing complexity | High (combinatorial) | Medium (additive) |
| Documentation size | Large (dual explanations everywhere) | Medium (two clean sections) |
