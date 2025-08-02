from typing import Any, Optional
from .formatting_workflow import FormattingFixWorkflow
from .dependency_workflow import DependencyFixWorkflow


class FailurePatternEngine:
    """
    Analyzes CI failure logs and determines possible fixes.
    
    This class integrates with both formatting and dependency workflows
    for automatic fixes and maintains backward compatibility.
    """

    def __init__(self, config_path: str = "", project_dir: str = "."):
        self.config_path = config_path
        self.project_dir = project_dir
        
        # Initialize formatting workflow
        self.formatting_workflow = FormattingFixWorkflow(
            working_directory=project_dir,
            config_path=config_path if config_path else None
        )
        
        # Initialize dependency workflow
        self.dependency_workflow = DependencyFixWorkflow(
            working_directory=project_dir,
            config_path=config_path if config_path else None
        )

    def analyze(self, failure_output: Optional[str] = None) -> Any | None:
        """
        Analyze failure logs and return a fix object if a known pattern is found.
        
        Args:
            failure_output: Optional failure output to analyze
            
        Returns:
            Fix object if a pattern is found, None otherwise
        """
        if failure_output:
            # Try formatting workflow first
            workflow_result = self.formatting_workflow.test_pattern_matching(failure_output)
            if workflow_result:
                return {
                    "type": "formatting-fix",
                    "pattern_id": workflow_result.pattern_id,
                    "tool": workflow_result.tool,
                    "fix_command": workflow_result.fix_command,
                    "workflow": self.formatting_workflow
                }
            
            # Try dependency workflow
            dependency_result = self.dependency_workflow.test_pattern_matching(failure_output)
            if dependency_result:
                return {
                    "type": "dependency-fix",
                    "pattern_id": dependency_result.pattern_id,
                    "tool": dependency_result.tool,
                    "fix_command": dependency_result.fix_command,
                    "severity": dependency_result.severity,
                    "workflow": self.dependency_workflow
                }
        
        # TODO: Add other types of pattern matching (build errors, import issues, etc.)
        
        # Fallback to dummy fix for backward compatibility
        return {"type": "dummy-fix", "details": "Simulated fix"}
