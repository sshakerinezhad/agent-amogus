"""Local pull request tracker for AMOGUS experiments.

Manages PR lifecycle (open, review, merge) without any external API.
Git merges are performed via GitPython wrapped in ``asyncio.to_thread``
so the orchestrator's event loop stays responsive.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal

from git import Repo
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class PRReview(BaseModel):
    """A single review attached to a pull request."""

    reviewer: str
    verdict: Literal["approve", "reject", "comment"]
    comments: list[str] = []
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class PullRequest(BaseModel):
    """Local PR tracker — no GitHub API needed."""

    id: str  # "PR-001"
    title: str
    author: str
    source_branch: str
    target_branch: str = "main"
    files_changed: list[str] = []
    status: Literal["open", "merged", "closed"] = "open"
    reviews: list[PRReview] = []
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


class PullRequestTracker:
    """Manages the full PR lifecycle within a local git repository.

    PRs use auto-incrementing IDs of the form ``PR-001``, ``PR-002``, etc.
    """

    def __init__(self) -> None:
        self._prs: dict[str, PullRequest] = {}
        self._counter: int = 0

    # -- queries -------------------------------------------------------------

    @property
    def all_prs(self) -> dict[str, PullRequest]:
        """Return a copy of all tracked PRs keyed by ID."""
        return dict(self._prs)

    def get_pr(self, pr_id: str) -> PullRequest:
        """Return a PR by ID, raising ``KeyError`` if not found."""
        try:
            return self._prs[pr_id]
        except KeyError:
            raise KeyError(f"Pull request not found: {pr_id}") from None

    def list_open_prs(self) -> list[PullRequest]:
        """Return all PRs whose status is ``open``."""
        return [pr for pr in self._prs.values() if pr.status == "open"]

    # -- mutations -----------------------------------------------------------

    def open_pr(
        self,
        author: str,
        title: str,
        branch: str,
        files: list[str],
    ) -> PullRequest:
        """Create a new PR with an auto-incrementing ID."""
        self._counter += 1
        pr_id = f"PR-{self._counter:03d}"
        pr = PullRequest(
            id=pr_id,
            title=title,
            author=author,
            source_branch=branch,
            files_changed=files,
        )
        self._prs[pr_id] = pr
        return pr

    def review_pr(
        self,
        pr_id: str,
        reviewer: str,
        verdict: Literal["approve", "reject", "comment"],
        comments: list[str] | None = None,
    ) -> None:
        """Append a review to an existing PR."""
        pr = self.get_pr(pr_id)
        review = PRReview(
            reviewer=reviewer,
            verdict=verdict,
            comments=comments or [],
        )
        pr.reviews.append(review)

    async def merge_pr(self, pr_id: str, repo: Repo) -> str:
        """Merge the PR's source branch into its target branch.

        The actual git merge runs in a thread via ``asyncio.to_thread`` so we
        don't block the event loop.  Returns the merge commit SHA and sets the
        PR status to ``merged``.

        IMPORTANT: We never call ``git checkout`` here because the main repo
        shares its ``.git`` directory with agent worktrees.  Checking out a
        different branch would move the shared HEAD and corrupt worktree state.
        Instead we verify the repo is already on the target branch.
        """
        pr = self.get_pr(pr_id)

        def _do_merge() -> str:
            # Verify we're already on the target branch — never checkout,
            # as that would corrupt worktrees sharing this .git directory.
            current = repo.active_branch.name if not repo.head.is_detached else None
            if current != pr.target_branch:
                raise RuntimeError(
                    f"Cannot merge {pr.id}: repo HEAD is on '{current}', "
                    f"expected '{pr.target_branch}'"
                )
            repo.git.merge(pr.source_branch, m=f"Merge {pr.source_branch}: {pr.title}")
            return repo.head.commit.hexsha

        merge_sha: str = await asyncio.to_thread(_do_merge)
        pr.status = "merged"
        return merge_sha
