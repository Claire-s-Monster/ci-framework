"""
Cohesive formatting fix workflow controller.

This module orchestrates the complete automatic formatting fix process from
error detection to committed solution, integrating all components.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .command_executor import (
    CommandExecutionError,
    CommandResult,
    CommandTimeoutError,
    SafeCommandExecutor,
)
from .formatting_engine import FormattingPatternEngine, MatchResult
from .syntax_verifier import (
    GitCommitResult,
    GitOperationError,
    SyntaxVerificationError,
    SyntaxVerifierAndCommitter,
)


@dataclass
class WorkflowResult:
    """Result of the complete formatting workflow."""

    success: bool
    message: str
    pattern_matched: str | None = None
    tool_used: str | None = None
    command_executed: str | None = None
    files_fixed: list[str] = None  # type: ignore
    commit_result: GitCommitResult | None = None
    execution_time: float = 0.0
    error_details: str | None = None

    def __post_init__(self):
        if self.files_fixed is None:
            self.files_fixed = []


class FormattingWorkflowError(Exception):
    """Raised when the formatting workflow encounters an error."""

    pass


class FormattingFixWorkflow:
    """
    Main controller for the automatic formatting fix workflow.

    Orchestrates pattern matching, command execution, syntax verification,
    and git commit operations.
    """

    def __init__(
        self,
        working_directory: str | None = None,
        config_path: str | None = None,
        command_timeout: int = 300,
        enable_logging: bool = True,
    ):
        """
        Initialize the formatting fix workflow.

        Args:
            working_directory: Working directory for operations
            config_path: Path to formatting.yml config file
            command_timeout: Timeout for command execution in seconds
            enable_logging: Whether to enable detailed logging
        """
        self.working_directory = Path(working_directory or ".").resolve()
        self.enable_logging = enable_logging

        # Initialize components
        self.pattern_engine = FormattingPatternEngine(config_path)
        self.command_executor = SafeCommandExecutor(
            default_timeout=command_timeout,
            working_directory=str(self.working_directory),
        )
        self.syntax_verifier = SyntaxVerifierAndCommitter(
            working_directory=str(self.working_directory)
        )

        # Setup logging
        if enable_logging:
            self._setup_logging()

        self.logger = logging.getLogger(__name__)

    def _setup_logging(self) -> None:
        """Setup logging for the workflow."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def process_tool_output(
        self,
        tool_output: str,
        dry_run: bool = False,
        verify_syntax: bool = True,
        create_commit: bool = True,
    ) -> WorkflowResult:
        """
        Process tool output through the complete formatting fix workflow.

        Args:
            tool_output: Raw stdout/stderr from formatting tool
            dry_run: Whether to perform a dry run (don't actually fix)
            verify_syntax: Whether to verify syntax after fixes
            create_commit: Whether to create git commit after fixes

        Returns:
            WorkflowResult with complete operation details
        """
        start_time = datetime.now()

        try:
            self.logger.info("Starting formatting workflow")
            self.logger.debug(f"Tool output: {tool_output[:200]}...")

            # Step 1: Pattern matching
            self.logger.info("Step 1: Analyzing tool output for fixable patterns")
            match_result = self.pattern_engine.match_output(tool_output)

            if not match_result:
                self.logger.info("No fixable patterns found in tool output")
                return WorkflowResult(
                    success=False,
                    message="No fixable formatting issues detected",
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )

            self.logger.info(
                f"Found fixable pattern: {match_result.pattern_id} for tool {match_result.tool}"
            )

            # Step 2: Command execution
            if dry_run:
                self.logger.info("Step 2: Executing dry-run command")
                command_result = self._execute_dry_run_command(match_result)

                return WorkflowResult(
                    success=True,
                    message=f"Dry run completed for {match_result.tool}",
                    pattern_matched=match_result.pattern_id,
                    tool_used=match_result.tool,
                    command_executed=command_result.command,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            else:
                self.logger.info("Step 2: Executing fix command")
                command_result = self._execute_fix_command(match_result)

            # Step 3: Syntax verification and commit
            if create_commit:
                self.logger.info("Step 3: Verifying syntax and creating commit")
                commit_result = self._verify_and_commit(match_result, verify_syntax)

                if commit_result.success:
                    self.logger.info(
                        f"Workflow completed successfully. Commit: {commit_result.commit_hash}"
                    )
                    return WorkflowResult(
                        success=True,
                        message=f"Successfully fixed and committed {match_result.tool} formatting issues",
                        pattern_matched=match_result.pattern_id,
                        tool_used=match_result.tool,
                        command_executed=command_result.command,
                        files_fixed=commit_result.files_committed,
                        commit_result=commit_result,
                        execution_time=(datetime.now() - start_time).total_seconds(),
                    )
                else:
                    self.logger.error(f"Commit failed: {commit_result.error_message}")
                    return WorkflowResult(
                        success=False,
                        message=f"Fix applied but commit failed: {commit_result.error_message}",
                        pattern_matched=match_result.pattern_id,
                        tool_used=match_result.tool,
                        command_executed=command_result.command,
                        commit_result=commit_result,
                        error_details=commit_result.error_message,
                        execution_time=(datetime.now() - start_time).total_seconds(),
                    )
            else:
                # Just apply fixes without committing
                self.logger.info("Step 3: Fix applied without commit")
                changed_files = self.syntax_verifier.get_changed_files()

                return WorkflowResult(
                    success=True,
                    message=f"Successfully applied {match_result.tool} formatting fixes",
                    pattern_matched=match_result.pattern_id,
                    tool_used=match_result.tool,
                    command_executed=command_result.command,
                    files_fixed=changed_files,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )

        except SyntaxVerificationError as e:
            self.logger.error(f"Syntax verification failed: {e}")
            return WorkflowResult(
                success=False,
                message=f"Syntax errors detected after formatting fix: {len(e.failed_files)} files",
                error_details=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

        except (CommandExecutionError, CommandTimeoutError) as e:
            self.logger.error(f"Command execution failed: {e}")
            return WorkflowResult(
                success=False,
                message=f"Failed to execute formatting command: {e}",
                error_details=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

        except GitOperationError as e:
            self.logger.error(f"Git operation failed: {e}")
            return WorkflowResult(
                success=False,
                message=f"Git operation failed: {e}",
                error_details=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

        except Exception as e:
            self.logger.error(f"Unexpected error in workflow: {e}")
            return WorkflowResult(
                success=False,
                message=f"Unexpected workflow error: {e}",
                error_details=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

    def _execute_dry_run_command(self, match_result: MatchResult) -> CommandResult:
        """Execute command in dry-run mode."""
        return self.command_executor.dry_run_command(
            command=match_result.fix_command,
            working_directory=str(self.working_directory),
        )

    def _execute_fix_command(self, match_result: MatchResult) -> CommandResult:
        """Execute the actual fix command."""
        return self.command_executor.execute_formatting_command(
            tool=match_result.tool,
            fix_command=match_result.fix_command,
            working_directory=str(self.working_directory),
        )

    def _verify_and_commit(
        self, match_result: MatchResult, verify_syntax: bool
    ) -> GitCommitResult:
        """Verify syntax and create commit."""
        git_config = self.pattern_engine.get_git_config()

        return self.syntax_verifier.atomic_format_commit(
            commit_message_template=match_result.commit_message_template,
            tool_name=match_result.tool,
            author=git_config.get("commit_author"),
            include_file_count=git_config.get("include_file_count", True),
            verify_syntax=verify_syntax,
        )

    def get_workflow_status(self) -> dict[str, Any]:
        """
        Get current workflow status and configuration.

        Returns:
            Dictionary with workflow status information
        """
        status = {
            "working_directory": str(self.working_directory),
            "is_git_repository": self.syntax_verifier.is_git_repository(),
            "available_patterns": len(sum(self.pattern_engine.patterns.values(), [])),
            "supported_tools": self.pattern_engine.get_all_tools(),
            "git_status": self.syntax_verifier.get_git_status_summary(),
            "engine_config": self.pattern_engine.get_engine_config(),
            "git_config": self.pattern_engine.get_git_config(),
        }

        return status

    def validate_configuration(self) -> list[str]:
        """
        Validate workflow configuration and return any errors.

        Returns:
            List of validation error messages
        """
        errors = []

        # Validate pattern engine
        pattern_errors = self.pattern_engine.validate_patterns()
        errors.extend(pattern_errors)

        # Validate working directory
        if not self.working_directory.exists():
            errors.append(f"Working directory does not exist: {self.working_directory}")

        # Validate git repository
        if not self.syntax_verifier.is_git_repository():
            errors.append("Working directory is not a git repository")

        # Validate tool availability
        supported_tools = self.pattern_engine.get_all_tools()
        for tool in supported_tools:
            tool_info = self.command_executor.get_command_info(tool)
            if not tool_info["available"]:
                errors.append(
                    f"Tool '{tool}' is not available: {tool_info.get('error', 'Unknown error')}"
                )

        return errors

    def test_pattern_matching(self, test_output: str) -> MatchResult | None:
        """
        Test pattern matching against sample output.

        Args:
            test_output: Sample tool output for testing

        Returns:
            MatchResult if pattern matches, None otherwise
        """
        return self.pattern_engine.match_output(test_output)

    def get_tool_info(self, tool: str) -> dict[str, Any]:
        """
        Get information about a specific formatting tool.

        Args:
            tool: Tool name

        Returns:
            Dictionary with tool information
        """
        return self.command_executor.get_command_info(tool)

    def process_multiple_outputs(
        self,
        tool_outputs: list[str],
        dry_run: bool = False,
        verify_syntax: bool = True,
        create_commit: bool = True,
    ) -> list[WorkflowResult]:
        """
        Process multiple tool outputs sequentially.

        Args:
            tool_outputs: List of tool outputs to process
            dry_run: Whether to perform dry runs
            verify_syntax: Whether to verify syntax after fixes
            create_commit: Whether to create commits after fixes

        Returns:
            List of WorkflowResult for each output processed
        """
        results = []

        for i, output in enumerate(tool_outputs):
            self.logger.info(f"Processing output {i + 1}/{len(tool_outputs)}")
            result = self.process_tool_output(
                tool_output=output,
                dry_run=dry_run,
                verify_syntax=verify_syntax,
                create_commit=create_commit,
            )
            results.append(result)

            # Continue processing all outputs regardless of individual failures
            if not result.success:
                self.logger.warning(f"Output {i + 1} failed: {result.message}")
            else:
                self.logger.info(f"Output {i + 1} processed successfully")

        return results
