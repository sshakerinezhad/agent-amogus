# Next Step

Read project context and masterplan, identify the next step, critically evaluate it, and produce a detailed implementation plan.

**Note:** This command is intended for use in plan mode.

## Instructions

### Phase 1: Gather Context

1. Read `.claude/scratchpad.md` for current session context
2. Read `.claude/work-plan.md` for active work items (if exists)
3. Read `.claude/masterplan.md` to understand:
   - Overall goal and architecture
   - What has been completed
   - What the next step is

### Phase 2: Identify Next Step

4. From the masterplan, identify the **next uncompleted step**
5. Assess if this step is appropriately scoped:
   - If too large, break it into smaller substeps
   - Focus on just what can be accomplished in one session
6. Consider how this step relates to:
   - What's already been built
   - What needs to come after

### Phase 3: Critical Evaluation

7. Evaluate the planned approach against project principles (see CLAUDE.md):
   - **Simplicity:** Is this the simplest solution? Could it be simpler?
   - **Bandaids:** Is this a temporary fix that creates tech debt?
   - **Scalability:** Will this approach cause problems as the project grows?
   - **Integration:** How does this interact with the existing system?
   - **Clutter:** Does this add unnecessary complexity or files?

8. Identify any issues:
   - Gaps in the plan
   - Open questions requiring user input
   - Potential problems or edge cases
   - Alternative approaches worth considering

### Phase 4: Report to User

9. If issues were found:
   - Present each issue clearly
   - Explain why it's a concern
   - Suggest options where possible
   - Ask the user how they want to proceed

10. If no issues, or after issues are resolved:
    - Present the fleshed-out plan for the next step
    - Include: what files will be modified/created, what changes will be made, and verification steps
