"""
Dependency resolution engine for self-healing CI framework.

This module handles automatic detection and resolution of dependency-related issues
including outdated lock files, missing packages, and environment synchronization.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .command_executor import SafeCommandExecutor as CommandExecutor

logger = logging.getLogger(__name__)


@dataclass
class DependencyPattern:
    """Represents a dependency error pattern."""
    
    id: str
    name: str
    pattern: str
    description: str
    fix_command: Optional[str]
    tool: str
    severity: str
    requires_git_commit: bool
    commit_message_template: str
    capture_groups: Optional[List[Dict[str, any]]] = None
    custom_handler: Optional[str] = None


@dataclass
class DependencyMatch:
    """Represents a matched dependency pattern."""
    
    pattern_id: str
    tool: str
    fix_command: Optional[str]
    severity: str
    requires_git_commit: bool
    commit_message_template: str
    captured_data: Dict[str, str]
    custom_handler: Optional[str] = None
    handler_message: Optional[str] = None


class DependencyEngine:
    """
    Engine for detecting and fixing dependency-related issues.
    
    This engine loads dependency patterns from a YAML file and matches them
    against error output to identify fixable dependency issues.
    """
    
    def __init__(self, pattern_file: str = "dependencies.yml"):
        """
        Initialize the dependency engine.
        
        Args:
            pattern_file: Path to the dependency patterns YAML file
        """
        self.pattern_file = Path(__file__).parent / pattern_file
        self.patterns: Dict[str, List[DependencyPattern]] = {}
        self.custom_handlers: Dict[str, Dict[str, any]] = {}
        self.command_executor = CommandExecutor()
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load dependency patterns from YAML file."""
        if not self.pattern_file.exists():
            logger.warning(f"Pattern file not found: {self.pattern_file}")
            return
            
        try:
            with open(self.pattern_file, 'r') as f:
                data = yaml.safe_load(f)
                
            # Load patterns by category
            for category, patterns in data.get('patterns', {}).items():
                self.patterns[category] = []
                for pattern_data in patterns:
                    pattern = DependencyPattern(**pattern_data)
                    self.patterns[category].append(pattern)
                    
            # Load custom handlers
            self.custom_handlers = data.get('custom_handlers', {})
            
            logger.info(f"Loaded {sum(len(p) for p in self.patterns.values())} dependency patterns")
            
        except Exception as e:
            logger.error(f"Failed to load dependency patterns: {e}")
    
    def match_pattern(self, output: str) -> Optional[DependencyMatch]:
        """
        Match output against dependency patterns.
        
        Args:
            output: The error output to analyze
            
        Returns:
            DependencyMatch if a pattern is found, None otherwise
        """
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                regex = re.compile(pattern.pattern, re.IGNORECASE | re.MULTILINE)
                match = regex.search(output)
                
                if match:
                    captured_data = {}
                    
                    # Extract captured groups if defined
                    if pattern.capture_groups:
                        for group in pattern.capture_groups:
                            group_index = group['index']
                            group_name = group['name']
                            if group_index <= len(match.groups()):
                                captured_data[group_name] = match.group(group_index)
                    
                    # Prepare handler message if custom handler is defined
                    handler_message = None
                    if pattern.custom_handler and pattern.custom_handler in self.custom_handlers:
                        handler = self.custom_handlers[pattern.custom_handler]
                        if 'message_template' in handler:
                            handler_message = handler['message_template'].format(**captured_data)
                    
                    return DependencyMatch(
                        pattern_id=pattern.id,
                        tool=pattern.tool,
                        fix_command=pattern.fix_command,
                        severity=pattern.severity,
                        requires_git_commit=pattern.requires_git_commit,
                        commit_message_template=pattern.commit_message_template,
                        captured_data=captured_data,
                        custom_handler=pattern.custom_handler,
                        handler_message=handler_message
                    )
        
        return None
    
    def suggest_fix(self, output: str) -> Optional[Dict[str, any]]:
        """
        Analyze output and suggest a fix for dependency issues.
        
        Args:
            output: The error output to analyze
            
        Returns:
            Dictionary with fix information if a pattern matches, None otherwise
        """
        match = self.match_pattern(output)
        
        if not match:
            return None
            
        fix_info = {
            'pattern_id': match.pattern_id,
            'tool': match.tool,
            'severity': match.severity,
            'requires_git_commit': match.requires_git_commit,
            'commit_message': match.commit_message_template
        }
        
        if match.fix_command:
            fix_info['fix_command'] = match.fix_command
            fix_info['action'] = 'execute'
        elif match.custom_handler:
            fix_info['action'] = match.custom_handler
            fix_info['message'] = match.handler_message
            fix_info['captured_data'] = match.captured_data
        
        return fix_info
    
    def apply_fix(self, fix_info: Dict[str, any], dry_run: bool = False) -> Tuple[bool, str]:
        """
        Apply the suggested fix.
        
        Args:
            fix_info: Dictionary containing fix information
            dry_run: If True, only simulate the fix
            
        Returns:
            Tuple of (success, message)
        """
        action = fix_info.get('action', 'execute')
        
        if action == 'execute' and 'fix_command' in fix_info:
            if dry_run:
                return True, f"Would execute: {fix_info['fix_command']}"
                
            # Execute the fix command
            result = self.command_executor.execute(fix_info['fix_command'])
            
            if result.return_code == 0:
                return True, f"Successfully executed: {fix_info['fix_command']}"
            else:
                return False, f"Failed to execute {fix_info['fix_command']}: {result.stderr}"
                
        elif action == 'suggest_pixi_add':
            # Just return the suggestion message
            return True, fix_info['message']
            
        elif action == 'notify_conflict':
            # Return the conflict notification
            return False, fix_info['message']
            
        else:
            return False, f"Unknown action: {action}"
    
    def test_pattern_matching(self, output: str) -> Optional[DependencyMatch]:
        """
        Test pattern matching without applying fixes.
        
        Args:
            output: The output to test against patterns
            
        Returns:
            DependencyMatch if a pattern matches, None otherwise
        """
        return self.match_pattern(output)