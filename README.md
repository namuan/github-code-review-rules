# GitHub PR Rules Analyzer

A comprehensive system that collects, processes, and analyzes GitHub pull request comments to generate coding rules. The system helps improve code quality and enforce coding standards automatically by leveraging AI-powered rule extraction from real-world code reviews.

## 🚀 Features

- **Data Collection**: Connects to GitHub API to collect pull request data including review comments, code snippets, and comment threads
- **AI-Powered Analysis**: Uses LLM services to extract meaningful coding rules from review comments
- **Web Interface**: Clean, responsive web dashboard for browsing and searching extracted rules
- **Repository Management**: Add and manage multiple GitHub repositories for analysis
- **Real-time Sync**: Monitor data collection progress and sync status
- **Search & Filter**: Powerful search functionality to find rules by category, severity, and repository
- **Statistics & Insights**: Comprehensive analytics and rule categorization
- **Production Ready**: Docker deployment with comprehensive testing and monitoring

## 📊 Code Statistics

```text
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                          30           1473           1462           5720
CSS                              1            153             15            779
Markdown                         5            186              0            637
JavaScript                       2             36             22            291
Bourne Shell                     1             69             75            288
HTML                             1             18             25            227
YAML                             2             16             32            215
TOML                             1              9              2             66
JSON                             3              0              0             62
make                             1             14              0             53
Dockerfile                       1             18             20             33
-------------------------------------------------------------------------------
SUM:                            48           1992           1653           8371
-------------------------------------------------------------------------------
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub API    │    │   LLM Service   │    │   Web UI        │
│                 │    │                 │    │                 │
│ - OAuth         │    │ - Ollama API    │    │ - React/Vue     │
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
                    │ - SQLite        │
                    │ - Data Models   │
                    │ - Indexes       │
                    └─────────────────┘
```

## 🛠️ Technology Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: SQLite (development), PostgreSQL (production)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla JS)
- **API Integration**: GitHub API v3/v4, Ollama API
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Deployment**: Docker, Docker Compose, systemd
- **Monitoring**: Prometheus, Grafana (optional)
- **CI/CD**: GitHub Actions

## 📦 Installation

### Prerequisites

- Python 3.11+
- pip
- Git
- Docker (optional, for containerized deployment)

### Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/github-pr-rules-analyzer.git
   cd github-pr-rules-analyzer
   ```

2. **Install dependencies**

   ```bash
   make install
   ```

3. **Set environment variables**

   ```bash
   export GITHUB_TOKEN=your_github_token
   export SECRET_KEY=your_secret_key
   ```

4. **Run the application**

   ```bash
   python main.py
   ```

5. **Access the web interface**
   Open your browser and navigate to `http://localhost:8000`

### Docker Deployment

1. **Build and run with Docker Compose**

   ```bash
   docker-compose up -d
   ```

2. **Access the application**
   - Web Interface: `http://localhost`
   - API Documentation: `http://localhost:8000/docs`

### Production Deployment

Use the provided deployment script for production setup:

```bash
sudo ./deploy/deploy.sh
```

## 🔧 Configuration

### Environment Variables

| Variable              | Description             | Default                     |
| --------------------- | ----------------------- | --------------------------- |
| `DEBUG`               | Debug mode              | `False`                     |
| `HOST`                | Host address            | `0.0.0.0`                   |
| `PORT`                | Port number             | `8000`                      |
| `DATABASE_URL`        | Database connection     | `sqlite:///app.db`          |
| `GITHUB_TOKEN`        | GitHub API token        | Required                    |
| `GITHUB_API_BASE_URL` | GitHub API base URL     | `https://api.github.com`    |
| `OLLAMA_MODEL`        | Ollama model to use     | `llama3.2:latest`           |
| `OLLAMA_API_BASE_URL` | Ollama API base URL     | `http://localhost:11434/v1` |
| `LLM_MAX_TOKENS`      | Maximum tokens for LLM  | `1000`                      |
| `LLM_TEMPERATURE`     | LLM temperature         | `0.3`                       |
| `SECRET_KEY`          | Secret key for sessions | Auto-generated              |
| `LOG_LEVEL`           | Logging level           | `INFO`                      |
| `LOG_FILE`            | Log file path           | `logs/app.log`              |

### GitHub API Setup

1. Create a GitHub Personal Access Token:

   - Go to GitHub Settings → Developer Settings → Personal Access Tokens
   - Generate a token with `repo` scope

2. Set the token as an environment variable:
   ```bash
   export GITHUB_TOKEN=your_token_here
   ```

### Using Ollama (Local LLM)

The application now uses Ollama by default for LLM processing:

1. Install Ollama: https://ollama.com/download

2. Pull the llama3.2 model:
   ```bash
   ollama pull llama3.2:latest
   ```

3. Start the Ollama service:
   ```bash
   ollama serve
   ```

4. Set the appropriate environment variables (optional, as defaults are provided):
   ```bash
   export OLLAMA_MODEL=llama3.2:latest
   # OLLAMA_API_BASE_URL defaults to http://localhost:11434/v1
   ```

## 📚 Usage

### Adding Repositories

1. Navigate to the "Repositories" section in the web interface
2. Click "Add Repository"
3. Enter the repository owner and name
4. Click "Add Repository"

### Syncing Data

1. After adding a repository, click "Sync" to start data collection
2. Monitor the sync progress in the "Sync Status" section
3. Once sync is complete, rules will be automatically extracted

### Browsing Rules

1. Navigate to the "Rules" section
2. Use the search bar to find specific rules
3. Filter by category, severity, or repository
4. Click on any rule to view details

### Managing Data

- **Repositories**: Add, sync, or remove repositories
- **Rules**: View, search, and filter extracted rules
- **Statistics**: View analytics and rule categorization
- **Sync Status**: Monitor data collection progress

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=github_pr_rules_analyzer --cov-report=html

# Run specific test file
pytest tests/test_main.py

# Run integration tests
pytest tests/test_integration.py
```

### Code Quality

```bash
# Linting
flake8 .
black .
isort .

# Security scanning
bandit -r .
safety check
```

### Performance Testing

```bash
# Run performance tests
python deploy/performance_test.py --url http://localhost:8000 --requests 100

# Run stress test
python deploy/performance_test.py --url http://localhost:8000 --stress --requests 1000
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t github-pr-rules-analyzer .

# Run container
docker run -p 8000:8000 github-pr-rules-analyzer
```

### Docker Compose Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment

The deployment script handles:

- System service setup
- Nginx configuration
- Environment setup
- Database initialization
- SSL configuration
- Monitoring and logging

```bash
# Run deployment script
sudo ./deploy/deploy.sh

# Check service status
systemctl status github-pr-rules-analyzer

# View logs
journalctl -u github-pr-rules-analyzer -f
```

## 🔍 API Documentation

Once the application is running, you can access the interactive API documentation at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key API Endpoints

| Endpoint                | Method   | Description           |
| ----------------------- | -------- | --------------------- |
| `/api/v1/health`        | GET      | Health check          |
| `/api/v1/dashboard`     | GET      | Dashboard data        |
| `/api/v1/repositories`  | GET/POST | Repository management |
| `/api/v1/rules`         | GET      | List rules            |
| `/api/v1/rules/search`  | GET      | Search rules          |
| `/api/v1/rules/extract` | POST     | Extract rules         |
| `/api/v1/sync`          | POST     | Start sync            |

## 📈 Monitoring

### Application Monitoring

- **Health Checks**: `/api/v1/health` endpoint
- **System Logs**: `journalctl -u github-pr-rules-analyzer`
- **Application Logs**: `tail -f logs/app.log`

### Performance Monitoring

- **Prometheus**: Metrics collection at `http://localhost:9090`
- **Grafana**: Dashboard at `http://localhost:3000`
- **Performance Tests**: Use `deploy/performance_test.py`

### Alerting

Configure alerts for:

- High error rates
- Slow response times
- Service unavailability
- Resource usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/github-pr-rules-analyzer.git
cd github-pr-rules-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [GitHub API](https://docs.github.com/en/rest) for providing excellent developer tools
- [Ollama](https://ollama.com/) for the local LLM capabilities
- [FastAPI](https://fastapi.tiangolo.com/) for the amazing web framework
- [Chart.js](https://www.chartjs.org/) for the data visualization library

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/github-pr-rules-analyzer/issues)
- **Documentation**: [Wiki](https://github.com/yourusername/github-pr-rules-analyzer/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/github-pr-rules-analyzer/discussions)

## 🗺️ Roadmap

- [ ] Support for multiple LLM providers
- [ ] Advanced rule categorization and tagging
- [ ] User authentication and permissions
- [ ] Rule recommendations and suggestions
- [ ] Integration with CI/CD pipelines
- [ ] Export rules to various formats
- [ ] Advanced search and filtering
- [ ] Real-time notifications
- [ ] Mobile app support

---
