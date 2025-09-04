"""Unit tests for data processor service."""

import time

from github_pr_rules_analyzer.services.data_processor import DataProcessor


class TestDataProcessor:
    """Test data processor service."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.processor = DataProcessor(max_workers=2)

    def test_initialization(self) -> None:
        """Test data processor initialization."""
        assert self.processor.max_workers == 2
        assert self.processor.session is not None
        assert self.processor.task_queue is not None
        assert self.processor.stop_event is not None
        assert self.processor.processed_count == 0
        assert self.processor.error_count == 0
        assert len(self.processor.workers) == 0

    def test_start_workers(self) -> None:
        """Test starting worker threads."""
        self.processor.start_workers()

        assert len(self.processor.workers) == 2
        assert all(worker.is_alive() for worker in self.processor.workers)

        # Clean up
        self.processor.stop_workers()

    def test_stop_workers(self) -> None:
        """Test stopping worker threads."""
        # Start workers first
        self.processor.start_workers()
        assert len(self.processor.workers) == 2

        # Stop workers
        self.processor.stop_workers()

        assert len(self.processor.workers) == 0

    def test_add_review_comment_task(self) -> None:
        """Test adding review comment task."""
        # Start workers
        self.processor.start_workers()

        comment_data = {
            "id": 1,
            "body": "This code needs improvement",
            "path": "src/main.py",
            "position": 5,
            "line": 10,
            "pull_request_id": 1,
        }

        result = self.processor.add_review_comment_task(comment_data)

        assert result is True
        assert self.processor.task_queue.qsize() == 1

        # Clean up
        self.processor.stop_workers()

    def test_add_code_snippet_task(self) -> None:
        """Test adding code snippet task."""
        # Start workers
        self.processor.start_workers()

        snippet_data = {
            "id": 1,
            "content": "def test():\n    pass",
            "file_path": "src/main.py",
            "line_start": 10,
            "line_end": 11,
            "review_comment_id": 1,
            "language": "python",
        }

        result = self.processor.add_code_snippet_task(snippet_data)

        assert result is True
        assert self.processor.task_queue.qsize() == 1

        # Clean up
        self.processor.stop_workers()

    def test_add_comment_thread_task(self) -> None:
        """Test adding comment thread task."""
        # Start workers
        self.processor.start_workers()

        thread_data = {
            "id": 1,
            "thread_path": "src/main.py",
            "thread_position": 5,
            "review_comment_id": 1,
            "is_resolved": False,
        }

        result = self.processor.add_comment_thread_task(thread_data)

        assert result is True
        assert self.processor.task_queue.qsize() == 1

        # Clean up
        self.processor.stop_workers()

    def test_add_rule_extraction_task(self) -> None:
        """Test adding rule extraction task."""
        # Start workers
        self.processor.start_workers()

        rule_data = {
            "review_comment_id": 1,
            "comment_text": "This code needs improvement",
            "file_path": "src/main.py",
            "context": {
                "file_path": "src/main.py",
                "line_number": 10,
                "position": 5,
            },
        }

        result = self.processor.add_rule_extraction_task(rule_data)

        assert result is True
        assert self.processor.task_queue.qsize() == 1

        # Clean up
        self.processor.stop_workers()

    def test_add_statistics_update_task(self) -> None:
        """Test adding statistics update task."""
        # Start workers
        self.processor.start_workers()

        stats_data = {
            "rule_id": 1,
            "repository_id": 1,
            "confidence_score": 0.85,
        }

        result = self.processor.add_statistics_update_task(stats_data)

        assert result is True
        assert self.processor.task_queue.qsize() == 1

        # Clean up
        self.processor.stop_workers()

    def test_validate_review_comment_valid(self) -> None:
        """Test validating valid review comment."""
        comment_data = {
            "id": 1,
            "body": "This code needs improvement",
            "path": "src/main.py",
            "position": 5,
        }

        result = self.processor._validate_review_comment(comment_data)

        assert result is True

    def test_validate_review_comment_invalid(self) -> None:
        """Test validating invalid review comment."""
        # Missing required field
        comment_data = {
            "id": 1,
            "body": "This code needs improvement",
            "path": "src/main.py",
            # Missing 'position'
        }

        result = self.processor._validate_review_comment(comment_data)

        assert result is False

    def test_validate_code_snippet_valid(self) -> None:
        """Test validating valid code snippet."""
        snippet_data = {
            "id": 1,
            "content": "def test():\n    pass",
            "file_path": "src/main.py",
            "line_start": 10,
            "line_end": 11,
        }

        result = self.processor._validate_code_snippet(snippet_data)

        assert result is True

    def test_validate_code_snippet_invalid(self) -> None:
        """Test validating invalid code snippet."""
        # Invalid line numbers
        snippet_data = {
            "id": 1,
            "content": "def test():\n    pass",
            "file_path": "src/main.py",
            "line_start": 11,
            "line_end": 10,  # Invalid: end < start
        }

        result = self.processor._validate_code_snippet(snippet_data)

        assert result is False

    def test_validate_comment_thread_valid(self) -> None:
        """Test validating valid comment thread."""
        thread_data = {
            "id": 1,
            "thread_path": "src/main.py",
            "thread_position": 5,
        }

        result = self.processor._validate_comment_thread(thread_data)

        assert result is True

    def test_validate_comment_thread_invalid(self) -> None:
        """Test validating invalid comment thread."""
        # Missing required field
        thread_data = {
            "id": 1,
            "thread_path": "src/main.py",
            # Missing 'thread_position'
        }

        result = self.processor._validate_comment_thread(thread_data)

        assert result is False

    def test_extract_rule_from_text_imperative(self) -> None:
        """Test extracting rule from imperative sentence."""
        text = "Use meaningful variable names instead of single letters."

        result = self.processor._extract_rule_from_text(text)

        assert result is not None
        assert "Use meaningful variable names" in result

    def test_extract_rule_from_text_pattern(self) -> None:
        """Test extracting rule from pattern."""
        text = "You should always validate user input."

        result = self.processor._extract_rule_from_text(text)

        assert result is not None
        assert "Should always validate user input" in result

    def test_extract_rule_from_text_no_rule(self) -> None:
        """Test extracting rule when no rule is present."""
        text = "This is just a comment without any specific rule."

        result = self.processor._extract_rule_from_text(text)

        assert result is None

    def test_extract_rule_from_text_empty(self) -> None:
        """Test extracting rule from empty text."""
        text = ""

        result = self.processor._extract_rule_from_text(text)

        assert result is None

    def test_categorize_rule_naming(self) -> None:
        """Test categorizing naming rule."""
        rule_text = "Use meaningful variable names"

        result = self.processor._categorize_rule(rule_text)

        assert result == "naming"

    def test_categorize_rule_performance(self) -> None:
        """Test categorizing performance rule."""
        rule_text = "Optimize for better performance and speed"

        result = self.processor._categorize_rule(rule_text)

        assert result == "performance"

    def test_categorize_rule_general(self) -> None:
        """Test categorizing general rule."""
        rule_text = "Make sure the code is clean and readable"

        result = self.processor._categorize_rule(rule_text)

        assert result == "readability"

    def test_assess_severity_critical(self) -> None:
        """Test assessing critical severity."""
        rule_text = "This is a critical security vulnerability that must be fixed immediately"

        result = self.processor._assess_severity(rule_text)

        assert result == "critical"

    def test_assess_severity_high(self) -> None:
        """Test assessing high severity."""
        rule_text = "This is an important issue that needs attention"

        result = self.processor._assess_severity(rule_text)

        assert result == "high"

    def test_assess_severity_medium(self) -> None:
        """Test assessing medium severity."""
        rule_text = "You should follow the coding conventions"

        result = self.processor._assess_severity(rule_text)

        assert result == "medium"

    def test_assess_severity_default(self) -> None:
        """Test assessing default severity."""
        rule_text = "This is a simple suggestion"

        result = self.processor._assess_severity(rule_text)

        assert result == "low"

    def test_calculate_confidence_with_context(self) -> None:
        """Test calculating confidence with context."""
        rule_text = "Use meaningful variable names"
        context = {
            "file_path": "src/main.py",
            "line_number": 10,
            "has_code_snippets": True,
            "author": "developer",
        }

        result = self.processor._calculate_confidence(rule_text, context)

        assert result >= 0.5  # Base confidence
        assert result <= 1.0  # Maximum confidence

    def test_calculate_confidence_minimal_context(self) -> None:
        """Test calculating confidence with minimal context."""
        rule_text = "Use meaningful variable names"
        context = {}

        result = self.processor._calculate_confidence(rule_text, context)

        assert result == 0.5  # Base confidence

    def test_get_processing_stats(self) -> None:
        """Test getting processing statistics."""
        # Add some tasks
        self.processor.add_review_comment_task({"id": 1, "body": "test", "path": "test.py", "position": 1})
        self.processor.add_code_snippet_task({
            "id": 1,
            "content": "test",
            "file_path": "test.py",
            "line_start": 1,
            "line_end": 2,
        })

        stats = self.processor.get_processing_stats()

        assert "processed_count" in stats
        assert "error_count" in stats
        assert "queue_size" in stats
        assert "worker_count" in stats
        assert "is_running" in stats
        assert stats["queue_size"] == 2

    def test_process_batch(self) -> None:
        """Test processing batch of items."""
        items = [
            {"id": 1, "body": "test", "path": "test.py", "position": 1},
            {"id": 2, "body": "test", "path": "test.py", "position": 2},
        ]

        # Start workers
        self.processor.start_workers()

        results = self.processor.process_batch(items, "process_review_comment")

        assert results["total"] == 2
        assert "start_time" in results
        assert "end_time" in results

        # Clean up
        self.processor.stop_workers()

    def test_process_review_comments_batch(self) -> None:
        """Test processing batch of review comments."""
        comments = [
            {"id": 1, "body": "test", "path": "test.py", "position": 1},
            {"id": 2, "body": "test", "path": "test.py", "position": 2},
        ]

        # Start workers
        self.processor.start_workers()

        results = self.processor.process_review_comments_batch(comments)

        assert results["total"] == 2
        assert results["success"] == 2

        # Clean up
        self.processor.stop_workers()

    def test_process_code_snippets_batch(self) -> None:
        """Test processing batch of code snippets."""
        snippets = [
            {"id": 1, "content": "test", "file_path": "test.py", "line_start": 1, "line_end": 2},
            {"id": 2, "content": "test", "file_path": "test.py", "line_start": 3, "line_end": 4},
        ]

        # Start workers
        self.processor.start_workers()

        results = self.processor.process_code_snippets_batch(snippets)

        assert results["total"] == 2
        assert results["success"] == 2

        # Clean up
        self.processor.stop_workers()

    def test_process_comment_threads_batch(self) -> None:
        """Test processing batch of comment threads."""
        threads = [
            {"id": 1, "thread_path": "test.py", "thread_position": 1},
            {"id": 2, "thread_path": "test.py", "thread_position": 2},
        ]

        # Start workers
        self.processor.start_workers()

        results = self.processor.process_comment_threads_batch(threads)

        assert results["total"] == 2
        assert results["success"] == 2

        # Clean up
        self.processor.stop_workers()

    def test_worker_error_handling(self) -> None:
        """Test error handling in worker threads."""
        # Start workers
        self.processor.start_workers()

        # Add invalid task that will cause error
        invalid_task = {"type": "invalid_task", "data": {}}
        self.processor.task_queue.put(invalid_task)

        # Wait for task to be processed
        time.sleep(1)

        # Check that error count increased
        stats = self.processor.get_processing_stats()
        assert stats["error_count"] > 0

        # Clean up
        self.processor.stop_workers()

    def test_concurrent_processing(self) -> None:
        """Test concurrent processing of multiple tasks."""
        # Start workers
        self.processor.start_workers()

        # Add multiple tasks
        tasks = []
        for i in range(10):
            task = {
                "type": "process_review_comment",
                "data": {
                    "id": i,
                    "body": f"Test comment {i}",
                    "path": "test.py",
                    "position": i,
                },
            }
            tasks.append(task)
            self.processor.task_queue.put(task)

        # Wait for all tasks to complete
        self.processor.task_queue.join()

        # Check that all tasks were processed
        stats = self.processor.get_processing_stats()
        assert stats["processed_count"] >= 10

        # Clean up
        self.processor.stop_workers()

    def test_task_queue_timeout(self) -> None:
        """Test task queue timeout handling."""
        # Don't start workers
        # Add task and check timeout
        task = {
            "type": "process_review_comment",
            "data": {
                "id": 1,
                "body": "Test comment",
                "path": "test.py",
                "position": 1,
            },
        }

        # This should not raise an exception even without workers
        result = self.processor.task_queue.put(task)
        assert result is None

        # Queue should have the task
        assert self.processor.task_queue.qsize() == 1
