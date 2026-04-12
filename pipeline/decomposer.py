"""Stage 3: 模块拆分 - 按目录结构 + import 关系划分模块."""
import json

from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import DECOMPOSER_SYSTEM, DECOMPOSER_USER


def decompose_into_modules(ctx: PipelineContext) -> None:
    file_list = "\n".join(f"  {f.path} ({f.size}B)" for f in ctx.important_files)
    user_msg = DECOMPOSER_USER.format(project_name=ctx.project_name, file_list=file_list)

    response = call_llm(ctx.provider, DECOMPOSER_SYSTEM, user_msg, model=ctx.lite_model)

    try:
        raw_modules = json.loads(extract_json(response))
    except json.JSONDecodeError:
        ctx.modules = _fallback_decompose(ctx.important_files)
        return

    modules = []
    existing_paths = {f.path for f in ctx.important_files}
    for m in raw_modules:
        name = m.get("name", "unknown")
        description = m.get("description", "")
        files = m.get("files", [])
        valid_files = [f for f in files if f in existing_paths]
        if valid_files:
            modules.append(Module(name=name, description=description, files=valid_files))

    ctx.modules = modules if modules else _fallback_decompose(ctx.important_files)


def _fallback_decompose(files) -> list[Module]:
    groups = {}
    for f in files:
        parts = f.path.split("/")
        group_key = parts[0] if len(parts) > 1 else "root"
        groups.setdefault(group_key, []).append(f.path)
    return [Module(name=key, description=f"Files in {key}/", files=paths) for key, paths in groups.items()]
