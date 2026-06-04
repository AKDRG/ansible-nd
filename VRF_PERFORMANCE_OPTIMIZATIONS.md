# `dcnm_vrf` Performance Optimization Plan

**Date:** April 16, 2026
**Scope:** `plugins/modules/dcnm_vrf.py`, `plugins/action/dcnm_vrf.py`
**Reference:** README copy.md / README copy 2.md — dcnm_network optimization history

---

## Background

The `dcnm_network` module underwent a series of targeted performance fixes that reduced
idempotent run time from **140s → 8s** for small playbooks and from **108s → 12s** for
large 200-network playbooks. The `dcnm_vrf` module has the identical structural
bottlenecks and has not yet received those fixes. This document catalogs every
optimization identified, split into what can be implemented now versus what should be
deferred, sorted within each group by expected performance gain descending and code risk
ascending.

---

## Part 1 — Implementable Now

Sorted by: **performance improvement (highest first)**, then **risk (lowest first)** within
the same performance band.

---

### OPT-01 — Targeted `get_have()` for `merged` and `replaced`

**Performance impact:** Very High — expected 10–20× speedup for small targeted playbooks
(mirrors dcnm_network: 140s → 8s).
**Code risk:** Medium (new branch in `get_have()`; existing path untouched).

**Problem:**
`get_have()` always calls `GET_VRF` for every VRF on the fabric, builds a
comma-separated string of all VRF names, then calls `GET_VRF_ATTACH` for all of them.
On a fabric with 200 VRFs, a playbook managing 4 VRFs fetches 200 VRF records and a
bulk attachment payload for all 200. Runtime scales with total fabric size, not with
the number of VRFs the playbook manages.

```python
# Current (always full-fabric sweep)
vrf_objects = self.get_vrf_objects()          # GET all VRFs
for vrf in vrf_objects["DATA"]:
    curr_vrfs += vrf["vrfName"] + ","
vrf_attach_objects = dcnm_get_url(            # GET attachments for ALL VRFs
    self.module, self.fabric,
    self.paths["GET_VRF_ATTACH"],
    curr_vrfs[:-1], "vrfs"
)
```

**Fix:**
Add a fast path activated when `state in ["merged", "replaced"]` and `self.config` is
present:

1. Call `GET_VRF` once to get all VRF objects (needed for validation).
2. Filter the returned list to only those VRFs named in `self.config`.
3. Build `curr_vrfs` from only those requested VRF names.
4. Call `GET_VRF_ATTACH` with only those names.
5. The full-fabric path is preserved unchanged for all other states.

**Why safe:**
`merged` and `replaced` only need controller state for VRFs named in the playbook.
They do not need a full-fabric inventory to compute diffs.

---

### OPT-02 — Targeted `get_have()` for `deleted` with Explicit `config`

**Performance impact:** Very High — dcnm_network showed 458s → 27s for a 4-network
targeted delete run.
**Code risk:** Medium (new branch; full-fabric delete without config unchanged).

**Problem:**
Same as OPT-01 but for `state: deleted`. Even when deleting 4 named VRFs, the full-
fabric sweep runs. On a fabric with 412 VRFs `dcnm_network` generated 412 individual
GET requests before the fix.

**Fix:**
Extend the fast path to `state == "deleted"` when `self.config` is present:
- Fetch and filter only named VRFs.
- Fetch `GET_VRF_ATTACH` only for the named VRFs.

When `state == "deleted"` and `self.config` is absent (delete everything), retain the
existing full-fabric sweep without any change.

**Why safe:**
Full-fabric delete is explicitly triggered by omitting `config`. Targeted delete only
needs state for named VRFs.

---

### OPT-03 — Build `have_create` and `have_attach` as Dicts for O(1) Lookups

**Performance impact:** Medium — eliminates O(n²) nested-loop patterns in all diff
methods.
**Code risk:** Low (additive-only; existing list structures kept for compatibility).

**Problem:**
`have_create` and `have_attach` are plain lists. Every lookup in `diff_merge_create()`,
`diff_merge_attach()`, `get_diff_replace()`, `get_diff_delete()`, and
`get_diff_override()` calls `find_dict_in_list_by_key_value()` which is an O(n) linear
scan. These are called inside loops over `want_create` and `want_attach`, producing
O(n²) behavior on large VRF counts.

```python
# Current O(n) lookup inside an O(n) loop → O(n²)
for want_c in self.want_create:
    for have_c in self.have_create:   # linear scan
        if want_c["vrfName"] == have_c["vrfName"]:
            ...
```

**Fix:**
After `get_have()` populates the lists, build auxiliary dicts immediately:

```python
self.have_create_by_name = {v["vrfName"]: v for v in self.have_create}
self.have_attach_by_name = {a["vrfName"]: a for a in self.have_attach}
```

