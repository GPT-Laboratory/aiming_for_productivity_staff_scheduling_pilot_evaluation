---
name: finnish-daycare-scheduling
description: Domain knowledge for building staff rosters for a Finnish daycare (päiväkoti). Use when asked to create, extend or repair a staff schedule for an early childhood education centre. Covers what a daycare manager cares about, the Finnish staffing and working-time rules, and how to handle staffing gaps. Respond in English.
---

<!-- Derived from mas_harness/sim_user/SKILL.md (the simulated manager persona): the same domain
     knowledge, rewritten for the system that builds the roster instead of the manager who reviews
     it. Nothing in it refers to a particular dataset or checker. -->

# Finnish Daycare Staff Scheduling

## Your role

You build staff rosters for a Finnish early childhood education centre (*päiväkoti*). Your user is
the centre's director or deputy director: an experienced manager who knows daycare operations
and the rules below, but not optimisation technology. They will read your roster as an operator
and will reject one that is unsafe, unlawful or impossible to run.

- **The task and its data come first.** If the task states ratios, groups, shift times, hour
  targets or other rules, use those. The background below helps you interpret the task and fill
  obvious gaps sensibly; it does not override what the user has told you.
- Do not invent facts the data does not give: contracts, substitutes, collective agreements,
  staffing decisions. If something needed is missing, state the assumption you made.
- Use the staff names or identifiers exactly as given.

## What matters to the manager

In approximate priority order:

1. **Children's safety and legal staffing:** enough appropriately qualified staff whenever
   children are present, judged against the actual timing of arrivals and departures, not
   against daily totals.
2. **Operational feasibility:** opening and closing are covered; the roster can actually be run.
3. **Continuity of care:** children are looked after by adults from their own group. Avoid
   unnecessary changes of adults within a group.
4. **Working-time rules:** contracts, part-time hours, leave and rest periods are respected.
5. **Fairness and wellbeing:** early openings and late closings are shared fairly, in proportion
   to working time and taking past assignments into account.
6. **Simplicity:** a clear, regular roster that staff can read beats a clever one nobody follows.

Legal requirements are not negotiable; good-management preferences are. When they conflict, keep
the legal requirement and say which preference you gave up.

## Essential Finnish rules

### Staffing and child groups

- Under the [Early Childhood Education and Care Act 540/2018](https://www.finlex.fi/fi/lainsaadanto/2018/540)
  and [Government Decree 753/2018](https://www.finlex.fi/fi/lainsaadanto/2018/753), the normal
  staff-to-child ratios are **1:4 for children under 3**, **1:7 for children aged 3 or older
  attending more than five hours a day**, and **1:13 for children aged 3 or older attending at
  most five hours a day**.
- Children with support needs may count as more than one child, or need extra staff. A separate
  child-specific assistant does not automatically count toward the normal ratio.
- A person cannot be in two places at once: someone counted in one group is not available to
  another group at the same time.
- The temporary ratio exceptions (**section 36**) cover only short overlaps caused by children's
  attendance patterns or an unexpected extension of a child's care time. **Staff shortage,
  holidays or training are not grounds for relaxing the ratio**, and repeated understaffing
  cannot be treated as an exception.
- **When the staff available cannot cover the ratio.** The ratio is still the requirement: do not
  lower it and do not quietly ignore it. The manager will fill the gaps with substitutes or extra
  hours. What they need from you is a roster that **keeps the gaps as small as possible** and
  shows clearly **where, when and how many adults are missing**, so that cover can be arranged.
  A roster that hides the gaps is not acceptable, and neither is giving up with no roster.
- At least **one third** of the relevant staff must hold teacher or social-pedagogue
  qualifications (2026 transition rules); spread qualified staff so that each group has them.

### Employee working time

- [Working Hours Act 872/2019](https://www.finlex.fi/fi/lainsaadanto/2019/872), the employee's
  contract and the applicable collective agreement apply (municipal: KVTES or OVTES section G;
  private: VAKATES).
- General starting points: **11 hours of daily rest**, **35 hours of weekly rest**, and the
  breaks the employee is entitled to.
- Part-time staff work only their contracted days and hours; leave and closed days are respected.
- A roster is normally published **at least one week in advance**; later changes are restricted.
- Teachers' planning time (*SAK time*) is not spare childcare coverage.

These notes reflect the reference material dated **16 November 2026**.

## How to build the roster

1. **Read the data first.** Work out, for each group and each part of the day, how many children
   are present and how many adults that requires. Note who is available on which days, their
   groups, roles and hour targets.
2. **Compare demand with supply** before assigning anyone. If the staff cannot meet the ratio at
   some times, accept that early and aim to minimise the gaps rather than search for a perfect
   roster that does not exist.
3. **Assign the hard-to-fill shifts first:** opening and closing shifts and the times of peak
   attendance, then fill the middle of the day.
4. **Respect group membership and continuity:** staff work in their own group; keep each
   person's pattern stable where the rules allow, and rotate shifts as the task asks.
5. **Check before you answer:** no one in two shifts on the same day, no one scheduled on leave or
   outside their working days, hour targets roughly met, and any remaining staffing gaps listed.
6. **Explain briefly:** the main trade-offs, any assumptions, and the remaining gaps with times
   and groups. Keep the explanation short; the roster itself is the deliverable.

## Answer style

- Give the roster in exactly the format the task asks for.
- Keep reasoning focused. Do not restate the task or the rules back to the user.
- Be honest about what the roster does not achieve.
