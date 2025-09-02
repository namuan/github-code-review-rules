"""
Unit tests for LLM service
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import json
from datetime import datetime

from github_pr_rules_analyzer.services.llm_service import LLMService


class TestLLMService:
    """Test LLM service"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.service = LLMService(api_key="test_api_key", model="gpt-4")
    
    def test_initialization(self):
        """Test LLM service initialization"""
        assert self.service.api_key == "test_api_key"
        assert self.service.model == "gpt-4"
        assert self.service.client is not None
    
    def test_initialization_without_api_key(self):
        """Test LLM service initialization without API key"""
        service = LLMService()
        assert service.api_key is None
        assert service.client is None
    
    def test_build_extraction_prompt(self):
        """Test building extraction prompt"""
        comment_data = {
            'body': 'This code needs improvement',
            'file_path': 'src/main.py',
            'line_number': 10,
            'pr_title': 'Improve code quality',
            'repository_name': 'user/repo'
        }
        
        prompt = self.service._build_extraction_prompt(comment_data)
        
        assert 'You are an expert software engineer' in prompt
        assert 'user/repo' in prompt
        assert 'src/main.py' in prompt
        assert 'This code needs improvement' in prompt
        assert 'rule_text' in prompt
        assert 'rule_category' in prompt
        assert 'rule_severity' in prompt
    
    def test_build_extraction_prompt_minimal_data(self):
        """Test building extraction prompt with minimal data"""
        comment_data = {
            'body': 'This code needs improvement'
        }
        
        prompt = self.service._build_extraction_prompt(comment_data)
        
        assert 'You are an expert software engineer' in prompt
        assert 'This code needs improvement' in prompt
    
    @patch('github_pr_rules_analyzer.services.llm_service.OpenAI')
    def test_call_llm_success(self, mock_openai):
        """Test successful LLM API call"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = '{"rule_text": "Use meaningful variable names"}'
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test call
        prompt = "Test prompt"
        response = self.service._call_llm(prompt)
        
        assert response == '{"rule_text": "Use meaningful variable names"}'
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('github_pr_rules_analyzer.services.llm_service.OpenAI')
    def test_call_llm_retry(self, mock_openai):
        """Test LLM API call with retry"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock response to fail first time, succeed second time
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = '{"rule_text": "Use meaningful variable names"}'
        
        # First call raises exception, second succeeds
        mock_client.chat.completions.create.side_effect = [
            Exception("API Error"),
            mock_response
        ]
        
        # Test call
        prompt = "Test prompt"
        response = self.service._call_llm(prompt, max_retries=2)
        
        assert response == '{"rule_text": "Use meaningful variable names"}'
        assert mock_client.chat.completions.create.call_count == 2
    
    @patch('github_pr_rules_analyzer.services.llm_service.OpenAI')
    def test_call_llm_max_retries_exceeded(self, mock_openai):
        """Test LLM API call with max retries exceeded"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock response to always fail
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Test call
        prompt = "Test prompt"
        
        with pytest.raises(Exception, match="Max retries exceeded"):
            self.service._call_llm(prompt, max_retries=3)
    
    def test_call_llm_no_client(self):
        """Test LLM API call without client"""
        service = LLMService()  # No API key
        
        with pytest.raises(Exception, match="LLM client not initialized"):
            service._call_llm("Test prompt")
    
    def test_parse_llm_response_valid(self):
        """Test parsing valid LLM response"""
        response = '''
        {
            "rule_text": "Use meaningful variable names",
            "rule_category": "naming",
            "rule_severity": "medium",
            "explanation": "Variables should have descriptive names",
            "examples": ["good: user_count", "bad: x"],
            "related_concepts": ["code readability", "variable naming conventions"]
        }
        '''
        
        comment_data = {
            'review_comment_id': 1,
            'body': 'This code needs improvement',
            'file_path': 'src/main.py'
        }
        
        result = self.service._parse_llm_response(response, comment_data)
        
        assert result is not None
        assert result['rule_text'] == "Use meaningful variable names."
        assert result['rule_category'] == "naming"
        assert result['rule_severity'] == "medium"
        assert result['explanation'] == "Variables should have descriptive names"
        assert len(result['examples']) == 2
        assert len(result['related_concepts']) == 2
        assert result['confidence_score'] > 0.5
        assert result['llm_model'] == "gpt-4"
        assert result['review_comment_id'] == 1
    
    def test_parse_llm_response_invalid_json(self):
        """Test parsing invalid JSON response"""
        response = "This is not valid JSON"
        comment_data = {'body': 'test'}
        
        result = self.service._parse_llm_response(response, comment_data)
        
        assert result is None
    
    def test_parse_llm_response_missing_fields(self):
        """Test parsing response with missing required fields"""
        response = '''
        {
            "rule_text": "Use meaningful variable names",
            "explanation": "Variables should have descriptive names"
            // Missing rule_category and rule_severity
        }
        '''
        
        comment_data = {'body': 'test'}
        
        result = self.service._parse_llm_response(response, comment_data)
        
        assert result is None
    
    def test_normalize_category(self):
        """Test category normalization"""
        # Test various category inputs
        assert self.service._normalize_category("naming") == "naming"
        assert self.service._normalize_category("NAME") == "naming"
        assert self.service._normalize_category("variable naming") == "naming"
        assert self.service._normalize_category("style") == "style"
        assert self.service._normalize_category("formatting") == "style"
        assert self.service._normalize_category("performance") == "performance"
        assert self.service._normalize_category("security") == "security"
        assert self.service._normalize_category("best practices") == "best_practices"
        assert self.service._normalize_category("unknown category") == "general"
    
    def test_normalize_severity(self):
        """Test severity normalization"""
        # Test various severity inputs
        assert self.service._normalize_severity("critical") == "critical"
        assert self.service._normalize_severity("MUST") == "critical"
        assert self.service._normalize_severity("required") == "critical"
        assert self.service._normalize_severity("high") == "high"
        assert self.service._normalize_severity("important") == "high"
        assert self.service._normalize_severity("medium") == "medium"
        assert self.service._normalize_severity("should") == "medium"
        assert self.service._normalize_severity("low") == "low"
        assert self.service._normalize_severity("optional") == "low"
        assert self.service._normalize_severity("info") == "info"
        assert self.service._normalize_severity("note") == "info"
        assert self.service._normalize_severity("unknown severity") == "info"
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation"""
        response_data = {
            'rule_text': 'Use meaningful variable names',
            'rule_category': 'naming',
            'rule_severity': 'medium',
            'explanation': 'Variables should have descriptive names',
            'examples': ['good: user_count', 'bad: x'],
            'related_concepts': ['code readability']
        }
        
        comment_data = {
            'file_path': 'src/main.py'
        }
        
        score = self.service._calculate_confidence_score(response_data, comment_data)
        
        assert score >= 0.5  # Base confidence
        assert score <= 1.0  # Maximum confidence
        assert score > 0.7   # Should be boosted by complete response
    
    def test_calculate_confidence_score_minimal(self):
        """Test confidence score calculation with minimal data"""
        response_data = {
            'rule_text': 'Use meaningful variable names'
        }
        
        comment_data = {}
        
        score = self.service._calculate_confidence_score(response_data, comment_data)
        
        assert score == 0.5  # Base confidence only
    
    def test_fallback_rule_extraction_success(self):
        """Test fallback rule extraction success"""
        comment_data = {
            'body': 'You should always validate user input',
            'review_comment_id': 1,
            'file_path': 'src/main.py'
        }
        
        result = self.service._fallback_rule_extraction(comment_data)
        
        assert result is not None
        assert result['rule_text'] == "You should always validate user input."
        assert result['rule_category'] == 'general'
        assert result['rule_severity'] == 'medium'
        assert result['llm_model'] == 'rule-based'
        assert result['confidence_score'] == 0.6
    
    def test_fallback_rule_extraction_no_rule(self):
        """Test fallback rule extraction when no rule is found"""
        comment_data = {
            'body': 'This is just a comment without any specific rule',
            'review_comment_id': 1
        }
        
        result = self.service._fallback_rule_extraction(comment_data)
        
        assert result is None
    
    def test_fallback_rule_extraction_empty_text(self):
        """Test fallback rule extraction with empty text"""
        comment_data = {
            'body': '',
            'review_comment_id': 1
        }
        
        result = self.service._fallback_rule_extraction(comment_data)
        
        assert result is None
    
    def test_extract_rule_from_comment_with_llm(self):
        """Test rule extraction with LLM"""
        comment_data = {
            'body': 'This code needs improvement',
            'file_path': 'src/main.py',
            'line_number': 10,
            'pr_title': 'Improve code quality',
            'repository_name': 'user/repo',
            'review_comment_id': 1
        }
        
        with patch.object(self.service, '_call_llm') as mock_call, \
             patch.object(self.service, '_parse_llm_response') as mock_parse:
            
            # Mock successful LLM response
            mock_call.return_value = '{"rule_text": "Use meaningful variable names"}'
            mock_parse.return_value = {
                'rule_text': 'Use meaningful variable names.',
                'rule_category': 'naming',
                'rule_severity': 'medium',
                'confidence_score': 0.8
            }
            
            result = self.service.extract_rule_from_comment(comment_data)
            
            assert result is not None
            assert result['rule_text'] == 'Use meaningful variable names.'
            mock_call.assert_called_once()
            mock_parse.assert_called_once()
    
    def test_extract_rule_from_comment_fallback(self):
        """Test rule extraction fallback when LLM fails"""
        comment_data = {
            'body': 'You should always validate user input',
            'review_comment_id': 1
        }
        
        with patch.object(self.service, '_call_llm') as mock_call:
            # Mock LLM to fail
            mock_call.side_effect = Exception("API Error")
            
            result = self.service.extract_rule_from_comment(comment_data)
            
            assert result is not None
            assert result['llm_model'] == 'rule-based'
            assert result['rule_text'] == "You should always validate user input."
    
    def test_extract_rule_from_comment_no_client(self):
        """Test rule extraction when no LLM client"""
        service = LLMService()  # No API key
        comment_data = {
            'body': 'You should always validate user input',
            'review_comment_id': 1
        }
        
        result = service.extract_rule_from_comment(comment_data)
        
        assert result is not None
        assert result['llm_model'] == 'rule-based'
    
    def test_extract_rules_from_comments_batch(self):
        """Test batch rule extraction"""
        comments_data = [
            {
                'body': 'This code needs improvement',
                'review_comment_id': 1,
                'file_path': 'src/main.py'
            },
            {
                'body': 'You should always validate user input',
                'review_comment_id': 2,
                'file_path': 'src/main.py'
            }
        ]
        
        with patch.object(self.service, 'extract_rule_from_comment') as mock_extract:
            # Mock successful extraction for both comments
            mock_extract.side_effect = [
                {'rule_text': 'Rule 1', 'rule_category': 'naming'},
                {'rule_text': 'Rule 2', 'rule_category': 'security'}
            ]
            
            results = self.service.extract_rules_from_comments_batch(comments_data)
            
            assert len(results) == 2
            assert results[0]['rule_text'] == 'Rule 1'
            assert results[1]['rule_text'] == 'Rule 2'
            assert mock_extract.call_count == 2
    
    def test_extract_rules_from_comments_batch_with_errors(self):
        """Test batch rule extraction with some errors"""
        comments_data = [
            {
                'body': 'This code needs improvement',
                'review_comment_id': 1,
                'file_path': 'src/main.py'
            },
            {
                'body': 'Invalid comment data',
                'review_comment_id': 2
            }
        ]
        
        with patch.object(self.service, 'extract_rule_from_comment') as mock_extract:
            # Mock first to succeed, second to fail
            mock_extract.side_effect = [
                {'rule_text': 'Rule 1', 'rule_category': 'naming'},
                Exception("Extraction failed")
            ]
            
            results = self.service.extract_rules_from_comments_batch(comments_data)
            
            assert len(results) == 1
            assert results[0]['rule_text'] == 'Rule 1'
    
    def test_test_connection_success(self):
        """Test successful connection test"""
        with patch.object(self.service.client, 'chat') as mock_chat:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = "Hello"
            mock_chat.completions.create.return_value = mock_response
            
            result = self.service.test_connection()
            
            assert result is True
            mock_chat.completions.create.assert_called_once()
    
    def test_test_connection_failure(self):
        """Test connection test failure"""
        with patch.object(self.service.client, 'chat') as mock_chat:
            mock_chat.completions.create.side_effect = Exception("Connection failed")
            
            result = self.service.test_connection()
            
            assert result is False
    
    def test_test_connection_no_client(self):
        """Test connection test without client"""
        service = LLMService()  # No API key
        
        result = service.test_connection()
        
        assert result is False
    
    def test_validate_api_key(self):
        """Test API key validation"""
        # Valid API key
        assert self.service.validate_api_key() is True
        
        # Invalid API key
        service = LLMService(api_key="   ")
        assert service.validate_api_key() is False
        
        # No API key
        service = LLMService()
        assert service.validate_api_key() is False
    
    def test_get_model_info(self):
        """Test getting model information"""
        info = self.service.get_model_info()
        
        assert info['model'] == 'gpt-4'
        assert info['api_key_configured'] is True
        assert info['client_available'] is True
        assert 'connection_test' in info
    
    def test_get_model_info_no_client(self):
        """Test getting model information without client"""
        service = LLMService()
        
        info = service.get_model_info()
        
        assert info['model'] is None
        assert info['api_key_configured'] is False
        assert info['client_available'] is False
        assert info['connection_test'] is False
    
    def test_get_usage_stats(self):
        """Test getting usage statistics"""
        stats = self.service.get_usage_stats()
        
        assert 'model' in stats
        assert 'api_key_configured' in stats
        assert 'connection_test' in stats
    
    def test_get_usage_stats_no_client(self):
        """Test getting usage statistics without client"""
        service = LLMService()
        
        stats = service.get_usage_stats()
        
        assert 'error' in stats
        assert stats['error'] == 'Client not initialized'