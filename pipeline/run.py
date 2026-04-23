"""Pipeline 主入口：6 阶段编排."""
import os
from datetime import datetime

from settings import load_settings, get_lite_config, get_pro_config, get_max_config
from pipeline.types import PipelineContext
from pipeline.scanner import scan_project
from pipeline.llm_filter import llm_filter_files
from pipeline.decomposer import decompose_into_modules
from pipeline.scorer import score_and_rank_modules
from pipeline.researcher import research_modules
from pipeline.aggregator import aggregate_reports

from langfuse import observe, propagate_attributes
import uuid


@observe(name="scan_project")
def _observed_scan_project(ctx, session_id):
    with propagate_attributes(session_id=session_id):
        return scan_project(ctx)


@observe(name="llm_filter_files")
def _observed_llm_filter_files(ctx, session_id):
    with propagate_attributes(session_id=session_id):
        return llm_filter_files(ctx)


@observe(name="decompose_into_modules")
def _observed_decompose_into_modules(ctx, session_id):
    with propagate_attributes(session_id=session_id):
        return decompose_into_modules(ctx)


@observe(name="score_and_rank_modules")
def _observed_score_and_rank_modules(ctx, session_id):
    with propagate_attributes(session_id=session_id):
        return score_and_rank_modules(ctx)


@observe(name="research_modules")
def _observed_research_modules(ctx, report_dir, modules, session_id):
    module_names = ",".join(m.name for m in modules)
    with propagate_attributes(session_id=session_id, tags=[f"modules:{module_names}"]):
        return research_modules(ctx, report_dir, modules)


@observe(name="aggregate_reports")
def _observed_aggregate_reports(ctx, modules, session_id):
    with propagate_attributes(session_id=session_id):
        return aggregate_reports(ctx, modules)


def run_pipeline(
    project_path: str,
    settings_path: str | None = None,
) -> str:
    """运行完整分析流水线。"""
    session_id = f"pipeline-{uuid.uuid4().hex[:8]}"

    settings = load_settings(settings_path)
    project_path = os.path.abspath(project_path)
    project_name = os.path.basename(project_path)

    lite_config = get_lite_config()
    pro_config = get_pro_config()
    max_config = get_max_config()
    max_sub_agent_steps = settings["max_sub_agent_steps"]
    research_parallel = settings["research_parallel"]
    research_threads = settings["research_threads"]

    print(f"模型配置: lite={lite_config['model']}, pro={pro_config['model']}, max={max_config['model']}")

    ctx = PipelineContext(
        project_path=project_path,
        project_name=project_name,
        lite_config=lite_config,
        pro_config=pro_config,
        max_config=max_config,
        max_sub_agent_steps=max_sub_agent_steps,
        research_parallel=research_parallel,
        research_threads=research_threads,
        settings=settings,
    )

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    report_dir = os.path.join(os.getcwd(), ".report", project_name, timestamp)
    os.makedirs(report_dir, exist_ok=True)
    print(f"报告输出目录: {report_dir}")

    # ====== 阶段 1: 扫描 ======
    print(f"\n{'='*60}\n阶段 1/6: 扫描项目 [{project_name}]\n{'='*60}")
    _observed_scan_project(ctx, session_id)
    print(f"  扫描到 {len(ctx.all_files)} 个文件")

    # ====== 阶段 2: LLM 过滤 ======
    print(f"\n{'='*60}\n阶段 2/6: LLM 智能过滤\n{'='*60}")
    _observed_llm_filter_files(ctx, session_id)
    important_count = sum(1 for f in ctx.all_files if f.is_important)
    print(f"  保留 {important_count} 个重要文件")

    # ====== 阶段 3: 模块拆分 ======
    print(f"\n{'='*60}\n阶段 3/6: 模块拆分\n{'='*60}")
    _observed_decompose_into_modules(ctx, session_id)
    print(f"  识别到 {len(ctx.modules)} 个模块:")
    for m in ctx.modules:
        print(f"    - {m.name}: {m.description} ({len(m.files)} 个文件)")

    # ====== 阶段 4: 模块打分 ======
    print(f"\n{'='*60}\n阶段 4/6: 模块重要性打分\n{'='*60}")
    _observed_score_and_rank_modules(ctx, session_id)
    print(f"  模块评分（从高到低）:")
    for m in ctx.modules:
        print(f"    - {m.name}: {m.score:.0f}分")
    print(f"  共 {len(ctx.modules)} 个模块，全部进行深度研究")

    # ====== 阶段 5: 深度研究 ======
    print(f"\n{'='*60}\n阶段 5/6: 子模块深度研究\n{'='*60}")
    _observed_research_modules(ctx, report_dir, ctx.modules, session_id)

    # ====== 阶段 6: 汇总报告 ======
    print(f"\n{'='*60}\n阶段 6/6: 汇总最终报告\n{'='*60}")
    _observed_aggregate_reports(ctx, ctx.modules, session_id)

    final_path = os.path.join(report_dir, f"最终报告-{ctx.project_name}.md")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(ctx.final_report)

    print(f"\n{'='*60}")
    print(f"分析完成！共 {len(ctx.modules)} 个模块报告 + 1 份最终报告")
    print(f"报告目录: {report_dir}")
    print(f"{'='*60}")
    return ctx.final_report