Replace all `find_dict_in_list_by_key_value(search=self.have_create, ...)` calls with
direct `self.have_create_by_name.get(name)` lookups in the diff methods.

---

### OPT-04 — Bulk Attachment Fetch in `get_diff_query()` When Config Present

**Performance impact:** Medium — changes O(n) sequential API calls to O(1) for the
query-with-config path.
**Code risk:** Low (isolated to `get_diff_query()`).

**Problem:**
When `self.config` is specified, `get_diff_query()` fetches attachments per-VRF inside
a loop:

```python
for want_c in self.want_create:
    for vrf in vrf_objects["DATA"]:
        if want_c["vrfName"] == vrf["vrfName"]:
            path = self.paths["GET_VRF_ATTACH"].format(
                self.fabric, vrf["vrfName"]
            )
            vrf_attach_objects = dcnm_send(...)   # one call per VRF
```

**Fix:**
Before the loop, build a comma-separated string of all wanted VRF names and make a
single `GET_VRF_ATTACH` call. Store results in a dict by VRF name for O(1) access
inside the loop. This is exactly what `get_have()` already does.

---

### OPT-05 — Bulk Attachment Fetch in `get_diff_query()` When No Config (Query All)

**Performance impact:** Medium — changes O(n) sequential calls to O(1) for full-fabric
query.
**Code risk:** Low (isolated to the `else` branch of `get_diff_query()`).

**Problem:**
The `else` branch (query all VRFs without config) also issues one `GET_VRF_ATTACH`
call per VRF:

```python
for vrf in vrf_objects["DATA"]:
    path = self.paths["GET_VRF_ATTACH"].format(self.fabric, vrf["vrfName"])
    vrf_attach_objects = dcnm_send(...)   # one call per VRF
```

**Fix:**
Build a single comma-separated string of all VRF names from `vrf_objects["DATA"]` and
issue one bulk `GET_VRF_ATTACH` call before the loop. Distribute results by VRF name
inside the loop.

---

### OPT-06 — `wait_for_vrf_del_ready()` — Initial Parallel Poll Pass

**Performance impact:** Medium — dcnm_network saved one full poll cycle for
`deploy: false` cases (reduced from 8 to 4 status polls per run).
**Code risk:** Low (additive logic before the existing loop).

**Problem:**
`wait_for_vrf_del_ready()` processes VRFs sequentially. For the first VRF, it blocks in
a `while` loop until that VRF reaches `NA` state before it even starts checking the
next VRF. VRFs that are already in `NA` state are still serialized behind the wait.

**Fix:**
Add an initial scan pass before the main polling loop:

1. Poll all VRFs in `diff_delete` once.
2. For any VRF already in `NA` state, mark it as ready and skip it in the main loop.
3. For any VRF in `OUT-OF-SYNC` or `FAILED`, mark it immediately.
4. Only enter the `while` wait loop for VRFs that actually need waiting.

This directly mirrors the "reuse first `wait_for_del_ready()` result" micro-optimization
documented in the README.

---

### OPT-07 — Remove `inspect.stack()` from Hot Loops

**Performance impact:** Medium — `inspect.stack()` walks the entire Python call stack
and is called at the top of nearly every method, including those invoked inside tight
inner loops.
**Code risk:** Low (logging-only change; no functional impact).

**Problem:**
Almost every method begins with:

```python
caller = inspect.stack()[1][3]
method_name = inspect.stack()[0][3]
```

`inspect.stack()` is expensive. It is called inside `diff_for_attach_deploy()`,
`diff_merge_create()`, `update_attach_params()`, `dict_values_differ()`, and all
attachment-processing loops — some of which are called O(switches × VRFs) times per
task run.

**Fix:**
- Replace `method_name = inspect.stack()[0][3]` with a hardcoded string constant
  (`method_name = "diff_for_attach_deploy"`) in all hot-path methods.
- Remove `caller = inspect.stack()[1][3]` entirely from methods that are called inside
  loops; it is only useful in error messages in `fail_json()` calls.
- Retain `inspect.stack()` in `failure()`, `fail_json()` call sites, and top-level
  entry methods where the debugging value is genuine.

---

### OPT-08 — Consistently Skip VRF-Lite API Calls in `get_have()`

**Performance impact:** Medium where VRF-Lite is absent (saves one `GET_VRF_SWITCH`
call per switch per VRF); zero impact when VRF-Lite is actively used.
**Code risk:** Low (`_has_vrf_lite_in_config()` already exists).

**Problem:**
`_has_vrf_lite_in_config()` is only called in some code paths in `get_have()`. Audit
all attachment-processing loops in `get_have()` to confirm every path that could invoke
`get_vrf_lite_objects()` has the guard check. Each `get_vrf_lite_objects()` call issues
a `GET_VRF_SWITCH` API request (one per switch per VRF), which is expensive on fabrics
where VRF-Lite is not in use.

