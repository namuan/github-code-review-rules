"""Data processing service for transforming and storing GitHub PR data."""

import queue
import threading
from datetime import UTC, datetime
from typing import Any

from github_pr_rules_analyzer.models import CodeSnippet, CommentThread, ExtractedRule, ReviewComment, RuleStatistics
from github_pr_rules_analyzer.utils import get_logger
from github_pr_rules_analyzer.utils.database import get_session_local

logger = get_logger(__name__)


class DataProcessor:
    """Service for processing and storing GitHub PR data."""

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize data processor.

        Args:
        ----
            max_workers: Maximum number of worker threads

        """
        self.max_workers = max_workers
        self.session = get_session_local()
        self.task_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.workers = []

        # Thread-safe counters
        self.processed_count = 0
        self.error_count = 0
        self.lock = threading.Lock()

    def __del__(self) -> None:
        """Clean up database session."""
        if hasattr(self, "session"):
            self.session.close()

    def start_workers(self) -> None:
        """Start worker threads for processing."""
        logger.info("Starting %d worker threads", self.max_workers)

        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"DataProcessor-{i}",
                daemon=True,
            )
            worker.start()
            self.workers.append(worker)

    def stop_workers(self) -> None:
        """Stop worker threads."""
        logger.info("Stopping worker threads")

        self.stop_event.set()

        # Add sentinel values to wake up all workers
        for _ in range(self.max_workers):
            self.task_queue.put(None)

        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)

        self.workers = []

    def _worker_loop(self) -> None:
        """Worker thread main loop."""
        while not self.stop_event.is_set():
            try:
                # Get task from queue with timeout
                task = self.task_queue.get(timeout=1)

                if task is None:
                    break

                try:
                    self._process_task(task)
                except Exception:
                    logger.exception("Error processing task")
                    with self.lock:
                        self.error_count += 1

                finally:
                    self.task_queue.task_done()

            except queue.Empty:
                continue
            except Exception:
                logger.exception("Worker error")

    def _process_task(self, task: dict[str, Any]) -> None:
        """Process a single task.

        Args:
        ----
            task: Task dictionary with type and data

        """
        task_type = task.get("type")

        if task_type == "process_review_comment":
            self._process_review_comment(task["data"])
        elif task_type == "process_code_snippet":
            self._process_code_snippet(task["data"])
        elif task_type == "process_comment_thread":
            self._process_comment_thread(task["data"])
        elif task_type == "extract_rule":
            self._extract_rule(task["data"])
        elif task_type == "update_statistics":
            self._update_statistics(task["data"])
        else:
            logger.error("Unknown task type: %s", task_type)

    def add_review_comment_task(self, comment_data: dict[str, Any]) -> bool:
        """Add review comment processing task.

        Args:
        ----
            comment_data: Review comment data

        Returns:
        -------
            True if task was added successfully

        """
        try:
            task = {
                "type": "process_review_comment",
                "data": comment_data,
            }
            self.task_queue.put(task)
            return True
        except Exception:
            logger.exception("Error adding review comment task")
            return False

    def add_code_snippet_task(self, snippet_data: dict[str, Any]) -> bool:
        """Add code snippet processing task.

        Args:
        ----
            snippet_data: Code snippet data

        Returns:
        -------
            True if task was added successfully

        """
        try:
            task = {
                "type": "process_code_snippet",
                "data": snippet_data,
            }
            self.task_queue.put(task)
            return True
        except Exception:
            logger.exception("Error adding code snippet task")
            return False

    def add_comment_thread_task(self, thread_data: dict[str, Any]) -> bool:
        """Add comment thread processing task.

        Args:
        ----
            thread_data: Comment thread data

        Returns:
        -------
            True if task was added successfully

        """
        try:
            task = {
                "type": "process_comment_thread",
                "data": thread_data,
            }
            self.task_queue.put(task)
            return True
        except Exception:
            logger.exception("Error adding comment thread task")
            return False

    def add_rule_extraction_task(self, rule_data: dict[str, Any]) -> bool:
        """Add rule extraction task.

        Args:
        ----
            rule_data: Rule extraction data

        Returns:
        -------
            True if task was added successfully

        """
        try:
            task = {
                "type": "extract_rule",
                "data": rule_data,
            }
            self.task_queue.put(task)
            return True
        except Exception:
            logger.exception("Error adding rule extraction task")
            return False

    def add_statistics_update_task(self, stats_data: dict[str, Any]) -> bool:
        """Add statistics update task.

        Args:
        ----
            stats_data: Statistics update data

        Returns:
        -------
            True if task was added successfully

        """
        try:
            task = {
                "type": "update_statistics",
                "data": stats_data,
            }
            self.task_queue.put(task)
            return True
        except Exception:
            logger.exception("Error adding statistics update task")
            return False

    def _process_review_comment(self, comment_data: dict[str, Any]) -> None:
        """Process review comment data.

        Args:
        ----
            comment_data: Review comment data

        """
        try:
            # Validate comment data
            if not self._validate_review_comment(comment_data):
                logger.warning("Invalid review comment data: %s", comment_data)
                return

            # Create or update review comment
            comment = self._upsert_review_comment(comment_data)

            # Add rule extraction task
            rule_data = {
                "review_comment_id": comment.id,
                "comment_text": comment.body,
                "file_path": comment.path,
                "context": self._get_comment_context(comment),
            }
            self.add_rule_extraction_task(rule_data)

            with self.lock:
                self.processed_count += 1

        except Exception:
            logger.exception("Error processing review comment")
            raise

    def _process_code_snippet(self, snippet_data: dict[str, Any]) -> None:
        """Process code snippet data.

        Args:
        ----
            snippet_data: Code snippet data

        """
        try:
            # Validate snippet data
            if not self._validate_code_snippet(snippet_data):
                logger.warning("Invalid code snippet data: %s", snippet_data)
                return

            # Create or update code snippet
            self._upsert_code_snippet(snippet_data)

            with self.lock:
                self.processed_count += 1

        except Exception:
            logger.exception("Error processing code snippet")
            raise

    def _process_comment_thread(self, thread_data: dict[str, Any]) -> None:
        """Process comment thread data.

        Args:
        ----
            thread_data: Comment thread data

        """
        try:
            # Validate thread data
            if not self._validate_comment_thread(thread_data):
                logger.warning("Invalid comment thread data: %s", thread_data)
                return

            # Create or update comment thread
            self._upsert_comment_thread(thread_data)

            with self.lock:
                self.processed_count += 1

        except Exception:
            logger.exception("Error processing comment thread")
            raise

    def _extract_rule(self, rule_data: dict[str, Any]) -> None:
        """Extract rule from review comment.

        Args:
        ----
            rule_data: Rule extraction data

        """
        try:
            # Extract rule using simple rule-based approach
            rule_text = self._extract_rule_from_text(rule_data["comment_text"])

            if rule_text:
                # Create extracted rule
                rule = ExtractedRule(
                    review_comment_id=rule_data["review_comment_id"],
                    rule_text=rule_text,
                    rule_category=self._categorize_rule(rule_text),
                    rule_severity=self._assess_severity(rule_text),
                    confidence_score=self._calculate_confidence(rule_text, rule_data["context"]),
                    llm_model="rule-based",
                    prompt_used="Simple rule extraction",
                    response_raw=f'{{"rule": "{rule_text}"}}',
                )

                self.session.add(rule)
                self.session.commit()

                # Add statistics update task
                stats_data = {
                    "rule_id": rule.id,
                    "repository_id": rule_data.get("repository_id"),
                    "confidence_score": rule.confidence_score,
                }
                self.add_statistics_update_task(stats_data)

            with self.lock:
                self.processed_count += 1

        except Exception:
            logger.exception("Error extracting rule")
            raise

    def _update_statistics(self, stats_data: dict[str, Any]) -> None:
        """Update rule statistics.

        Args:
        ----
            stats_data: Statistics update data

        """
        try:
            rule_id = stats_data["rule_id"]
            repository_id = stats_data["repository_id"]
            confidence_score = stats_data["confidence_score"]

            # Check if statistics already exist
            existing_stats = (
                self.session.query(RuleStatistics)
                .filter(
                    RuleStatistics.rule_id == rule_id,
                    RuleStatistics.repository_id == repository_id,
                )
                .first()
            )

            if existing_stats:
                # Update existing statistics
                existing_stats.increment_occurrence(confidence_score)
            else:
                # Create new statistics
                from github_pr_rules_analyzer.models import ExtractedRule

                rule = self.session.query(ExtractedRule).filter(ExtractedRule.id == rule_id).first()
                if rule:
                    from github_pr_rules_analyzer.models import Repository

                    repository = self.session.query(Repository).filter(Repository.id == repository_id).first()
                    if repository:
                        stats = RuleStatistics.from_rule_and_repository(rule, repository)
                        self.session.add(stats)

            self.session.commit()

            with self.lock:
                self.processed_count += 1

        except Exception:
            logger.exception("Error updating statistics")
            raise

    def _validate_review_comment(self, comment_data: dict[str, Any]) -> bool:
        """Validate review comment data.

        Args:
        ----
            comment_data: Review comment data

        Returns:
        -------
            True if data is valid

        """
        required_fields = ["id", "body", "path", "position"]

        return all(not (field not in comment_data or not comment_data[field]) for field in required_fields)

    def _validate_code_snippet(self, snippet_data: dict[str, Any]) -> bool:
        """Validate code snippet data.

        Args:
        ----
            snippet_data: Code snippet data

        Returns:
        -------
            True if data is valid

        """
        required_fields = ["id", "content", "file_path", "line_start", "line_end"]

        for field in required_fields:
            if field not in snippet_data or not snippet_data[field]:
                return False

        # Validate line numbers
        return not (
            snippet_data["line_start"] <= 0
            or snippet_data["line_end"] <= 0
            or snippet_data["line_start"] > snippet_data["line_end"]
        )

    def _validate_comment_thread(self, thread_data: dict[str, Any]) -> bool:
        """Validate comment thread data.

        Args:
        ----
            thread_data: Comment thread data

        Returns:
        -------
            True if data is valid

        """
        required_fields = ["id", "thread_path", "thread_position"]

        return all(not (field not in thread_data or not thread_data[field]) for field in required_fields)

    def _upsert_review_comment(self, comment_data: dict[str, Any]) -> ReviewComment:
        """Create or update review comment.

        Args:
        ----
            comment_data: Review comment data

        Returns:
        -------
            ReviewComment instance

        """
        # Check if comment already exists
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
            existing_comment = ReviewComment.from_github_data(comment_data, comment_data.get("pull_request_id"))
            self.session.add(existing_comment)
            logger.debug("Created comment %d", comment_data["id"])

        self.session.commit()
        return existing_comment

    def _upsert_code_snippet(self, snippet_data: dict[str, Any]) -> None:
        """Create or update code snippet.

        Args:
        ----
            snippet_data: Code snippet data

        """
        # Check if snippet already exists
        existing_snippet = (
            self.session.query(CodeSnippet)
            .filter(
                CodeSnippet.id == snippet_data["id"],
            )
            .first()
        )

        if existing_snippet:
            # Update existing snippet
            existing_snippet.file_path = snippet_data["file_path"]
            existing_snippet.line_start = snippet_data["line_start"]
            existing_snippet.line_end = snippet_data["line_end"]
            existing_snippet.content = snippet_data["content"]
            existing_snippet.language = snippet_data.get("language")
            logger.debug("Updated snippet %d", snippet_data["id"])
        else:
            # Create new snippet
            from github_pr_rules_analyzer.models import ReviewComment

            review_comment = (
                self.session.query(ReviewComment)
                .filter(
                    ReviewComment.id == snippet_data["review_comment_id"],
                )
                .first()
            )

            if review_comment:
                snippet = CodeSnippet.from_review_comment(
                    review_comment,
                    snippet_data["file_path"],
                    snippet_data["line_start"],
                    snippet_data["line_end"],
                    snippet_data["content"],
                    snippet_data.get("language"),
                )
                self.session.add(snippet)
                logger.debug("Created snippet %d", snippet_data["id"])

        self.session.commit()

    def _upsert_comment_thread(self, thread_data: dict[str, Any]) -> None:
        """Create or update comment thread.

        Args:
        ----
            thread_data: Comment thread data

        """
        # Check if thread already exists
        existing_thread = (
            self.session.query(CommentThread)
            .filter(
                CommentThread.id == thread_data["id"],
            )
            .first()
        )

        if existing_thread:
            # Update existing thread
            existing_thread.thread_path = thread_data["thread_path"]
            existing_thread.thread_position = thread_data["thread_position"]
            existing_thread.is_resolved = thread_data.get("is_resolved", False)
            logger.debug("Updated thread %d", thread_data["id"])
        else:
            # Create new thread
            from github_pr_rules_analyzer.models import ReviewComment

            review_comment = (
                self.session.query(ReviewComment)
                .filter(
                    ReviewComment.id == thread_data["review_comment_id"],
                )
                .first()
            )

            if review_comment:
                pull_request = review_comment.pull_request
                thread = CommentThread(
                    pull_request_id=pull_request.id,
                    review_comment_id=review_comment.id,
                    thread_path=thread_data["thread_path"],
                    thread_position=thread_data["thread_position"],
                    is_resolved=thread_data.get("is_resolved", False),
                )
                self.session.add(thread)
                logger.debug("Created thread %d", thread_data["id"])

        self.session.commit()

    def _get_comment_context(self, comment: ReviewComment) -> dict[str, Any]:
        """Get context for a review comment.

        Args:
        ----
            comment: Review comment instance

        Returns:
        -------
            Context dictionary

        """
        return {
            "file_path": comment.path,
            "line_number": comment.line,
            "position": comment.position,
            "pr_title": comment.pull_request.title,
            "pr_number": comment.pull_request.number,
            "repository_name": comment.pull_request.repository.full_name,
            "author": comment.author_login,
            "comment_length": len(comment.body),
            "has_code_snippets": len(comment.code_snippets) > 0,
        }

    def _extract_rule_from_text(self, text: str) -> str | None:
        """Extract rule from comment text using simple rule-based approach.

        Args:
        ----
            text: Comment text

        Returns:
        -------
            Extracted rule text or None

        """
        if not text or not text.strip():
            return None

        # Common rule indicators
        rule_patterns = [
            r"should\s+(?:always|never)\s+\w+",
            r"avoid\s+\w+",
            r"use\s+\w+\s+instead",
            r"prefer\s+\w+\s+over",
            r"follow\s+\w+\s+convention",
            r"ensure\s+\w+\s+is\s+\w+",
            r"make\s+sure\s+to\s+\w+",
            r"remember\s+to\s+\w+",
            r"do\s+not\s+\w+",
            r"always\s+\w+",
            r"never\s+\w+",
        ]

        import re

        for pattern in rule_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Clean up the matched text
                rule_text = match.group(0)
                # Capitalize first letter
                rule_text = rule_text[0].upper() + rule_text[1:]
                # Add period if missing
                if not rule_text.endswith("."):
                    rule_text += "."
                return rule_text

        # Look for imperative sentences
        sentences = re.split(r"[.!?]+", text)
        for sentence in sentences:
            stripped_sentence = sentence.strip()
            if stripped_sentence and len(stripped_sentence) > 10:  # Reasonable length
                # Check if it starts with imperative verb
                imperative_verbs = [
                    "use",
                    "avoid",
                    "follow",
                    "ensure",
                    "make",
                    "remember",
                    "do",
                    "always",
                    "never",
                    "prefer",
                    "implement",
                    "add",
                    "remove",
                    "change",
                    "update",
                    "fix",
                    "refactor",
                    "optimize",
                    "simplify",
                    "standardize",
                    "document",
                    "test",
                    "validate",
                ]

                first_word = sentence.split()[0].lower() if sentence.split() else ""
                if first_word in imperative_verbs:
                    rule_text = sentence[0].upper() + sentence[1:]
                    if not rule_text.endswith("."):
                        rule_text += "."
                    return rule_text

        return None

    def _categorize_rule(self, rule_text: str) -> str:
        """Categorize rule text.

        Args:
        ----
            rule_text: Rule text

        Returns:
        -------
            Category name

        """
        rule_lower = rule_text.lower()

        category_keywords = {
            "naming": ["name", "naming", "variable", "function", "class", "method", "identifier"],
            "style": ["style", "format", "indent", "spacing", "layout", "appearance"],
            "performance": ["performance", "efficient", "optimize", "speed", "memory"],
            "security": ["security", "safe", "vulnerable", "attack", "protect"],
            "best_practices": ["best", "practice", "convention", "standard", "guideline"],
            "error_handling": ["error", "exception", "handle", "catch", "throw"],
            "testing": ["test", "testing", "unit", "integration", "coverage"],
            "documentation": ["document", "comment", "doc", "readme", "description"],
            "architecture": ["architecture", "design", "structure", "pattern", "module"],
            "readability": ["readable", "clear", "understand", "simple", "clean"],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in rule_lower for keyword in keywords):
                return category

        return "general"

    def _assess_severity(self, rule_text: str) -> str:
        """Assess rule severity.

        Args:
        ----
            rule_text: Rule text

        Returns:
        -------
            Severity level

        """
        rule_lower = rule_text.lower()

        severity_keywords = {
            "critical": ["critical", "must", "required", "mandatory", "essential"],
            "high": ["high", "important", "serious", "major"],
            "medium": ["medium", "moderate", "should", "recommended"],
            "low": ["low", "minor", "optional", "suggestion"],
            "info": ["info", "note", "reminder", "fyi"],
        }

        for severity, keywords in severity_keywords.items():
            if any(keyword in rule_lower for keyword in keywords):
                return severity

        # Default based on rule length and complexity
        if len(rule_text) > 100:
            return "medium"
        if len(rule_text) > 50:
            return "low"
        return "info"

    def _calculate_confidence(self, rule_text: str, context: dict[str, Any]) -> float:
        """Calculate confidence score for rule.

        Args:
        ----
            rule_text: Rule text
            context: Comment context

        Returns:
        -------
            Confidence score (0.0 to 1.0)

        """
        confidence = 0.5  # Base confidence

        # Boost confidence for longer rules
        if len(rule_text) > 50:
            confidence += 0.1

        # Boost confidence for rules with context
        if context.get("has_code_snippets"):
            confidence += 0.1

        # Boost confidence for specific categories
        if context.get("file_path"):
            confidence += 0.05

        # Boost confidence for authors with history
        if context.get("author"):
            confidence += 0.05

        # Cap at 1.0
        return min(confidence, 1.0)

    def get_processing_stats(self) -> dict[str, Any]:
        """Get processing statistics.

        Returns
        -------
            Statistics dictionary

        """
        with self.lock:
            return {
                "processed_count": self.processed_count,
                "error_count": self.error_count,
                "queue_size": self.task_queue.qsize(),
                "worker_count": len(self.workers),
                "is_running": len(self.workers) > 0,
            }

    def process_batch(self, items: list[dict[str, Any]], task_type: str) -> dict[str, Any]:
        """Process a batch of items.

        Args:
        ----
            items: List of items to process
            task_type: Type of task to create

        Returns:
        -------
            Processing results

        """
        results = {
            "total": len(items),
            "success": 0,
            "errors": 0,
            "start_time": datetime.now(UTC),
            "end_time": None,
        }

        try:
            # Add tasks to queue
            for item in items:
                task = {"type": task_type, "data": item}
                self.task_queue.put(task)

            # Wait for all tasks to complete
            self.task_queue.join()

            results["success"] = results["total"] - results["errors"]
            results["end_time"] = datetime.now(UTC)

            return results

        except Exception:
            logger.exception("Error processing batch")
            results["errors"] = results["total"]
            results["end_time"] = datetime.now(UTC)
            return results

    def process_review_comments_batch(self, comments: list[dict[str, Any]]) -> dict[str, Any]:
        """Process a batch of review comments.

        Args:
        ----
            comments: List of review comment data

        Returns:
        -------
            Processing results

        """
        return self.process_batch(comments, "process_review_comment")

    def process_code_snippets_batch(self, snippets: list[dict[str, Any]]) -> dict[str, Any]:
        """Process a batch of code snippets.

        Args:
        ----
            snippets: List of code snippet data

        Returns:
        -------
            Processing results

        """
        return self.process_batch(snippets, "process_code_snippet")

    def process_comment_threads_batch(self, threads: list[dict[str, Any]]) -> dict[str, Any]:
        """Process a batch of comment threads.

        Args:
        ----
            threads: List of comment thread data

        Returns:
        -------
            Processing results

        """
        return self.process_batch(threads, "process_comment_thread")
