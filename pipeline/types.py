from dataclasses import dataclass, field


@dataclass
class FileInfo:
    path: str
    size: int
    file_type: str = ""  # code, doc, config, log
    is_important: bool = True


@dataclass
class Module:
    name: str
    description: str
    files: list[str]
    score: float = 0.0
    research_report: str = ""


@dataclass
class PipelineContext:
    project_path: str
    project_name: str
    lite_config: dict = field(default_factory=dict)
    pro_config: dict = field(default_factory=dict)
    max_config: dict = field(default_factory=dict)
    max_sub_agent_steps: int = 30
    research_parallel: bool = False
    research_threads: int = 4
    settings: dict = field(default_factory=dict)

    # Stage 1: scanner output
    all_files: list[FileInfo] = field(default_factory=list)

    # Stage 3: decomposer output
    modules: list[Module] = field(default_factory=list)

    # Stage 5: aggregator output
    final_report: str = ""

    @property
    def provider(self) -> str:
        """Legacy property for backward compatibility."""
        return self.lite_config.get("provider", "anthropic")

    @property
    def lite_model(self) -> str:
        """Legacy property for backward compatibility."""
        return self.lite_config.get("model", "deepseek-chat")

    @property
    def pro_model(self) -> str:
        """Legacy property for backward compatibility."""
        return self.pro_config.get("model", "deepseek-chat")

    @property
    def max_model(self) -> str:
        """Legacy property for backward compatibility."""
        return self.max_config.get("model", "deepseek-reasoner")