**Specific check:**
Verify the guard at the attachment-processing loop in `get_have()` covers every
iteration path, including attachments encountered via the targeted fast path added for
OPT-01 and OPT-02.

---

### OPT-09 — Deduplicate `all_vrfs` Lists Using Sets

**Performance impact:** Low — prevents duplicate VRF names in `vrfNames` deploy
payloads, which can cause redundant deploy operations on the controller.
**Code risk:** Low (purely additive change).

**Problem:**
`all_vrfs` lists are built with `.append()` in `diff_merge_attach()`,
`get_diff_replace()`, and `get_diff_override()`. If a VRF appears in both the replace
diff and the attach diff, it can be appended multiple times, causing the controller to
receive a `vrfNames` string with the same VRF listed twice.

**Fix:**
```python
# Before join, deduplicate:
vrf_names = ",".join(sorted(set(all_vrfs)))
```

---

### OPT-10 — Avoid Double Fabric Discovery API Calls in Action Plugin

**Performance impact:** Low-Medium — saves 1–2 API calls at the start of every task
run in non-federated environments.
**Code risk:** Low (logic change in `run()` only).

**Problem:**
In `run()`, the fabric discovery can make up to 3 API calls:
1. `obtain_federated_fabric_associations()` — always called first.
2. `obtain_fabric_associations()` — called if federated returns "no federation manager".
3. `obtain_fabric_associations()` — called again if MCFG detection fails on result of #1.

In a non-federated environment (standalone or MSD), calls #1 and #2 are always both
made. In a federated environment where MCFG detection fails, all three are made.

**Fix:**
Cache the result of `obtain_fabric_associations()` so it is only fetched once regardless
of how many detection branches are taken:

```python
msd_fabric_data = None   # lazy-loaded cache

def get_msd_associations():
    nonlocal msd_fabric_data
    if msd_fabric_data is None:
        msd_fabric_data = obtain_fabric_associations(self, task_vars, tmp)
    return msd_fabric_data
```

---

## Part 2 — Pending / Deferred

Sorted by: **performance improvement (highest first)**, then **risk (lowest first)** within
the same performance band. These items are deferred due to higher complexity, dependency
on Part 1 completions, or requiring additional design decisions.

---

### PENDING-01 — Hybrid Bulk Threshold for Large `merged` and `replaced`

**Performance impact:** High — dcnm_network dropped from 108s → 12s for a 205-network
`state: replaced` playbook.
**Reason deferred:** Depends on OPT-01 being implemented first. Adding a threshold on
top of the targeted fast path is a follow-up step.

**Description:**
The targeted fast path from OPT-01 fetches named VRFs individually. When a playbook
lists 200 VRFs, this still produces 200 individual GET requests. The hybrid approach
adds a threshold:

- If `len(config) < BULK_GET_HAVE_VRF_THRESHOLD` (e.g., 25): use targeted named
  lookups (OPT-01 path).
- If `len(config) >= BULK_GET_HAVE_VRF_THRESHOLD`: use one bulk `GET_VRF` + local
  filtering, same as the full-fabric path but without blindly including unrelated VRFs
  in the attachment fetch.

The threshold should be a named constant:
```python
BULK_GET_HAVE_VRF_THRESHOLD = 25
```

**Dependency:** OPT-01 must be merged first.

---

### PENDING-02 — Parallelize Child Fabric Task Execution in Action Plugin

**Performance impact:** Medium — for parent fabrics with 3+ child fabrics, child tasks
currently run serially. Parallelization would reduce wall-clock time proportionally to
the number of children.
**Reason deferred:** High complexity; requires thread-safety audit of `self._task`,
`self._connection`, and shared Ansible connection state. Needs explicit Ansible version
compatibility check.

**Description:**
Child tasks in `handle_parent_workflow()` are executed sequentially:

```python
for child_task in child_tasks_dict.values():
    child_result = self.execute_child_task(child_task, task_vars, tmp)
    child_results.append(child_result)
    if child_result.get("failed", False):
        break
```

Each child task is an independent `_execute_module()` call to a different fabric. They
have no inter-dependencies (VRF IDs are assigned by the parent operation before
children are processed). These can be parallelized with
`concurrent.futures.ThreadPoolExecutor`.

**Risk factors to resolve:**
- Ansible's `_execute_module()` must be evaluated for thread-safety.
- The `self._connection` object may not be safely shared across threads.
- Result aggregation in `create_structured_results()` must handle concurrent updates.

---

### PENDING-03 — Remove Redundant `copy.deepcopy()` in Non-Mutated Data Paths

