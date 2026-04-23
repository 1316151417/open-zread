import argparse
import os

import dotenv
dotenv.load_dotenv()

from pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Code Deep Research - 自动化代码深度分析"
    )
    parser.add_argument(
        "project_path",
        help="要分析的项目路径",
    )
    parser.add_argument(
        "--settings",
        default=None,
        help="配置文件路径 (默认: 当前目录/settings.json)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出文件路径 (默认: 写入 .report/ 目录)",
    )

    args = parser.parse_args()

    project_path = os.path.abspath(args.project_path)
    if not os.path.isdir(project_path):
        print(f"错误: {project_path} 不是有效目录")
        return 1

    report = run_pipeline(
        project_path=project_path,
        settings_path=args.settings,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n报告已写入: {args.output}")

    return 0


if __name__ == "__main__":
    exit(main())
