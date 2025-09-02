"""
LLM service for extracting coding rules from GitHub PR comments
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import openai
from openai import OpenAI

from ..config import get_settings
from ..utils import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMService:
    """
    Service for interacting with LLM to extract coding rules
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize LLM service
        
        Args:
            api_key: OpenAI API key
            model: Model to use for rule extraction
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.client = None
        
        # Initialize OpenAI client
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            logger.warning("No OpenAI API key provided")
    
    def __del__(self):
        """Clean up resources"""
        pass
    
    def extract_rule_from_comment(self, comment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract rule from a single comment using LLM
        
        Args:
            comment_data: Comment data including text and context
            
        Returns:
            Extracted rule data or None
        """
        if not self.client:
            logger.warning("LLM client not initialized, using fallback rule extraction")
            return self._fallback_rule_extraction(comment_data)
        
        try:
            # Prepare prompt
            prompt = self._build_extraction_prompt(comment_data)
            
            # Make API call
            response = self._call_llm(prompt)
            
            # Parse response
            rule_data = self._parse_llm_response(response, comment_data)
            
            return rule_data
            
        except Exception as e:
            logger.error(f"Error extracting rule with LLM: {e}")
            # Fallback to rule-based extraction
            return self._fallback_rule_extraction(comment_data)
    
    def extract_rules_from_comments_batch(self, comments_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract rules from multiple comments in batch
        
        Args:
            comments_data: List of comment data
            
        Returns:
            List of extracted rule data
        """
        results = []
        
        for comment_data in comments_data:
            try:
                rule_data = self.extract_rule_from_comment(comment_data)
                if rule_data:
                    results.append(rule_data)
            except Exception as e:
                logger.error(f"Error processing comment {comment_data.get('id', 'unknown')}: {e}")
                continue
        
        return results
    
    def _build_extraction_prompt(self, comment_data: Dict[str, Any]) -> str:
        """
        Build prompt for rule extraction
        
        Args:
            comment_data: Comment data
            
        Returns:
            Formatted prompt
        """
        comment_text = comment_data.get('body', '')
        file_path = comment_data.get('file_path', '')
        line_number = comment_data.get('line_number', '')
        pr_title = comment_data.get('pr_title', '')
        repository_name = comment_data.get('repository_name', '')
        
        prompt = f"""
You are an expert software engineer specializing in code quality and best practices. 
Your task is to extract specific coding rules or guidelines from the following GitHub pull request comment.

Context Information:
- Repository: {repository_name}
- Pull Request Title: {pr_title}
- File: {file_path}
- Line: {line_number}

Comment Text:
"{comment_text}"

Please analyze this comment and extract a clear, specific coding rule or guideline. 
The rule should be:
1. Specific and actionable
2. Focused on code quality and best practices
3. Applicable to similar situations in the future
4. Written in clear, concise language

Format your response as a JSON object with the following structure:
{{
    "rule_text": "The extracted rule in clear, imperative language",
    "rule_category": "Category of the rule (naming, style, performance, security, best_practices, error_handling, testing, documentation, architecture, readability, general)",
    "rule_severity": "Severity level (critical, high, medium, low, info)",
    "explanation": "Brief explanation of why this rule is important",
    "examples": ["Example of good code", "Example of bad code"],
    "related_concepts": ["Related programming concepts or patterns"]
}}

If no specific coding rule can be extracted, return null.
"""
        
        return prompt
    
    def _call_llm(self, prompt: str, max_retries: int = 3) -> str:
        """
        Call LLM API with retry logic
        
        Args:
            prompt: Prompt to send to LLM
            max_retries: Maximum number of retry attempts
            
        Returns:
            LLM response text
        """
        if not self.client:
            raise Exception("LLM client not initialized")
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Calling LLM (attempt {attempt + 1}/{max_retries})")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert software engineer specializing in code quality and best practices."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                response_text = response.choices[0].message.content.strip()
                
                # Validate response is JSON
                try:
                    json.loads(response_text)
                except json.JSONDecodeError:
                    logger.warning(f"LLM response is not valid JSON: {response_text}")
                    raise ValueError("Invalid JSON response from LLM")
                
                return response_text
                
            except Exception as e:
                logger.warning(f"LLM API call failed (attempt {attempt + 1}): {e}")
                
                if attempt == max_retries - 1:
                    raise
                
                # Wait before retry (exponential backoff)
                wait_time = (2 ** attempt) * 1
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        raise Exception("Max retries exceeded for LLM API call")
    
    def _parse_llm_response(self, response: str, comment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse LLM response and extract rule data
        
        Args:
            response: LLM response text
            comment_data: Original comment data
            
        Returns:
            Parsed rule data or None
        """
        try:
            response_data = json.loads(response)
            
            # Validate required fields
            required_fields = ['rule_text', 'rule_category', 'rule_severity']
            for field in required_fields:
                if field not in response_data or not response_data[field]:
                    logger.warning(f"Missing required field in LLM response: {field}")
                    return None
            
            # Clean up rule text
            rule_text = response_data['rule_text'].strip()
            if not rule_text.endswith('.'):
                rule_text += '.'
            
            # Normalize category
            category = self._normalize_category(response_data['rule_category'])
            
            # Normalize severity
            severity = self._normalize_severity(response_data['rule_severity'])
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(response_data, comment_data)
            
            # Build rule data
            rule_data = {
                'rule_text': rule_text,
                'rule_category': category,
                'rule_severity': severity,
                'explanation': response_data.get('explanation', ''),
                'examples': response_data.get('examples', []),
                'related_concepts': response_data.get('related_concepts', []),
                'confidence_score': confidence,
                'llm_model': self.model,
                'prompt_used': self._build_extraction_prompt(comment_data),
                'response_raw': response,
                'is_valid': True,
                'review_comment_id': comment_data.get('review_comment_id'),
                'comment_text': comment_data.get('body', ''),
                'file_path': comment_data.get('file_path', ''),
                'context': comment_data
            }
            
            return rule_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
    
    def _normalize_category(self, category: str) -> str:
        """
        Normalize rule category
        
        Args:
            category: Raw category from LLM
            
        Returns:
            Normalized category
        """
        category_lower = category.lower().strip()
        
        category_mapping = {
            'naming': ['naming', 'name', 'identifier', 'variable', 'function', 'class', 'method'],
            'style': ['style', 'format', 'formatting', 'indent', 'spacing', 'layout', 'appearance'],
            'performance': ['performance', 'efficient', 'optimize', 'optimization', 'speed', 'memory'],
            'security': ['security', 'secure', 'safe', 'vulnerable', 'vulnerability', 'attack', 'protect'],
            'best_practices': ['best practice', 'best practices', 'convention', 'conventions', 'standard', 'standards', 'guideline', 'guidelines'],
            'error_handling': ['error handling', 'error', 'exception', 'handle', 'handling', 'catch', 'throw', 'exception handling'],
            'testing': ['test', 'testing', 'unit test', 'unit tests', 'integration test', 'integration tests', 'coverage', 'tdd'],
            'documentation': ['documentation', 'document', 'doc', 'comment', 'comments', 'readme', 'description'],
            'architecture': ['architecture', 'design', 'structure', 'pattern', 'patterns', 'module', 'modules', 'component'],
            'readability': ['readability', 'readable', 'clear', 'clarity', 'understand', 'understandable', 'simple', 'clean'],
            'maintainability': ['maintainability', 'maintain', 'maintainable', 'refactor', 'refactoring'],
            'reliability': ['reliability', 'reliable', 'robust', 'robustness', 'stability', 'stable']
        }
        
        for normalized_category, keywords in category_mapping.items():
            if any(keyword in category_lower for keyword in keywords):
                return normalized_category
        
        return 'general'
    
    def _normalize_severity(self, severity: str) -> str:
        """
        Normalize rule severity
        
        Args:
            severity: Raw severity from LLM
            
        Returns:
            Normalized severity
        """
        severity_lower = severity.lower().strip()
        
        severity_mapping = {
            'critical': ['critical', 'must', 'required', 'mandatory', 'essential', 'urgent'],
            'high': ['high', 'important', 'serious', 'major', 'significant'],
            'medium': ['medium', 'moderate', 'should', 'recommended', 'advised'],
            'low': ['low', 'minor', 'optional', 'suggestion', 'suggested'],
            'info': ['info', 'information', 'note', 'reminder', 'fyi', 'reference']
        }
        
        for normalized_severity, keywords in severity_mapping.items():
            if any(keyword in severity_lower for keyword in keywords):
                return normalized_severity
        
        # Default based on rule content
        if any(word in severity_lower for word in ['critical', 'must', 'required']):
            return 'critical'
        elif any(word in severity_lower for word in ['important', 'serious']):
            return 'high'
        elif any(word in severity_lower for word in ['should', 'recommended']):
            return 'medium'
        elif any(word in severity_lower for word in ['optional', 'suggestion']):
            return 'low'
        else:
            return 'info'
    
    def _calculate_confidence_score(self, response_data: Dict[str, Any], comment_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score for the extracted rule
        
        Args:
            response_data: Parsed LLM response
            comment_data: Original comment data
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence
        
        # Boost confidence for complete responses
        if all(field in response_data for field in ['rule_text', 'rule_category', 'rule_severity']):
            confidence += 0.1
        
        # Boost confidence for detailed explanations
        if response_data.get('explanation'):
            confidence += 0.05
        
        # Boost confidence for examples
        if response_data.get('examples'):
            confidence += 0.05
        
        # Boost confidence for related concepts
        if response_data.get('related_concepts'):
            confidence += 0.05
        
        # Boost confidence for longer, more specific rules
        rule_text = response_data.get('rule_text', '')
        if len(rule_text) > 50:
            confidence += 0.05
        
        # Boost confidence for rules with context
        if comment_data.get('file_path'):
            confidence += 0.05
        
        # Boost confidence for rules from specific categories
        category = response_data.get('rule_category', '').lower()
        if category in ['security', 'performance', 'critical']:
            confidence += 0.05
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def _fallback_rule_extraction(self, comment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fallback rule extraction using simple rule-based approach
        
        Args:
            comment_data: Comment data
            
        Returns:
            Extracted rule data or None
        """
        comment_text = comment_data.get('body', '')
        if not comment_text or not comment_text.strip():
            return None
        
        # Simple rule patterns
        import re
        
        rule_patterns = [
            (r'should\s+(?:always|never)\s+\w+', 'should/never rule'),
            (r'avoid\s+\w+', 'avoidance rule'),
            (r'use\s+\w+\s+instead', 'substitution rule'),
            (r'prefer\s+\w+\s+over', 'preference rule'),
            (r'follow\s+\w+\s+convention', 'convention rule'),
            (r'ensure\s+\w+\s+is\s+\w+', 'ensurance rule'),
            (r'make\s+sure\s+to\s+\w+', 'instruction rule'),
            (r'remember\s+to\s+\w+', 'reminder rule'),
            (r'do\s+not\s+\w+', 'prohibition rule'),
            (r'always\s+\w+', 'requirement rule'),
            (r'never\s+\w+', 'prohibition rule')
        ]
        
        for pattern, rule_type in rule_patterns:
            match = re.search(pattern, comment_text, re.IGNORECASE)
            if match:
                rule_text = match.group(0)
                rule_text = rule_text[0].upper() + rule_text[1:]
                if not rule_text.endswith('.'):
                    rule_text += '.'
                
                return {
                    'rule_text': rule_text,
                    'rule_category': self._categorize_fallback_rule(rule_text),
                    'rule_severity': self._assess_fallback_severity(rule_text),
                    'explanation': f'Extracted using pattern matching: {rule_type}',
                    'examples': [],
                    'related_concepts': [],
                    'confidence_score': 0.6,  # Moderate confidence for fallback
                    'llm_model': 'rule-based',
                    'prompt_used': 'Fallback rule extraction',
                    'response_raw': f'{{"rule": "{rule_text}"}}',
                    'is_valid': True,
                    'review_comment_id': comment_data.get('review_comment_id'),
                    'comment_text': comment_text,
                    'file_path': comment_data.get('file_path', ''),
                    'context': comment_data
                }
        
        return None
    
    def _categorize_fallback_rule(self, rule_text: str) -> str:
        """
        Categorize rule for fallback extraction
        
        Args:
            rule_text: Rule text
            
        Returns:
            Category name
        """
        rule_lower = rule_text.lower()
        
        category_keywords = {
            'naming': ['name', 'naming', 'variable', 'function', 'class', 'method', 'identifier'],
            'style': ['style', 'format', 'indent', 'spacing', 'layout', 'appearance'],
            'performance': ['performance', 'efficient', 'optimize', 'speed', 'memory'],
            'security': ['security', 'safe', 'vulnerable', 'attack', 'protect'],
            'best_practices': ['best', 'practice', 'convention', 'standard', 'guideline'],
            'error_handling': ['error', 'exception', 'handle', 'catch', 'throw'],
            'testing': ['test', 'testing', 'unit', 'integration', 'coverage'],
            'documentation': ['document', 'comment', 'doc', 'readme', 'description'],
            'architecture': ['architecture', 'design', 'structure', 'pattern', 'module'],
            'readability': ['readable', 'clear', 'understand', 'simple', 'clean']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in rule_lower for keyword in keywords):
                return category
        
        return 'general'
    
    def _assess_fallback_severity(self, rule_text: str) -> str:
        """
        Assess severity for fallback extraction
        
        Args:
            rule_text: Rule text
            
        Returns:
            Severity level
        """
        rule_lower = rule_text.lower()
        
        severity_keywords = {
            'critical': ['critical', 'must', 'required', 'mandatory', 'essential'],
            'high': ['high', 'important', 'serious', 'major'],
            'medium': ['medium', 'moderate', 'should', 'recommended'],
            'low': ['low', 'minor', 'optional', 'suggestion'],
            'info': ['info', 'note', 'reminder', 'fyi']
        }
        
        for severity, keywords in severity_keywords.items():
            if any(keyword in rule_lower for keyword in keywords):
                return severity
        
        # Default based on rule length
        if len(rule_text) > 100:
            return 'medium'
        elif len(rule_text) > 50:
            return 'low'
        else:
            return 'info'
    
    def test_connection(self) -> bool:
        """
        Test connection to LLM service
        
        Returns:
            True if connection is successful
        """
        if not self.client:
            return False
        
        try:
            # Simple test call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            return response.choices[0].message.content is not None
            
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model
        
        Returns:
            Model information dictionary
        """
        return {
            'model': self.model,
            'api_key_configured': bool(self.api_key),
            'client_available': self.client is not None,
            'connection_test': self.test_connection() if self.client else False
        }
    
    def validate_api_key(self) -> bool:
        """
        Validate API key configuration
        
        Returns:
            True if API key is valid
        """
        return bool(self.api_key and self.api_key.strip())
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics (if available)
        
        Returns:
            Usage statistics dictionary
        """
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
            
            # This would typically require additional API calls
            # For now, return basic info
            return {
                'model': self.model,
                'api_key_configured': self.validate_api_key(),
                'connection_test': self.test_connection()
            }
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return {'error': str(e)}