**Performance impact:** Low-Medium — `copy.deepcopy()` is O(n) in object graph size and
is called extensively on large VRF/attachment payloads.
**Reason deferred:** Requires careful audit of mutation patterns; incorrect removal can
cause subtle bugs where controller payloads are silently modified.

**Description:**
`copy.deepcopy()` is called in:
- `get_want()` — final assignment `self.want_create = copy.deepcopy(want_create)`, etc.
- `diff_merge_create()` / `push_diff_create()` — multiple deepcopy of VRF payloads.
- `push_diff_attach()` — `diff_attach["lanAttachList"] = copy.deepcopy(new_lan_attach_list)`.
- `create_child_task()` / `execute_child_task()` in action plugin.

**Approach:**
Audit which copies are truly needed (data is mutated in multiple separate code paths)
versus which are purely defensive (data flows linearly and is consumed once). Replace
defensive deepcopies with `dict.copy()` + explicit field construction for flat dicts,
or shallow list copies where nesting is only one level.

---

### PENDING-04 — Avoid Redundant `vrfTemplateConfig` JSON Re-parse in `push_diff_create()`

**Performance impact:** Low — avoids one `json.loads()` + full dict rebuild per new VRF
during the push phase.
**Reason deferred:** Requires a structural change to how VRF objects are passed between
`diff_merge_create()` and `push_diff_create()`.

**Description:**
`diff_merge_create()` already parses `vrfTemplateConfig`, builds `template_conf`, and
re-serializes it: `want_c.update({"vrfTemplateConfig": json.dumps(template_conf)})`.

`push_diff_create()` then immediately does `json.loads(vrf["vrfTemplateConfig"])` again
and rebuilds `t_conf` from scratch — even though `template_conf` was already built
correctly in the previous step.

**Fix:**
Store the already-built `template_conf` as a temporary sidecar key (e.g.,
`_parsed_template_config`) during the diff phase and consume it in `push_diff_create()`,
removing the key before the payload is sent to the controller.

---

### PENDING-05 — Batch VRF-Lite Switch Lookups Across Multiple Switches

**Performance impact:** Medium where VRF-Lite is actively used on multi-switch fabrics.
**Reason deferred:** Requires API capability verification — the `GET_VRF_SWITCH` path
must support comma-separated `serial-numbers`.

**Description:**
`get_vrf_lite_objects()` issues one `GET_VRF_SWITCH` call per (VRF, serial_number) pair:

```python
path = self.paths["GET_VRF_SWITCH"].format(
    attach_fabric, attach["vrfName"], attach["serialNumber"]  # one serial at a time
)
```

If the controller API supports `serial-numbers=SN1,SN2,SN3`, all switches for a given
VRF can be queried in a single call. This reduces O(switches) calls per VRF to O(1)
per VRF.

**Action required before implementing:**
Verify that the `GET_VRF_SWITCH` API endpoint accepts a comma-separated list of serial
numbers in the same way `GET_VRF_ATTACH` accepts comma-separated VRF names.

---

## Quick Reference

| ID | Description | Perf Impact | Risk | State |
|---|---|---|---|---|
| OPT-01 | Targeted `get_have()` for `merged`/`replaced` | Very High | Medium | Implement |
| OPT-02 | Targeted `get_have()` for `deleted` + config | Very High | Medium | Implement |
| OPT-03 | `have_create`/`have_attach` dict indexes for O(1) lookups | Medium | Low | Implement |
| OPT-04 | Bulk attachment fetch in `get_diff_query()` with config | Medium | Low | Implement |
| OPT-05 | Bulk attachment fetch in `get_diff_query()` no config | Medium | Low | Implement |
| OPT-06 | `wait_for_vrf_del_ready()` parallel initial poll pass | Medium | Low | Implement |
| OPT-07 | Remove `inspect.stack()` from hot loops | Medium | Low | Implement |
| OPT-08 | Consistent VRF-Lite API call guard in `get_have()` | Medium | Low | Implement |
| OPT-09 | Deduplicate `all_vrfs` with sets | Low | Low | Implement |
| OPT-10 | Avoid double fabric discovery in action plugin | Low-Medium | Low | Implement |
| PENDING-01 | Hybrid bulk threshold for large `merged`/`replaced` (≥25 VRFs) | High | Medium | After OPT-01 |
| PENDING-02 | Parallelize child fabric task execution | Medium | High | Design review |
| PENDING-03 | Audit + reduce `copy.deepcopy()` in non-mutated paths | Low-Medium | Medium | Audit first |
| PENDING-04 | Avoid `vrfTemplateConfig` re-parse in `push_diff_create()` | Low | Medium | Deferred |
| PENDING-05 | Batch VRF-Lite switch lookups (multi-serial) | Medium | Medium | API verify first |
