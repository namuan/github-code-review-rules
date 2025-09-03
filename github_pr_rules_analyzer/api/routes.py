"""FastAPI routes for the GitHub PR Rules Analyzer."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from github_pr_rules_analyzer.models import ExtractedRule, PullRequest, Repository, ReviewComment
from github_pr_rules_analyzer.services.data_collector import DataCollector
from github_pr_rules_analyzer.services.data_processor import DataProcessor
from github_pr_rules_analyzer.services.llm_service import LLMService
from github_pr_rules_analyzer.utils import get_logger
from github_pr_rules_analyzer.utils.database import get_session_local

logger = get_logger(__name__)
router = APIRouter()


# Dependency to get database session
def get_db() -> Session:
    """Get database session."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()


# Dependency to get services
def get_services() -> dict[str, Any]:
    """Get service instances."""
    return {
        "data_collector": DataCollector(),
        "data_processor": DataProcessor(),
        "llm_service": LLMService(),
    }


@router.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint."""
    return {
        "message": "GitHub PR Rules Analyzer API",
        "version": "1.0.0",
        "endpoints": {
            "repositories": "/repositories",
            "rules": "/rules",
            "dashboard": "/dashboard",
            "sync": "/sync",
        },
    }


# Repository Management Endpoints
@router.get("/repositories")
async def get_repositories(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get all repositories."""
    try:
        repositories = db.query(Repository).offset(skip).limit(limit).all()
        total = db.query(Repository).count()

        return {
            "repositories": [repo.to_dict() for repo in repositories],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        logger.exception("Error getting repositories")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/repositories")
async def add_repository(
    repo_data: dict[str, Any],
    services: Annotated[dict[str, Any], Depends(get_services)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Add a new repository for monitoring."""
    try:
        # Validate repository data
        required_fields = ["owner", "name"]
        for field in required_fields:
            if field not in repo_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Check if repository already exists
        existing_repo = (
            db.query(Repository)
            .filter(
                Repository.full_name == f"{repo_data['owner']}/{repo_data['name']}",
            )
            .first()
        )

        if existing_repo:
            raise HTTPException(status_code=400, detail="Repository already exists")

        # Validate repository access
        data_collector = services["data_collector"]
        validation_result = data_collector.validate_repository_access(
            repo_data["owner"],
            repo_data["name"],
        )

        if not validation_result["success"]:
            raise HTTPException(status_code=400, detail=validation_result["message"])

        # Create repository
        repo_info = data_collector.get_repository_info(repo_data["owner"], repo_data["name"])
        repository = Repository.from_github_data(repo_info["info"])

        db.add(repository)
        db.commit()
        db.refresh(repository)

        return {
            "message": "Repository added successfully",
            "repository": repository.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error adding repository")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/repositories/{repo_id}")
async def delete_repository(
    repo_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a repository."""
    try:
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Delete repository (cascade will handle related data)
        db.delete(repository)
        db.commit()

        return {"message": "Repository deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting repository")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Data Collection Endpoints
@router.post("/sync")
async def sync_all_repositories(
    services: dict[str, Any] = Depends(get_services),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Sync all repositories."""
    try:
        # Get all repositories
        repositories = db.query(Repository).all()

        if not repositories:
            return {
                "message": "No repositories to sync",
                "synced_count": 0,
            }

        # Sync each repository
        synced_count = 0
        errors = []

        data_collector = services["data_collector"]
        data_processor = services["data_processor"]

        for repository in repositories:
            try:
                # Collect repository data
                results = data_collector.collect_repository_data(
                    repository.owner_login,
                    repository.name,
                )

                # Process collected data
                # Process review comments
                if results["review_comments"]:
                    data_processor.process_review_comments_batch(results["review_comments"])

                # Process code snippets
                if results["code_snippets"]:
                    data_processor.process_code_snippets_batch(results["code_snippets"])

                # Process comment threads
                if results["comment_threads"]:
                    data_processor.process_comment_threads_batch(results["comment_threads"])

                synced_count += 1

            except Exception as e:
                error_msg = f"Error syncing repository {repository.full_name}: {e!s}"
                logger.exception(error_msg)
                errors.append(error_msg)

        return {
            "message": f"Sync completed for {synced_count} repositories",
            "synced_count": synced_count,
            "total_repositories": len(repositories),
            "errors": errors,
        }

    except Exception as e:
        logger.exception("Error syncing all repositories")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/sync/{repo_id}")
async def sync_repository(
    repo_id: Annotated[int, Path(ge=1)],
    services: dict[str, Any] = Depends(get_services),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Sync repository data."""
    try:
        # Check if repository exists
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")

        data_collector = services["data_collector"]

        # Collect repository data
        results = data_collector.collect_repository_data(
            repository.owner_login,
            repository.name,
        )

        # Process collected data
        data_processor = services["data_processor"]

        # Process review comments
        if results["review_comments"]:
            data_processor.process_review_comments_batch(results["review_comments"])

        # Process code snippets
        if results["code_snippets"]:
            data_processor.process_code_snippets_batch(results["code_snippets"])

        # Process comment threads
        if results["comment_threads"]:
            data_processor.process_comment_threads_batch(results["comment_threads"])

        return {
            "message": "Repository sync completed",
            "results": results,
            "processed_comments": len(results["review_comments"]),
            "processed_snippets": len(results["code_snippets"]),
            "processed_threads": len(results["comment_threads"]),
            "errors": results["errors"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error syncing repository")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/sync/status")
async def get_sync_status(
    services: Annotated[dict[str, Any], Depends(get_services)],
) -> dict[str, Any]:
    """Get sync status."""
    try:
        data_processor = services["data_processor"]
        stats = data_processor.get_processing_stats()

        return {
            "processing_stats": stats,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.exception("Error getting sync status")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Rule Extraction Endpoints
@router.post("/rules/extract")
async def extract_rules(
    comment_ids: list[int],
    services: Annotated[dict[str, Any], Depends(get_services)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Extract rules from review comments."""
    try:
        # Get review comments
        comments = []
        for comment_id in comment_ids:
            comment = db.query(ReviewComment).filter(ReviewComment.id == comment_id).first()
            if not comment:
                continue

            comment_data = {
                "review_comment_id": comment.id,
                "body": comment.body,
                "file_path": comment.path,
                "line_number": comment.line,
                "pr_title": comment.pull_request.title,
                "repository_name": comment.pull_request.repository.full_name,
                "context": {
                    "file_path": comment.path,
                    "line_number": comment.line,
                    "position": comment.position,
                    "pr_title": comment.pull_request.title,
                    "pr_number": comment.pull_request.number,
                    "repository_name": comment.pull_request.repository.full_name,
                    "author": comment.author_login,
                    "comment_length": len(comment.body),
                    "has_code_snippets": len(comment.code_snippets) > 0,
                },
            }
            comments.append(comment_data)

        if not comments:
            raise HTTPException(status_code=404, detail="No valid comments found")

        # Extract rules using LLM
        llm_service = services["llm_service"]
        extracted_rules = llm_service.extract_rules_from_comments_batch(comments)

        # Save rules to database
        saved_rules = []
        for rule_data in extracted_rules:
            rule = ExtractedRule(
                review_comment_id=rule_data["review_comment_id"],
                rule_text=rule_data["rule_text"],
                rule_category=rule_data["rule_category"],
                rule_severity=rule_data["rule_severity"],
                confidence_score=rule_data["confidence_score"],
                llm_model=rule_data["llm_model"],
                prompt_used=rule_data["prompt_used"],
                response_raw=rule_data["response_raw"],
                is_valid=rule_data["is_valid"],
            )

            db.add(rule)
            saved_rules.append(rule)

        db.commit()

        return {
            "message": "Rules extracted successfully",
            "extracted_count": len(saved_rules),
            "rules": [rule.to_dict() for rule in saved_rules],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error extracting rules")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Rule Management Endpoints
@router.get("/rules")
async def get_rules(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    category: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    repository_id: Annotated[int | None, Query()] = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get all rules with filtering."""
    try:
        query = db.query(ExtractedRule)

        # Apply filters
        if category:
            query = query.filter(ExtractedRule.rule_category == category)
        if severity:
            query = query.filter(ExtractedRule.rule_severity == severity)
        if repository_id:
            query = (
                query.join(ReviewComment)
                .join(PullRequest)
                .filter(
                    PullRequest.repository_id == repository_id,
                )
            )

        rules = query.offset(skip).limit(limit).all()
        total = query.count()

        return {
            "rules": [rule.to_dict() for rule in rules],
            "total": total,
            "skip": skip,
            "limit": limit,
            "filters": {
                "category": category,
                "severity": severity,
                "repository_id": repository_id,
            },
        }

    except Exception as e:
        logger.exception("Error getting rules")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get a specific rule."""
    try:
        rule = db.query(ExtractedRule).filter(ExtractedRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        return rule.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting rule")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/rules/search")
async def search_rules(
    query: Annotated[str, Query(min_length=1)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Search rules by text."""
    try:
        # Simple text search in rule_text and explanation
        rules = (
            db.query(ExtractedRule)
            .filter(
                ExtractedRule.rule_text.ilike(f"%{query}%") | ExtractedRule.explanation.ilike(f"%{query}%"),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        total = (
            db.query(ExtractedRule)
            .filter(
                ExtractedRule.rule_text.ilike(f"%{query}%") | ExtractedRule.explanation.ilike(f"%{query}%"),
            )
            .count()
        )

        return {
            "rules": [rule.to_dict() for rule in rules],
            "total": total,
            "skip": skip,
            "limit": limit,
            "query": query,
        }

    except Exception as e:
        logger.exception("Error searching rules")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Statistics and Analytics Endpoints
@router.get("/rules/categories")
async def get_rule_categories(db: Annotated[Session, Depends(get_db)]) -> dict[str, list[str]]:
    """Get all rule categories."""
    try:
        categories = db.query(ExtractedRule.rule_category).distinct().all()
        return {
            "categories": [cat[0] for cat in categories if cat[0]],
        }
    except Exception as e:
        logger.exception("Error getting categories")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/rules/severities")
async def get_rule_severities(db: Annotated[Session, Depends(get_db)]) -> dict[str, list[str]]:
    """Get all rule severities."""
    try:
        severities = db.query(ExtractedRule.rule_severity).distinct().all()
        return {
            "severities": [sev[0] for sev in severities if sev[0]],
        }
    except Exception as e:
        logger.exception("Error getting severities")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/rules/statistics")
async def get_rule_statistics(
    repository_id: Annotated[int | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get rule statistics."""
    try:
        # Get basic statistics
        query = db.query(ExtractedRule)

        if repository_id:
            query = (
                query.join(ReviewComment)
                .join(PullRequest)
                .filter(
                    PullRequest.repository_id == repository_id,
                )
            )
        if category:
            query = query.filter(ExtractedRule.rule_category == category)
        if severity:
            query = query.filter(ExtractedRule.rule_severity == severity)

        total_rules = query.count()

        # Get category distribution
        category_query = db.query(ExtractedRule.rule_category, db.func.count(ExtractedRule.id))
        if repository_id:
            category_query = (
                category_query.join(ReviewComment).join(PullRequest).filter(PullRequest.repository_id == repository_id)
            )
        if category:
            category_query = category_query.filter(ExtractedRule.rule_category == category)
        if severity:
            category_query = category_query.filter(ExtractedRule.rule_severity == severity)
        category_stats = dict(category_query.group_by(ExtractedRule.rule_category).all())

        # Get severity distribution
        severity_query = db.query(ExtractedRule.rule_severity, db.func.count(ExtractedRule.id))
        if repository_id:
            severity_query = (
                severity_query.join(ReviewComment).join(PullRequest).filter(PullRequest.repository_id == repository_id)
            )
        if category:
            severity_query = severity_query.filter(ExtractedRule.rule_category == category)
        if severity:
            severity_query = severity_query.filter(ExtractedRule.rule_severity == severity)
        severity_stats = dict(severity_query.group_by(ExtractedRule.rule_severity).all())

        # Get average confidence
        avg_confidence = db.query(db.func.avg(ExtractedRule.confidence_score)).scalar() or 0

        return {
            "total_rules": total_rules,
            "category_distribution": category_stats,
            "severity_distribution": severity_stats,
            "average_confidence": round(avg_confidence, 2),
            "filters": {
                "repository_id": repository_id,
                "category": category,
                "severity": severity,
            },
        }

    except Exception as e:
        logger.exception("Error getting statistics")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Dashboard Endpoints
@router.get("/dashboard")
async def get_dashboard_data(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Get dashboard data."""
    try:
        # Repository statistics
        total_repos = db.query(Repository).count()
        active_repos = db.query(Repository).filter(Repository.is_active).count()

        # PR statistics
        total_prs = db.query(PullRequest).count()
        closed_prs = db.query(PullRequest).filter(PullRequest.state == "closed").count()

        # Comment statistics
        total_comments = db.query(ReviewComment).count()

        # Rule statistics
        total_rules = db.query(ExtractedRule).count()
        valid_rules = db.query(ExtractedRule).filter(ExtractedRule.is_valid).count()

        # Recent activity
        recent_rules = (
            db.query(ExtractedRule)
            .order_by(
                ExtractedRule.created_at.desc(),
            )
            .limit(10)
            .all()
        )

        # Top categories
        top_categories = (
            db.query(
                ExtractedRule.rule_category,
                db.func.count(ExtractedRule.id),
            )
            .group_by(ExtractedRule.rule_category)
            .order_by(
                db.func.count(ExtractedRule.id).desc(),
            )
            .limit(5)
            .all()
        )

        return {
            "repositories": {
                "total": total_repos,
                "active": active_repos,
            },
            "pull_requests": {
                "total": total_prs,
                "closed": closed_prs,
            },
            "review_comments": {
                "total": total_comments,
            },
            "rules": {
                "total": total_rules,
                "valid": valid_rules,
            },
            "recent_rules": [rule.to_dict() for rule in recent_rules],
            "top_categories": {cat[0]: cat[1] for cat in top_categories},
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.exception("Error getting dashboard data")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# PR Detail Endpoints
@router.get("/pull-requests/{pr_id}")
async def get_pull_request(
    pr_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get pull request details."""
    try:
        pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
        if not pr:
            raise HTTPException(status_code=404, detail="Pull request not found")

        # Get related comments
        comments = (
            db.query(ReviewComment)
            .filter(
                ReviewComment.pull_request_id == pr_id,
            )
            .all()
        )

        # Get related rules
        rules = (
            db.query(ExtractedRule)
            .join(
                ReviewComment,
            )
            .filter(
                ReviewComment.pull_request_id == pr_id,
            )
            .all()
        )

        return {
            "pull_request": pr.to_dict(),
            "comments": [comment.to_dict() for comment in comments],
            "rules": [rule.to_dict() for rule in rules],
            "comment_count": len(comments),
            "rule_count": len(rules),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting pull request")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Repository-specific Endpoints
@router.get("/repositories/{repo_id}/rules")
async def get_repository_rules(
    repo_id: Annotated[int, Path(ge=1)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    category: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get rules for a specific repository."""
    try:
        # Check if repository exists
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Get rules for this repository
        query = (
            db.query(ExtractedRule)
            .join(
                ReviewComment,
            )
            .join(
                PullRequest,
            )
            .filter(
                PullRequest.repository_id == repo_id,
            )
        )

        # Apply filters
        if category:
            query = query.filter(ExtractedRule.rule_category == category)
        if severity:
            query = query.filter(ExtractedRule.rule_severity == severity)

        rules = query.offset(skip).limit(limit).all()
        total = query.count()

        return {
            "repository": repository.to_dict(),
            "rules": [rule.to_dict() for rule in rules],
            "total": total,
            "skip": skip,
            "limit": limit,
            "filters": {
                "category": category,
                "severity": severity,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting repository rules")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/repositories/{repo_id}/statistics")
async def get_repository_statistics(
    repo_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get statistics for a specific repository."""
    try:
        # Check if repository exists
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Get PR statistics
        total_prs = (
            db.query(PullRequest)
            .filter(
                PullRequest.repository_id == repo_id,
            )
            .count()
        )

        closed_prs = (
            db.query(PullRequest)
            .filter(
                PullRequest.repository_id == repo_id,
                PullRequest.state == "closed",
            )
            .count()
        )

        # Get comment statistics
        total_comments = (
            db.query(ReviewComment)
            .join(
                PullRequest,
            )
            .filter(
                PullRequest.repository_id == repo_id,
            )
            .count()
        )

        # Get rule statistics
        total_rules = (
            db.query(ExtractedRule)
            .join(
                ReviewComment,
            )
            .join(
                PullRequest,
            )
            .filter(
                PullRequest.repository_id == repo_id,
            )
            .count()
        )

        # Get category distribution
        category_stats = (
            db.query(
                ExtractedRule.rule_category,
                db.func.count(ExtractedRule.id),
            )
            .join(
                ReviewComment,
            )
            .join(
                PullRequest,
            )
            .filter(
                PullRequest.repository_id == repo_id,
            )
            .group_by(
                ExtractedRule.rule_category,
            )
            .all()
        )

        return {
            "repository": repository.to_dict(),
            "pull_requests": {
                "total": total_prs,
                "closed": closed_prs,
            },
            "review_comments": {
                "total": total_comments,
            },
            "rules": {
                "total": total_rules,
            },
            "category_distribution": {cat[0]: cat[1] for cat in category_stats},
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting repository statistics")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Health Check Endpoint
@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0",
    }
