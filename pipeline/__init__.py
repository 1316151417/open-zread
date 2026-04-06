import os

from pipeline.types import PipelineContext
from pipeline.scanner import scan_project
from pipeline.llm_filter import llm_filter_files
from pipeline.decomposer import decompose_into_modules
from pipeline.scorer import score_and_rank_modules
from pipeline.researcher import research_modules
from pipeline.aggregator import aggregate_reports


def run_pipeline(
    project_path: str,
    provider: str = "anthropic",
    max_sub_agents: int = 5,
    max_sub_agent_steps: int = 15,
) -> str:
    project_path = os.path.abspath(project_path)
    project_name = os.path.basename(project_path)

    ctx = PipelineContext(
        project_path=project_path,
        project_name=project_name,
        provider=provider,
        max_sub_agents=max_sub_agents,
        max_sub_agent_steps=max_sub_agent_steps,
    )

    # Stage 1: Scan + basic filter
    print(f"Scanning project: {project_name}")
    scan_project(ctx)
    print(f"  Found {len(ctx.all_files)} files, {len(ctx.filtered_files)} after basic filter")

    # Stage 2: LLM filter
    print("LLM filtering files...")
    llm_filter_files(ctx)
    print(f"  {len(ctx.important_files)} files deemed important")

    # Stage 3: Decompose into modules
    print("Decomposing into modules...")
    decompose_into_modules(ctx)
    print(f"  Identified {len(ctx.modules)} modules")

    # Stage 4: Score and rank
    print("Scoring modules...")
    score_and_rank_modules(ctx)
    print(f"  Selected top {len(ctx.selected_modules)} modules for deep research")

    # Stage 5: Research each module
    print("Starting deep research...")
    research_modules(ctx)

    # Stage 6: Aggregate reports
    print("Aggregating final report...")
    aggregate_reports(ctx)

    print("Done!")
    return ctx.final_report
