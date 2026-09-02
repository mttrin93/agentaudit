# The issue tracker

**The tracker is GitHub Issues on `TuringCollegeSubmissions/mrinal-AE.CAP.AFA.1.1`.**

That repository is the `submission` remote. There is also a stale `old-origin`
remote pointing at `mrinal-AE.AFA.4.6`, a different sprint's repository, and `gh`
resolves to it by default unless told otherwise. **Always pass `-R`:**

```
gh issue view <number> -R TuringCollegeSubmissions/mrinal-AE.CAP.AFA.1.1 --comments
gh issue list -R TuringCollegeSubmissions/mrinal-AE.CAP.AFA.1.1 --state open
```

Without `-R`, issues are read from — or filed into — a repository nobody reads.

## Finding the issue a change came from

Commit messages carry the PR number, not the issue number: this repo squash-merges,
so a subject ends `(#31)` where 31 is the **pull request**. The issue is named in the
PR body as `Closes #28`. To get from a commit to its issue:

```
gh pr view <pr-number> -R TuringCollegeSubmissions/mrinal-AE.CAP.AFA.1.1 --json body,closingIssuesReferences
```

`closingIssuesReferences` is the reliable field. Do not assume the number in a commit
subject is an issue number — it usually is not.

## Dependencies and grouping are machine-readable

Blockers live in GitHub's native dependency fields, not only in issue prose:

```
gh api repos/TuringCollegeSubmissions/mrinal-AE.CAP.AFA.1.1/issues/<n>/dependencies/blocked_by
```

Parent/child grouping uses native sub-issues, readable over GraphQL (`parent`,
`subIssues`). Several issues titled `Group A:`, `Group B:` … are parents that hold no
work of their own; their children carry it. An issue is ready to start when nothing
in its `blocked_by` list is still open.

## Where the standards live, for a Standards-axis review

This repo has no `CODING_STANDARDS.md` and no `CONTRIBUTING.md`. The documented
standards are:

- **`CLAUDE.md`** — the standing rules. Most load-bearing: no adaptive result may
  write into a scored rate; drive every new test red once before committing; never
  merge on red CI; blockers live in GitHub's native fields.
- **`CONTEXT.md`** — the domain vocabulary. Terms like *target*, *case*, *attempt*,
  *family* and *verdict* are load-bearing arithmetic, not synonyms; an **attempt** is
  the unit of the denominator and a turn is not an attempt.
- **`docs/adr/`** — the architectural decisions, each numbered. A change that
  contradicts an accepted ADR is a hard violation, not a judgement call. ADR-0010
  (the two layers) and ADR-0017 (what a signed document states) are the ones most
  often at stake.
- **`docs/specs/`** — the build specs, and `PLAN.md` for scope and phases.

Prose convention: this codebase carries its architectural reasoning in **docstrings**
rather than in comments, and at length. Density of explanation is the house style, not
a smell to report.

## Closing

Never close an issue bare — post a comment saying what landed first, since the thread
is the only record a tracker reader sees:

```
gh issue comment <n> -R TuringCollegeSubmissions/mrinal-AE.CAP.AFA.1.1 --body-file <file>
gh issue close <n> -R TuringCollegeSubmissions/mrinal-AE.CAP.AFA.1.1 --reason completed
```
