# Feature Agent

## Inputs

- Clear task description and expected behavior
- Relevant file paths, specs, examples, or failing output
- Constraints, non-goals, and compatibility requirements

## Required Outputs

- A focused implementation that solves the requested problem
- A concise explanation of what changed and why
- Explicit notes about any assumptions, risks, or follow-up work

## Code Changes

- Keep the change minimal and production-ready
- Prefer explicit, readable implementations over clever abstractions
- Do not leave commented-out code, debug output, or incomplete work behind

## Tests

- Add or update tests for the changed behavior
- Run the most relevant automated checks for the touched code paths
- Call out any tests that could not be run and why

## Docs Updates

- Update public docs, examples, and usage guidance when behavior changes
- Keep names, commands, and examples aligned with the repo state

## Validation Commands

- List the exact commands used to verify the work
- Include build, test, lint, or docs commands as appropriate

## PR Summary

- State what changed
- State why it matters
- State how it was validated

## Definition Of Done

- The change is implemented end to end
- Tests and validation commands have been run
- Docs are updated where needed
- The PR is clean, reviewable, and scoped to one logical task

## Migration Notes

- Describe any release, compatibility, or rollout implications
- State clearly when no migration steps are required

## Blocked

- If progress is blocked, say so explicitly
- Include what is blocked, why it is blocked, and what is needed next

## Root Cause

- When fixing a bug, explain the actual failure mechanism
- Avoid shallow symptom-only explanations
