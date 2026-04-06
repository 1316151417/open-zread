import argparse
import os

from pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Code Deep Research - Automated codebase analysis"
    )
    parser.add_argument(
        "project_path",
        help="Path to the project to analyze",
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai"],
        help="LLM provider to use (default: anthropic)",
    )
    parser.add_argument(
        "--max-modules",
        type=int,
        default=5,
        help="Maximum number of modules to research in depth (default: 5)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=15,
        help="Maximum ReAct steps per sub-agent (default: 15)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    project_path = os.path.abspath(args.project_path)
    if not os.path.isdir(project_path):
        print(f"Error: {project_path} is not a directory")
        return 1

    report = run_pipeline(
        project_path=project_path,
        provider=args.provider,
        max_sub_agents=args.max_modules,
        max_sub_agent_steps=args.max_steps,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to {args.output}")
    else:
        print("\n" + "=" * 60)
        print(report)

    return 0


if __name__ == "__main__":
    exit(main())
