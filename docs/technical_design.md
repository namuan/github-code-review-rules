# Technical Design Document

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub API    │    │   LLM Service   │    │   Web UI        │
│                 │    │                 │    │                 │
│ - Authentication│    │ - OpenAI API    │    │ - React/Vue     │
│ - Rate Limiting │    │ - Rule Parsing  │    │ - Data Display  │
│ - Data Fetching │    │ - Response      │    │ - Search/Filter │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Backend API   │
                    │                 │
                    │ - FastAPI       │
                    │ - Data Processing│
                    │ - Business Logic│
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Database      │
                    │                 │
                    │ - PostgreSQL    │
                    │ - Data Models   │
                    │ - Indexes       │
                    └─────────────────┘
```

### 1.2 Component Overview

#### 1.2.1 Data Collector Service

- **Technology**: Python with FastAPI
- **Responsibilities**: GitHub API integration, data fetching, initial validation
- **Key Features**:
  - OAuth authentication with GitHub
  - Rate limiting handling
  - Pagination support
  - Error retry mechanisms

#### 1.2.2 Data Analysis Service

- **Technology**: Python with FastAPI
- **Responsibilities**: LLM integration, rule extraction, data processing
- **Key Features**:
  - OpenAI API integration
  - Prompt engineering for rule extraction
  - Response parsing and validation
  - Rule categorization

#### 1.2.3 Web UI Service

- **Technology**: HTML/CSS/JavaScript
- **Responsibilities**: User interface, data visualization, user interaction
- **Key Features**:
  - Dashboard view
  - Rule browsing and search
  - PR detail view

#### 1.2.4 Database Layer

- **Technology**: SQLite
- **Responsibilities**: Data persistence, querying, indexing
- **Key Features**:
  - Structured data storage
  - Efficient querying
  - Data integrity constraints
  - Backup and recovery

## 2. Data Models

### 2.1 Database Schema

#### 2.1.1 Repository Table

```sql
CREATE TABLE repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    github_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    owner_login VARCHAR(255) NOT NULL,
    html_url TEXT NOT NULL,
    description TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    language VARCHAR(100),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_repositories_github_id ON repositories(github_id);
CREATE INDEX idx_repositories_owner ON repositories(owner_login);
CREATE INDEX idx_repositories_name ON repositories(name);
```

#### 2.1.2 Pull Request Table

```sql
CREATE TABLE pull_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    github_id BIGINT UNIQUE NOT NULL,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    body TEXT,
    state VARCHAR(50) NOT NULL,
    created_at DATETIME,
    closed_at DATETIME,
    merged_at DATETIME,
    author_login VARCHAR(255) NOT NULL,
    html_url TEXT NOT NULL,
    diff_url TEXT,
    patch_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pull_requests_github_id ON pull_requests(github_id);
CREATE INDEX idx_pull_requests_repository ON pull_requests(repository_id);
CREATE INDEX idx_pull_requests_state ON pull_requests(state);
CREATE INDEX idx_pull_requests_author ON pull_requests(author_login);
CREATE INDEX idx_pull_requests_dates ON pull_requests(created_at, closed_at);
```

#### 2.1.3 Review Comment Table

```sql
CREATE TABLE review_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    github_id BIGINT UNIQUE NOT NULL,
    pull_request_id INTEGER REFERENCES pull_requests(id) ON DELETE CASCADE,
    author_login VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    path VARCHAR(500) NOT NULL,
    position INTEGER NOT NULL,
    line INTEGER,
    side VARCHAR(20),
    created_at DATETIME,
    updated_at DATETIME,
    html_url TEXT NOT NULL,
    diff_hunk TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_comments_github_id ON review_comments(github_id);
