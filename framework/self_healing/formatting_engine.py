"""
Pattern matching engine for automatic code formatting fixes.

This module loads the formatting.yml pattern database and uses it to parse 
raw text output from command-line formatting tools to identify fixable issues.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class MatchResult:
    """Result of pattern matching operation."""
    pattern_id: str
    tool: str  
    fix_command: str
    commit_message_template: str
    severity: str
    requires_git_commit: bool
    matched_groups: List[str]
    original_output: str
    description: str


class FormattingPatternEngine:
    """
    Engine that loads formatting patterns and matches them against tool output.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the pattern engine.
        
        Args:
            config_path: Path to formatting.yml config file. If None, uses default location.
        """
        self.config_path = config_path or self._get_default_config_path()
        self.patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.engine_config: Dict[str, Any] = {}
        self.git_config: Dict[str, Any] = {}
        self._load_patterns()
    
    def _get_default_config_path(self) -> Path:
        """Get the default path to formatting.yml."""
        return Path(__file__).parent / "formatting.yml"
    
    def _load_patterns(self) -> None:
        """Load patterns from the YAML configuration file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.patterns = config.get("patterns", {})
            self.engine_config = config.get("engine_config", {})
            self.git_config = config.get("git_config", {})
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Pattern config file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
    
    def match_output(self, output: str) -> Optional[MatchResult]:
        """
        Match the given tool output against all known patterns.
        
        Args:
            output: Raw stdout/stderr from a formatting tool
            
        Returns:
            MatchResult if a pattern matches, None otherwise
        """
        if not output or not output.strip():
            return None
            
        # Try each tool's patterns
        for tool_name, tool_patterns in self.patterns.items():
            for pattern_config in tool_patterns:
                match = self._try_pattern_match(output, pattern_config)
                if match:
                    return match
        
        return None
    
    def _try_pattern_match(self, output: str, pattern_config: Dict[str, Any]) -> Optional[MatchResult]:
        """
        Try to match output against a single pattern.
        
        Args:
            output: Tool output to match
            pattern_config: Pattern configuration dict
            
        Returns:
            MatchResult if match successful, None otherwise
        """
        try:
            regex_pattern = pattern_config["pattern"]
            match = re.search(regex_pattern, output, re.MULTILINE | re.DOTALL)
            
            if match:
                # Extract matched groups
                matched_groups = [match.group(0)]  # Full match
                matched_groups.extend(match.groups())  # Capture groups
                
                return MatchResult(
                    pattern_id=pattern_config["id"],
                    tool=pattern_config["tool"],
                    fix_command=pattern_config["fix_command"],
                    commit_message_template=pattern_config["commit_message_template"],
                    severity=pattern_config["severity"],
                    requires_git_commit=pattern_config["requires_git_commit"],
                    matched_groups=matched_groups,
                    original_output=output,
                    description=pattern_config["description"]
                )
        except re.error as e:
            # Log invalid regex but don't fail completely
            print(f"Warning: Invalid regex in pattern {pattern_config.get('id', 'unknown')}: {e}")
        except KeyError as e:
            print(f"Warning: Missing required field in pattern config: {e}")
        
        return None
    
    def get_patterns_by_tool(self, tool: str) -> List[Dict[str, Any]]:
        """
        Get all patterns for a specific tool.
        
        Args:
            tool: Tool name (e.g., 'ruff', 'black', 'isort')
            
        Returns:
            List of pattern configurations for the tool
        """
        return self.patterns.get(tool, [])
    
    def get_all_tools(self) -> List[str]:
        """
        Get list of all tools that have patterns defined.
        
        Returns:
            List of tool names
        """
        return list(self.patterns.keys())
    
    def get_engine_config(self) -> Dict[str, Any]:
        """Get engine configuration."""
        return self.engine_config.copy()
    
    def get_git_config(self) -> Dict[str, Any]:
        """Get git configuration."""
        return self.git_config.copy()
    
    def match_specific_tool(self, output: str, tool: str) -> Optional[MatchResult]:
        """
        Match output against patterns for a specific tool only.
        
        Args:
            output: Tool output to match
            tool: Specific tool name to check patterns for
            
        Returns:
            MatchResult if a pattern matches, None otherwise
        """
        tool_patterns = self.patterns.get(tool, [])
        
        for pattern_config in tool_patterns:
            match = self._try_pattern_match(output, pattern_config)
            if match:
                return match
        
        return None
    
    def validate_patterns(self) -> List[str]:
        """
        Validate all patterns and return list of validation errors.
        
        Returns:
            List of validation error messages (empty if all patterns valid)
        """
        errors = []
        
        for tool_name, tool_patterns in self.patterns.items():
            for pattern_config in tool_patterns:
                # Check required fields
                required_fields = [
                    "id", "name", "pattern", "description", "fix_command",
                    "tool", "severity", "requires_git_commit", "commit_message_template"
                ]
                
                for field in required_fields:
                    if field not in pattern_config:
                        errors.append(f"Pattern {pattern_config.get('id', 'unknown')} missing field: {field}")
                
                # Validate regex pattern
                try:
                    re.compile(pattern_config.get("pattern", ""))
                except re.error as e:
                    errors.append(f"Invalid regex in pattern {pattern_config.get('id', 'unknown')}: {e}")
                
                # Validate severity
                if pattern_config.get("severity") not in ["low", "medium", "high"]:
                    errors.append(f"Invalid severity in pattern {pattern_config.get('id', 'unknown')}: {pattern_config.get('severity')}")
        
        return errors