"""
FastAPI routes for the GitHub PR Rules Analyzer
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from ..utils.database import get_session_local
from ..models import Repository, PullRequest, ReviewComment, ExtractedRule, RuleStatistics
from ..services.data_collector import DataCollector
from ..services.data_processor import DataProcessor
from ..services.llm_service import LLMService
from ..utils import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Dependency to get database session
def get_db():
    """Get database session"""
    db = get_session_local()
    try:
        yield db
    finally:
        db.close()

# Dependency to get services
def get_services():
    """Get service instances"""
    return {
        'data_collector': DataCollector(),
        'data_processor': DataProcessor(),
        'llm_service': LLMService()
    }

@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GitHub PR Rules Analyzer API",
        "version": "1.0.0",
        "endpoints": {
            "repositories": "/api/v1/repositories",
            "rules": "/api/v1/rules",
            "dashboard": "/api/v1/dashboard",
            "sync": "/api/v1/sync"
        }
    }

# Repository Management Endpoints
@router.get("/api/v1/repositories")
async def get_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get all repositories"""
    try:
        repositories = db.query(Repository).offset(skip).limit(limit).all()
        total = db.query(Repository).count()
        
        return {
            "repositories": [repo.to_dict() for repo in repositories],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting repositories: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/api/v1/repositories")
async def add_repository(
    repo_data: Dict[str, Any],
    services: Dict[str, Any] = Depends(get_services),
    db: Session = Depends(get_db)
):
    """Add a new repository for monitoring"""
    try:
        # Validate repository data
        required_fields = ['owner', 'name']
        for field in required_fields:
            if field not in repo_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Check if repository already exists
        existing_repo = db.query(Repository).filter(
            Repository.full_name == f"{repo_data['owner']}/{repo_data['name']}"
        ).first()
        
        if existing_repo:
            raise HTTPException(status_code=400, detail="Repository already exists")
        
        # Validate repository access
        data_collector = services['data_collector']
        validation_result = data_collector.validate_repository_access(
            repo_data['owner'], 
            repo_data['name']
        )
        
        if not validation_result['success']:
            raise HTTPException(status_code=400, detail=validation_result['message'])
        
        # Create repository
        repo_info = data_collector.get_repository_info(repo_data['owner'], repo_data['name'])
        repository = Repository.from_github_data(repo_info['info'])
        
        db.add(repository)
        db.commit()
        db.refresh(repository)
        
        return {
            "message": "Repository added successfully",
            "repository": repository.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding repository: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/api/v1/repositories/{repo_id}")
async def delete_repository(
    repo_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
):
    """Delete a repository"""
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
        logger.error(f"Error deleting repository: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Data Collection Endpoints
@router.post("/api/v1/sync/{repo_id}")
async def sync_repository(
    repo_id: int = Path(..., ge=1),
    services: Dict[str, Any] = Depends(get_services),
    db: Session = Depends(get_db)
):
    """Sync repository data"""
    try:
        # Check if repository exists
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        data_collector = services['data_collector']
        
        # Collect repository data
        results = data_collector.collect_repository_data(
            repository.owner_login,
            repository.name
        )
        
        # Process collected data
        data_processor = services['data_processor']
        
        # Process review comments
        if results['review_comments']:
            comments_batch = data_processor.process_review_comments_batch(results['review_comments'])
        
        # Process code snippets
        if results['code_snippets']:
            snippets_batch = data_processor.process_code_snippets_batch(results['code_snippets'])
        
        # Process comment threads
        if results['comment_threads']:
            threads_batch = data_processor.process_comment_threads_batch(results['comment_threads'])
        
        return {
            "message": "Repository sync completed",
            "results": results,
            "processed_comments": len(results['review_comments']),
            "processed_snippets": len(results['code_snippets']),
            "processed_threads": len(results['comment_threads']),
            "errors": results['errors']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing repository: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/api/v1/sync/status")
async def get_sync_status(
    services: Dict[str, Any] = Depends(get_services)
):
    """Get sync status"""
    try:
        data_processor = services['data_processor']
        stats = data_processor.get_processing_stats()
        
        return {
            "processing_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Rule Extraction Endpoints
@router.post("/api/v1/rules/extract")
async def extract_rules(
    comment_ids: List[int],
    services: Dict[str, Any] = Depends(get_services),
    db: Session = Depends(get_db)
):
    """Extract rules from review comments"""
    try:
        # Get review comments
        comments = []
        for comment_id in comment_ids:
            comment = db.query(ReviewComment).filter(ReviewComment.id == comment_id).first()
            if not comment:
                continue
            
            comment_data = {
                'review_comment_id': comment.id,
                'body': comment.body,
                'file_path': comment.path,
                'line_number': comment.line,
                'pr_title': comment.pull_request.title,
                'repository_name': comment.pull_request.repository.full_name,
                'context': {
                    'file_path': comment.path,
                    'line_number': comment.line,
                    'position': comment.position,
                    'pr_title': comment.pull_request.title,
                    'pr_number': comment.pull_request.number,
                    'repository_name': comment.pull_request.repository.full_name,
                    'author': comment.author_login,
                    'comment_length': len(comment.body),
                    'has_code_snippets': len(comment.code_snippets) > 0
                }
            }
            comments.append(comment_data)
        
        if not comments:
            raise HTTPException(status_code=404, detail="No valid comments found")
        
        # Extract rules using LLM
        llm_service = services['llm_service']
        extracted_rules = llm_service.extract_rules_from_comments_batch(comments)
        
        # Save rules to database
        saved_rules = []
        for rule_data in extracted_rules:
            rule = ExtractedRule(
                review_comment_id=rule_data['review_comment_id'],
                rule_text=rule_data['rule_text'],
                rule_category=rule_data['rule_category'],
                rule_severity=rule_data['rule_severity'],
                confidence_score=rule_data['confidence_score'],
                llm_model=rule_data['llm_model'],
                prompt_used=rule_data['prompt_used'],
                response_raw=rule_data['response_raw'],
                is_valid=rule_data['is_valid']
            )
            
            db.add(rule)
            saved_rules.append(rule)
        
        db.commit()
        
        return {
            "message": "Rules extracted successfully",
            "extracted_count": len(saved_rules),
            "rules": [rule.to_dict() for rule in saved_rules]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting rules: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Rule Management Endpoints
@router.get("/api/v1/rules")
async def get_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    repository_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get all rules with filtering"""
    try:
        query = db.query(ExtractedRule)
        
        # Apply filters
        if category:
            query = query.filter(ExtractedRule.rule_category == category)
        if severity:
            query = query.filter(ExtractedRule.rule_severity == severity)
        if repository_id:
            query = query.join(ReviewComment).join(PullRequest).filter(
                PullRequest.repository_id == repository_id
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
                "repository_id": repository_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting rules: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/api/v1/rules/{rule_id}")
async def get_rule(
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
):
    """Get a specific rule"""
    try:
        rule = db.query(ExtractedRule).filter(ExtractedRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        return rule.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/api/v1/rules/search")
async def search_rules(
    query: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Search rules by text"""
    try:
        # Simple text search in rule_text and explanation
        rules = db.query(ExtractedRule).filter(
            ExtractedRule.rule_text.ilike(f"%{query}%") |
            ExtractedRule.explanation.ilike(f"%{query}%")
        ).offset(skip).limit(limit).all()
        
        total = db.query(ExtractedRule).filter(
            ExtractedRule.rule_text.ilike(f"%{query}%") |
            ExtractedRule.explanation.ilike(f"%{query}%")
        ).count()
        
        return {
            "rules": [rule.to_dict() for rule in rules],
            "total": total,
            "skip": skip,
            "limit": limit,
            "query": query
        }
        
    except Exception as e:
        logger.error(f"Error searching rules: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Statistics and Analytics Endpoints
@router.get("/api/v1/rules/categories")
async def get_rule_categories(db: Session = Depends(get_db)):
    """Get all rule categories"""
    try:
        categories = db.query(ExtractedRule.rule_category).distinct().all()
        return {
            "categories": [cat[0] for cat in categories if cat[0]]
        }
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/api/v1/rules/severities")
async def get_rule_severities(db: Session = Depends(get_db)):
    """Get all rule severities"""
    try:
        severities = db.query(ExtractedRule.rule_severity).distinct().all()
        return {
            "severities": [sev[0] for sev in severities if sev[0]]
        }
    except Exception as e:
        logger.error(f"Error getting severities: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/api/v1/rules/statistics")
async def get_rule_statistics(
    repository_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get rule statistics"""
    try:
        # Get basic statistics
        query = db.query(ExtractedRule)
        
        if repository_id:
            query = query.join(ReviewComment).join(PullRequest).filter(
                PullRequest.repository_id == repository_id
            )
        if category:
            query = query.filter(ExtractedRule.rule_category == category)
        if severity:
            query = query.filter(ExtractedRule.rule_severity == severity)
        
        total_rules = query.count()
        
        # Get category distribution
        category_stats = {}
        categories = db.query(
            ExtractedRule.rule_category,
            db.func.count(ExtractedRule.id)
        ).group_by(ExtractedRule.rule_category).all()
        
        for cat, count in categories:
            category_stats[cat] = count
        
        # Get severity distribution
        severity_stats = {}
        severities = db.query(
            ExtractedRule.rule_severity,
            db.func.count(ExtractedRule.id)
        ).group_by(ExtractedRule.rule_severity).all()
        
        for sev, count in severities:
            severity_stats[sev] = count
        
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
                "severity": severity
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Dashboard Endpoints
@router.get("/api/v1/dashboard")
async def get_dashboard_data(
    db: Session = Depends(get_db)
):
    """Get dashboard data"""
    try:
        # Repository statistics
        total_repos = db.query(Repository).count()
        active_repos = db.query(Repository).filter(Repository.is_active == True).count()
        
        # PR statistics
        total_prs = db.query(PullRequest).count()
        closed_prs = db.query(PullRequest).filter(PullRequest.state == 'closed').count()
        
        # Comment statistics
        total_comments = db.query(ReviewComment).count()
        
        # Rule statistics
        total_rules = db.query(ExtractedRule).count()
        valid_rules = db.query(ExtractedRule).filter(ExtractedRule.is_valid == True).count()
        
        # Recent activity
        recent_rules = db.query(ExtractedRule).order_by(
            ExtractedRule.created_at.desc()
        ).limit(10).all()
        
        # Top categories
        top_categories = db.query(
            ExtractedRule.rule_category,
            db.func.count(ExtractedRule.id)
        ).group_by(ExtractedRule.rule_category).order_by(
            db.func.count(ExtractedRule.id).desc()
        ).limit(5).all()
        
        return {
            "repositories": {
                "total": total_repos,
                "active": active_repos
            },
            "pull_requests": {
                "total": total_prs,
                "closed": closed_prs
            },
            "review_comments": {
                "total": total_comments
            },
            "rules": {
                "total": total_rules,
                "valid": valid_rules
            },
            "recent_rules": [rule.to_dict() for rule in recent_rules],
            "top_categories": {cat[0]: cat[1] for cat in top_categories},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# PR Detail Endpoints
@router.get("/api/v1/pull-requests/{pr_id}")
async def get_pull_request(
    pr_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
):
    """Get pull request details"""
    try:
        pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
        if not pr:
            raise HTTPException(status_code=404, detail="Pull request not found")
        
        # Get related comments
        comments = db.query(ReviewComment).filter(
            ReviewComment.pull_request_id == pr_id
        ).all()
        
        # Get related rules
        rules = db.query(ExtractedRule).join(
            ReviewComment
        ).filter(
            ReviewComment.pull_request_id == pr_id
        ).all()
        
        return {
            "pull_request": pr.to_dict(),
            "comments": [comment.to_dict() for comment in comments],
            "rules": [rule.to_dict() for rule in rules],
            "comment_count": len(comments),
            "rule_count": len(rules)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pull request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Repository-specific Endpoints
@router.get("/api/v1/repositories/{repo_id}/rules")
async def get_repository_rules(
    repo_id: int = Path(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get rules for a specific repository"""
    try:
        # Check if repository exists
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Get rules for this repository
        query = db.query(ExtractedRule).join(
            ReviewComment
        ).join(
            PullRequest
        ).filter(
            PullRequest.repository_id == repo_id
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
                "severity": severity
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting repository rules: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/api/v1/repositories/{repo_id}/statistics")
async def get_repository_statistics(
    repo_id: int = Path(..., ge=1),
    db: Session = Depends(get_db)
):
    """Get statistics for a specific repository"""
    try:
        # Check if repository exists
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Get PR statistics
        total_prs = db.query(PullRequest).filter(
            PullRequest.repository_id == repo_id
        ).count()
        
        closed_prs = db.query(PullRequest).filter(
            PullRequest.repository_id == repo_id,
            PullRequest.state == 'closed'
        ).count()
        
        # Get comment statistics
        total_comments = db.query(ReviewComment).join(
            PullRequest
        ).filter(
            PullRequest.repository_id == repo_id
        ).count()
        
        # Get rule statistics
        total_rules = db.query(ExtractedRule).join(
            ReviewComment
        ).join(
            PullRequest
        ).filter(
            PullRequest.repository_id == repo_id
        ).count()
        
        # Get category distribution
        category_stats = db.query(
            ExtractedRule.rule_category,
            db.func.count(ExtractedRule.id)
        ).join(
            ReviewComment
        ).join(
            PullRequest
        ).filter(
            PullRequest.repository_id == repo_id
        ).group_by(
            ExtractedRule.rule_category
        ).all()
        
        return {
            "repository": repository.to_dict(),
            "pull_requests": {
                "total": total_prs,
                "closed": closed_prs
            },
            "review_comments": {
                "total": total_comments
            },
            "rules": {
                "total": total_rules
            },
            "category_distribution": {cat[0]: cat[1] for cat in category_stats},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting repository statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Health Check Endpoint
@router.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }