"""
Code Snippet data model
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from ..utils.database import Base


class CodeSnippet(Base):
    """
    Code Snippet model representing code snippets associated with review comments
    """
    __tablename__ = "code_snippets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_comment_id = Column(Integer, ForeignKey("review_comments.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False, index=True)
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    review_comment = relationship("ReviewComment", back_populates="code_snippets")
    
    # Indexes
    __table_args__ = (
        Index('idx_code_snippets_lines', 'line_start', 'line_end'),
    )
    
    def __repr__(self):
        return f"<CodeSnippet(id={self.id}, file='{self.file_path}', lines={self.line_start}-{self.line_end})>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "review_comment_id": self.review_comment_id,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "content": self.content,
            "language": self.language,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_review_comment(cls, review_comment, file_path, line_start, line_end, content, language=None):
        """Create code snippet from review comment context"""
        return cls(
            review_comment_id=review_comment.id,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            content=content,
            language=language
        )
    
    def get_line_count(self):
        """Get the number of lines in the snippet"""
        return self.line_end - self.line_start + 1
    
    def get_preview(self, max_lines=10, max_chars=200):
        """Get a preview of the code snippet"""
        lines = self.content.split('\n')
        
        if len(lines) <= max_lines:
            preview = '\n'.join(lines)
        else:
            preview = '\n'.join(lines[:max_lines]) + f'\n... ({len(lines) - max_lines} more lines)'
        
        if len(preview) > max_chars:
            preview = preview[:max_chars] + '...'
        
        return preview
    
    def get_language_display_name(self):
        """Get human-readable language name"""
        if not self.language:
            return "Unknown"
        
        language_names = {
            'python': 'Python',
            'javascript': 'JavaScript',
            'typescript': 'TypeScript',
            'java': 'Java',
            'cpp': 'C++',
            'c': 'C',
            'c#': 'C#',
            'go': 'Go',
            'rust': 'Rust',
            'php': 'PHP',
            'ruby': 'Ruby',
            'swift': 'Swift',
            'kotlin': 'Kotlin',
            'scala': 'Scala',
            'html': 'HTML',
            'css': 'CSS',
            'scss': 'SCSS',
            'sass': 'SASS',
            'less': 'LESS',
            'sql': 'SQL',
            'shell': 'Shell',
            'bash': 'Bash',
            'zsh': 'Zsh',
            'powershell': 'PowerShell',
            'lua': 'Lua',
            'r': 'R',
            'matlab': 'MATLAB',
            'julia': 'Julia',
            'dockerfile': 'Dockerfile',
            'yaml': 'YAML',
            'yml': 'YAML',
            'json': 'JSON',
            'xml': 'XML',
            'markdown': 'Markdown',
            'plaintext': 'Plain Text'
        }
        
        return language_names.get(self.language.lower(), self.language.title())
    
    def is_valid_snippet(self):
        """Check if the code snippet is valid"""
        if not self.content or not self.content.strip():
            return False
        
        if self.line_start <= 0 or self.line_end <= 0:
            return False
        
        if self.line_start > self.line_end:
            return False
        
        if len(self.content.strip()) == 0:
            return False
        
        return True
    
    def get_relative_path(self, base_path=None):
        """Get relative path if base_path is provided"""
        if not base_path:
            return self.file_path
        
        if self.file_path.startswith(base_path):
            return self.file_path[len(base_path):].lstrip('/')
        
        return self.file_path
    
    def format_for_display(self):
        """Format code snippet for display"""
        result = []
        result.append(f"File: {self.file_path}")
        result.append(f"Lines: {self.line_start}-{self.line_end}")
        if self.language:
            result.append(f"Language: {self.get_language_display_name()}")
        result.append("")
        result.append("```" + (self.language or ""))
        result.append(self.get_preview())
        result.append("```")
        
        return '\n'.join(result)