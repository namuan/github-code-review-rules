"""Data collection service for GitHub pull requests."""

from datetime import UTC, datetime
from typing import Any

from ..github.client import GitHubAPIClient
from ..models import CodeSnippet, CommentThread, PullRequest, Repository, ReviewComment
from ..utils import get_logger
from ..utils.database import get_session_local

logger = get_logger(__name__)


class DataCollector:
    """Service for collecting GitHub pull request data."""

    def __init__(self, github_token: str | None = None) -> None:
        """Initialize data collector.

        Args:
        ----
            github_token: GitHub personal access token

        """
        self.github_client = GitHubAPIClient(github_token)
        self.session = get_session_local()

    def __del__(self) -> None:
        """Clean up database session."""
        if hasattr(self, "session"):
            self.session.close()

    def collect_repository_data(self, owner: str, repo: str) -> dict[str, Any]:
        """Collect all data for a repository.

        Args:
        ----
            owner: Repository owner
            repo: Repository name

        Returns:
        -------
            Collection results dictionary

        """
        logger.info("Starting data collection for %s/%s", owner, repo)

        results = {
            "repository": None,
            "pull_requests": [],
            "review_comments": [],
            "code_snippets": [],
            "comment_threads": [],
            "errors": [],
            "start_time": datetime.now(UTC),
            "end_time": None,
        }

        try:
            # Validate repository access
            if not self.github_client.validate_repository_access(owner, repo):
                msg = f"Cannot access repository {owner}/{repo}"
                raise Exception(msg)

            # Get repository info
            repo_info = self.github_client.get_repository_info(owner, repo)
            logger.info("Repository info: %s", repo_info["info"]["full_name"])

            # Create or update repository
            repository = self._upsert_repository(repo_info["info"])
            results["repository"] = repository.to_dict()

            # Get closed pull requests
            closed_prs = self.github_client.get_pull_requests(owner, repo, state="closed")
            logger.info("Found %d closed pull requests", len(closed_prs))

            # Collect data for each pull request
            for pr_data in closed_prs:
                try:
                    pr_result = self._collect_pull_request_data(pr_data, repository.id)
                    results["pull_requests"].append(pr_result)

                    # Aggregate results
                    results["review_comments"].extend(pr_result["review_comments"])
                    results["code_snippets"].extend(pr_result["code_snippets"])
                    results["comment_threads"].extend(pr_result["comment_threads"])

                except Exception as e:
                    error_msg = f"Error collecting PR #{pr_data['number']}: {e!s}"
                    logger.exception(error_msg)
                    results["errors"].append(error_msg)

            results["end_time"] = datetime.now(UTC)

            # Log summary
            duration = (results["end_time"] - results["start_time"]).total_seconds()
            logger.info("Data collection completed in %.2f seconds", duration)
            "Collected: %d PRs, %d comments, %d snippets, %d threads" % (
                      len(results["pull_requests"]),
                      len(results["review_comments"]),
                      len(results["code_snippets"]),
                      len(results["comment_threads"]),
                  )

            return results

        except Exception as e:
            error_msg = f"Error collecting repository data: {e!s}"
            logger.exception(error_msg)
            results["errors"].append(error_msg)
            results["end_time"] = datetime.now(UTC)
            return results

    def _upsert_repository(self, repo_data: dict[str, Any]) -> Repository:
        """Create or update repository in database.

        Args:
        ----
            repo_data: Repository data from GitHub API

        Returns:
        -------
            Repository instance

        """
        # Check if repository already exists
        existing_repo = (
            self.session.query(Repository)
            .filter(
                Repository.github_id == repo_data["id"],
            )
            .first()
        )

        if existing_repo:
            # Update existing repository
            existing_repo.update_from_github_data(repo_data)
            logger.info("Updated repository: %s", repo_data["full_name"])
        else:
            # Create new repository
            existing_repo = Repository.from_github_data(repo_data)
            self.session.add(existing_repo)
            logger.info("Created repository: %s", repo_data["full_name"])

        self.session.commit()
        return existing_repo

    def _collect_pull_request_data(self, pr_data: dict[str, Any], repository_id: int) -> dict[str, Any]:
        """Collect data for a single pull request.

        Args:
        ----
            pr_data: Pull request data from GitHub API
            repository_id: Database ID of the repository

        Returns:
        -------
            Collection results for the pull request

        """
        logger.info("Collecting data for PR #%d: %s", pr_data["number"], pr_data["title"])

        results = {
            "pull_request": None,
            "review_comments": [],
            "code_snippets": [],
            "comment_threads": [],
            "errors": [],
        }

        try:
            # Create or update pull request
            pull_request = self._upsert_pull_request(pr_data, repository_id)
            results["pull_request"] = pull_request.to_dict()

            # Get all comments
            all_comments = self.github_client.get_all_comments(
                pr_data["head"]["repo"]["full_name"].split("/")[0],
                pr_data["head"]["repo"]["full_name"].split("/")[1],
                pr_data["number"],
            )

            logger.info("Found %d comments for PR #%d", len(all_comments), pr_data["number"])

            # Process each comment
            for comment_data in all_comments:
                try:
                    comment_result = self._process_comment(comment_data, pull_request.id)
                    results["review_comments"].append(comment_result["comment"])
                    results["code_snippets"].extend(comment_result["code_snippets"])
                    results["comment_threads"].extend(comment_result["comment_threads"])

                except Exception as e:
                    error_msg = f"Error processing comment {comment_data.get('id', 'unknown')}: {e!s}"
                    logger.exception(error_msg)
                    results["errors"].append(error_msg)

            return results

        except Exception as e:
            error_msg = f"Error collecting PR #{pr_data['number']}: {e!s}"
            logger.exception(error_msg)
            results["errors"].append(error_msg)
            return results

    def _upsert_pull_request(self, pr_data: dict[str, Any], repository_id: int) -> PullRequest:
        """Create or update pull request in database.

        Args:
        ----
            pr_data: Pull request data from GitHub API
            repository_id: Database ID of the repository

        Returns:
        -------
            PullRequest instance

        """
        # Check if pull request already exists
        existing_pr = (
            self.session.query(PullRequest)
            .filter(
                PullRequest.github_id == pr_data["id"],
            )
            .first()
        )

        if existing_pr:
            # Update existing pull request
            existing_pr.update_from_github_data(pr_data)
            logger.info("Updated PR #%d", pr_data["number"])
        else:
            # Create new pull request
            existing_pr = PullRequest.from_github_data(pr_data, repository_id)
            self.session.add(existing_pr)
            logger.info("Created PR #%d", pr_data["number"])

        self.session.commit()
        return existing_pr

    def _process_comment(self, comment_data: dict[str, Any], pull_request_id: int) -> dict[str, Any]:
        """Process a single comment and extract related data.

        Args:
        ----
            comment_data: Comment data from GitHub API
            pull_request_id: Database ID of the pull request

        Returns:
        -------
            Processing results for the comment

        """
        results = {
            "comment": None,
            "code_snippets": [],
            "comment_threads": [],
        }

        try:
            # Create or update review comment
            review_comment = self._upsert_review_comment(comment_data, pull_request_id)
            results["comment"] = review_comment.to_dict()

            # Extract code snippets from diff hunk
            if comment_data.get("diff_hunk"):
                snippets = self._extract_code_snippets(review_comment, comment_data["diff_hunk"])
                results["code_snippets"] = [snippet.to_dict() for snippet in snippets]

            # Create comment thread
            thread = self._create_comment_thread(review_comment, pull_request_id)
            if thread:
                results["comment_threads"] = [thread.to_dict()]

            return results

        except Exception as e:
            logger.exception("Error processing comment: %s", str(e))
            return results

    def _upsert_review_comment(self, comment_data: dict[str, Any], pull_request_id: int) -> ReviewComment:
        """Create or update review comment in database.

        Args:
        ----
            comment_data: Comment data from GitHub API
            pull_request_id: Database ID of the pull request

        Returns:
        -------
            ReviewComment instance

        """
        # Check if review comment already exists
        existing_comment = (
            self.session.query(ReviewComment)
            .filter(
                ReviewComment.github_id == comment_data["id"],
            )
            .first()
        )

        if existing_comment:
            # Update existing comment
            existing_comment.update_from_github_data(comment_data)
            logger.debug("Updated comment %d", comment_data["id"])
        else:
            # Create new comment
            existing_comment = ReviewComment.from_github_data(comment_data, pull_request_id)
            self.session.add(existing_comment)
            logger.debug("Created comment %d", comment_data["id"])

        self.session.commit()
        return existing_comment

    def _extract_code_snippets(self, review_comment: ReviewComment, diff_hunk: str) -> list[CodeSnippet]:
        """Extract code snippets from diff hunk.

        Args:
        ----
            review_comment: Review comment instance
            diff_hunk: Diff hunk from GitHub API

        Returns:
        -------
            List of CodeSnippet instances

        """
        snippets = []

        try:
            # Parse diff hunk to extract code
            lines = diff_hunk.split("\n")
            code_lines = []
            line_number = None

            for line in lines:
                if line.startswith("@@"):
                    # Parse line numbers from hunk header
                    # Example: @@ -50,6 +50,6 @@
                    parts = line.split(" ")
                    if len(parts) >= 3:
                        new_line_part = parts[2]
                        if new_line_part.startswith("+"):
                            line_number = int(new_line_part[1:].split(",")[0])
                elif line.startswith("+") and not line.startswith("++"):
                    # This is an added line of code
                    if line_number is not None:
                        code_lines.append((line_number, line[1:]))  # Remove '+' prefix
                        line_number += 1

            # Create code snippets
            if code_lines:
                # Group consecutive lines
                current_snippet = []
                start_line = None

                for line_num, code_line in code_lines:
                    if current_snippet and line_num != start_line + len(current_snippet):
                        # Start new snippet
                        if current_snippet:
                            snippet = CodeSnippet.from_review_comment(
                                review_comment,
                                review_comment.path,
                                start_line,
                                start_line + len(current_snippet) - 1,
                                "\n".join([line for _, line in current_snippet]),
                                self._detect_language(review_comment.path),
                            )
                            snippets.append(snippet)
                            self.session.add(snippet)

                        current_snippet = [(line_num, code_line)]
                        start_line = line_num
                    else:
                        current_snippet.append((line_num, code_line))

                # Add last snippet
                if current_snippet:
                    snippet = CodeSnippet.from_review_comment(
                        review_comment,
                        review_comment.path,
                        start_line,
                        start_line + len(current_snippet) - 1,
                        "\n".join([line for _, line in current_snippet]),
                        self._detect_language(review_comment.path),
                    )
                    snippets.append(snippet)
                    self.session.add(snippet)

                self.session.commit()

        except Exception as e:
            logger.exception("Error extracting code snippets: %s", str(e))

        return snippets

    def _detect_language(self, file_path: str) -> str | None:
        """Detect programming language from file path.

        Args:
        ----
            file_path: File path

        Returns:
        -------
            Language name or None

        """
        extension = file_path.split(".")[-1].lower() if "." in file_path else None

        language_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "cs": "c#",
            "go": "go",
            "rs": "rust",
            "php": "php",
            "rb": "ruby",
            "swift": "swift",
            "kt": "kotlin",
            "scala": "scala",
            "html": "html",
            "css": "css",
            "scss": "scss",
            "sass": "sass",
            "less": "less",
            "sql": "sql",
            "sh": "shell",
            "bash": "bash",
            "zsh": "zsh",
            "ps1": "powershell",
            "lua": "lua",
            "r": "r",
            "m": "matlab",
            "jl": "julia",
            "dockerfile": "dockerfile",
            "yaml": "yaml",
            "yml": "yaml",
            "json": "json",
            "xml": "xml",
            "md": "markdown",
            "txt": "plaintext",
        }

        return language_map.get(extension)

    def _create_comment_thread(self, review_comment: ReviewComment, pull_request_id: int) -> CommentThread | None:
        """Create comment thread for review comment.

        Args:
        ----
            review_comment: Review comment instance
            pull_request_id: Database ID of the pull request

        Returns:
        -------
            CommentThread instance or None

        """
        try:
            # Check if thread already exists
            existing_thread = (
                self.session.query(CommentThread)
                .filter(
                    CommentThread.pull_request_id == pull_request_id,
                    CommentThread.thread_path == review_comment.path,
                    CommentThread.thread_position == review_comment.position,
                )
                .first()
            )

            if existing_thread:
                return existing_thread

            # Create new thread
            thread = CommentThread.from_review_comment(review_comment, pull_request_id)
            self.session.add(thread)
            self.session.commit()

            return thread

        except Exception as e:
            logger.exception("Error creating comment thread: %s", str(e))
            return None

    def get_collection_status(self) -> dict[str, Any]:
        """Get current collection status.

        Returns
        -------
            Status dictionary

        """
        try:
            # Get repository count
            repo_count = self.session.query(Repository).count()

            # Get pull request count
            pr_count = self.session.query(PullRequest).count()

            # Get review comment count
            comment_count = self.session.query(ReviewComment).count()

            # Get code snippet count
            snippet_count = self.session.query(CodeSnippet).count()

            # Get comment thread count
            thread_count = self.session.query(CommentThread).count()

            # Get rate limit status
            rate_limit = self.github_client.get_rate_limit_status()

            return {
                "repositories": repo_count,
                "pull_requests": pr_count,
                "review_comments": comment_count,
                "code_snippets": snippet_count,
                "comment_threads": thread_count,
                "rate_limit": rate_limit,
            }

        except Exception as e:
            logger.exception("Error getting collection status: %s", str(e))
            return {"error": str(e)}

    def cleanup_old_data(self, days: int = 30) -> dict[str, int]:
        """Clean up old data from database.

        Args:
        ----
            days: Number of days to keep data

        Returns:
        -------
            Dictionary with counts of deleted items

        """
        from datetime import timedelta

        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        results = {}

        try:
            # Delete old code snippets
            deleted_snippets = (
                self.session.query(CodeSnippet)
                .filter(
                    CodeSnippet.created_at < cutoff_date,
                )
                .delete()
            )
            results["code_snippets"] = deleted_snippets

            # Delete old comment threads
            deleted_threads = (
                self.session.query(CommentThread)
                .filter(
                    CommentThread.created_at < cutoff_date,
                )
                .delete()
            )
            results["comment_threads"] = deleted_threads

            # Delete old review comments (cascade delete related data)
            deleted_comments = (
                self.session.query(ReviewComment)
                .filter(
                    ReviewComment.created_at < cutoff_date,
                )
                .delete()
            )
            results["review_comments"] = deleted_comments

            # Delete old pull requests (cascade delete related data)
            deleted_prs = (
                self.session.query(PullRequest)
                .filter(
                    PullRequest.created_at < cutoff_date,
                )
                .delete()
            )
            results["pull_requests"] = deleted_prs

            # Delete old repositories (cascade delete related data)
            deleted_repos = (
                self.session.query(Repository)
                .filter(
                    Repository.created_at < cutoff_date,
                )
                .delete()
            )
            results["repositories"] = deleted_repos

            self.session.commit()

            logger.info("Cleaned up old data: %s", results)

            return results

        except Exception as e:
            logger.exception("Error cleaning up old data: %s", str(e))
            self.session.rollback()
            return {"error": str(e)}
