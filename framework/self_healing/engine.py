import argparse

from .applier import FixApplier, RollbackException
from .pattern_engine import FailurePatternEngine


def main():
    parser = argparse.ArgumentParser(description="Self-Healing CI Engine")
    parser.add_argument("--config", type=str, default="", help="Path to config file")
    parser.add_argument("--project-dir", type=str, default=".", help="Project directory")
    parser.add_argument("--timeout-minutes", type=int, default=10, help="Timeout in minutes")
    args = parser.parse_args()

    status = {"healed": "false", "rollback": "false", "error": ""}

    try:
        # Analyze failure patterns
        engine = FailurePatternEngine(config_path=args.config, project_dir=args.project_dir)
        fix = engine.analyze()
        if fix is None:
            status["healed"] = "false"
            status["error"] = "No applicable fix found"
        else:
            applier = FixApplier(project_dir=args.project_dir)
            try:
                applier.apply(fix)
                status["healed"] = "true"
            except RollbackException as re:
                applier.rollback()
                status["rollback"] = "true"
                status["error"] = f"Rollback triggered: {re}"
            except Exception as e:
                applier.rollback()
                status["rollback"] = "true"
                status["error"] = f"Unexpected error: {e}"
    except Exception as e:
        status["error"] = f"Engine error: {e}"

    # Write status for GitHub Action output
    status_file = f"{args.project_dir}/.self_healing_status"
    with open(status_file, "w") as f:
        for k, v in status.items():
            f.write(f"{k}={v}\n")

if __name__ == "__main__":
    main()