CREATE INDEX idx_review_comments_pr ON review_comments(pull_request_id);
CREATE INDEX idx_review_comments_author ON review_comments(author_login);
CREATE INDEX idx_review_comments_path ON review_comments(path);
CREATE INDEX idx_review_comments_dates ON review_comments(created_at);
```

#### 2.1.4 Code Snippet Table

```sql
CREATE TABLE code_snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_comment_id INTEGER REFERENCES review_comments(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    content TEXT NOT NULL,
    language VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_code_snippets_comment ON code_snippets(review_comment_id);
CREATE INDEX idx_code_snippets_file ON code_snippets(file_path);
CREATE INDEX idx_code_snippets_lines ON code_snippets(line_start, line_end);
```

#### 2.1.5 Comment Thread Table

```sql
CREATE TABLE comment_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pull_request_id INTEGER REFERENCES pull_requests(id) ON DELETE CASCADE,
    review_comment_id INTEGER REFERENCES review_comments(id) ON DELETE CASCADE,
    thread_path VARCHAR(500) NOT NULL,
    thread_position INTEGER NOT NULL,
    is_resolved BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_comment_threads_pr ON comment_threads(pull_request_id);
CREATE INDEX idx_comment_threads_comment ON comment_threads(review_comment_id);
CREATE INDEX idx_comment_threads_path ON comment_threads(thread_path);
```

#### 2.1.6 Extracted Rule Table

```sql
CREATE TABLE extracted_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_comment_id INTEGER REFERENCES review_comments(id) ON DELETE CASCADE,
    rule_text TEXT NOT NULL,
    rule_category VARCHAR(100),
    rule_severity VARCHAR(50),
    confidence_score REAL,
    llm_model VARCHAR(100),
    prompt_used TEXT,
    response_raw TEXT,
    is_valid BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_extracted_rules_comment ON extracted_rules(review_comment_id);
CREATE INDEX idx_extracted_rules_category ON extracted_rules(rule_category);
CREATE INDEX idx_extracted_rules_severity ON extracted_rules(rule_severity);
CREATE INDEX idx_extracted_rules_confidence ON extracted_rules(confidence_score);
CREATE INDEX idx_extracted_rules_dates ON extracted_rules(created_at);
```

#### 2.1.7 Rule Statistics Table

```sql
CREATE TABLE rule_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER REFERENCES extracted_rules(id) ON DELETE CASCADE,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    occurrence_count INTEGER DEFAULT 1,
    first_seen DATETIME,
    last_seen DATETIME,
    avg_confidence REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rule_statistics_rule ON rule_statistics(rule_id);
CREATE INDEX idx_rule_statistics_repo ON rule_statistics(repository_id);
CREATE INDEX idx_rule_statistics_dates ON rule_statistics(first_seen, last_seen);
```

## 3. API Design

### 3.1 Data Collector API Endpoints

```
POST   /api/v1/collector/repos/{repo_id}/sync     - Sync repository PRs
GET    /api/v1/collector/repos                    - List all repositories
POST   /api/v1/collector/repos                    - Add new repository
DELETE /api/v1/collector/repos/{repo_id}          - Remove repository
GET    /api/v1/collector/status                   - Get sync status
```

### 3.2 Data Analysis API Endpoints

```
POST   /api/v1/analysis/rules/extract            - Extract rules from PR data
GET    /api/v1/analysis/rules                     - List all rules
GET    /api/v1/analysis/rules/{rule_id}           - Get specific rule
GET    /api/v1/analysis/categories                - List rule categories
GET    /api/v1/analysis/statistics                - Get rule statistics
```

### 3.3 Data Presentation API Endpoints

```
GET    /api/v1/ui/dashboard                       - Get dashboard data
GET    /api/v1/ui/rules                           - Get rules with pagination
GET    /api/v1/ui/rules/search                    - Search rules
GET    /api/v1/ui/prs/{pr_id}                     - Get PR details
GET    /api/v1/ui/repos/{repo_id}/rules           - Get rules for repository
```

## 4. External Integration Design

### 4.1 GitHub API Integration

- **Authentication**: OAuth2 with personal access token
- **Rate Limiting**: Handle 5000 requests/hour for authenticated requests
- **Endpoints Used**:
  - `GET /repos/{owner}/{repo}/pulls` - List pull requests
  - `GET /repos/{owner}/{repo}/pulls/{number}/files` - Get PR files
  - `GET /repos/{owner}/{repo}/pulls/{number}/comments` - Get review comments
  - `GET /repos/{owner}/{repo}/issues/{number}/comments` - Get issue comments

### 4.2 LLM Service Integration

- **Provider**: OpenAI GPT-4 or compatible service
- **Authentication**: API key
- **Prompt Engineering**: Structured prompts for rule extraction
- **Response Parsing**: JSON-based response parsing with validation
- **Fallback Strategy**: Basic rule extraction if LLM service unavailable

## 5. Error Handling Strategy

### 5.1 GitHub API Errors

- **Rate Limiting**: Exponential backoff and retry
- **Authentication**: Clear error messages and token refresh
- **Network Issues**: Retry with exponential backoff
- **Data Validation**: Schema validation before storage

### 5.2 LLM Service Errors

- **API Limits**: Queue requests and implement rate limiting
- **Response Parsing**: Fallback to simpler parsing on errors
- **Prompt Failures**: Multiple prompt attempts with different phrasing
- **Service Unavailable**: Basic rule extraction as fallback

### 5.3 Database Errors

- **Connection Issues**: Connection retry logic and file validation
- **Constraint Violations**: Graceful error handling and user feedback
- **Performance**: Query optimization and indexing
- **File Corruption**: Database backup and restore procedures

## 6. Security Considerations

### 6.1 Data Protection

- **GitHub Tokens**: Secure storage with encryption
- **API Keys**: Environment variables and secure vaults
- **Database**: File permissions and backup procedures

### 6.2 Input Validation

- **API Inputs**: Comprehensive validation and sanitization
- **LLM Responses**: Content filtering and validation
- **User Input**: XSS prevention and SQL injection protection

## 7. Performance Optimization

### 7.1 Database Optimization

- **Indexing**: Strategic indexes on query patterns
- **Query Optimization**: Efficient SQL queries
- **Connection Management**: Optimized SQLite connections

### 7.2 Caching Strategy

- **API Responses**: In-memory caching for frequently accessed data
- **LLM Responses**: Cache similar prompts and responses
- **Static Assets**: Browser caching for web assets

### 7.3 Background Processing

- **Threading**: Async processing for data collection and analysis
- **Queue Management**: Priority queues for critical operations
- **Monitoring**: Task monitoring and error tracking
