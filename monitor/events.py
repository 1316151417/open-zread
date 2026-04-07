"""
Pipeline monitoring event types and event class.
Separated from base/types.py which handles ReAct streaming events.
"""
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any


class PipelineEventType(Enum):
    PIPELINE_START = "pipeline_start"
    PIPELINE_END = "pipeline_end"
    PIPELINE_ERROR = "pipeline_error"
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    STAGE_ERROR = "stage_error"
    STAGE_SCAN_COMPLETE = "stage_scan_complete"
    STAGE_FILTER_COMPLETE = "stage_filter_complete"
    STAGE_DECOMPOSE_COMPLETE = "stage_decompose_complete"
    STAGE_SCORE_COMPLETE = "stage_score_complete"
    STAGE_RESEARCH_COMPLETE = "stage_research_complete"
    STAGE_AGGREGATE_COMPLETE = "stage_aggregate_complete"
    LLM_CALL = "llm_call"
    LLM_ERROR = "llm_error"
    HEARTBEAT = "heartbeat"
    # Sub-node lifecycle
    SUB_NODE_START = "sub_node_start"
    SUB_NODE_END = "sub_node_end"
    # Evaluation result
    EVAL_RESULT = "eval_result"
    # Deep ReAct events
    LLM_STEP_START = "llm_step_start"
    LLM_STEP_END = "llm_step_end"
    LLM_TOOL_CALL = "llm_tool_call"
    LLM_TOOL_RESULT = "llm_tool_result"
    LLM_TOOL_ERROR = "llm_tool_error"
    LLM_CONTENT = "llm_content"


@dataclass
class PipelineEvent:
    event_id: str
    run_id: str
    type: PipelineEventType
    stage: str | None
    timestamp: str
    data: dict
    step: int = 1
    # Hierarchy fields for 3-layer monitoring
    sub_node_id: str | None = None       # e.g., "module_auth", "aggregate_generate"
    sub_node_name: str | None = None     # e.g., "认证模块", "生成Agent"
    operation_type: str | None = None    # e.g., "llm_call", "tool_call", "eval", "data_output"

    def to_dict(self) -> dict:
        d = {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "type": self.type.value,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "data": self.data,
            "step": self.step,
        }
        if self.sub_node_id is not None:
            d["sub_node_id"] = self.sub_node_id
        if self.sub_node_name is not None:
            d["sub_node_name"] = self.sub_node_name
        if self.operation_type is not None:
            d["operation_type"] = self.operation_type
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineEvent":
        d = dict(d)
        d["type"] = PipelineEventType(d["type"])
        d.setdefault("sub_node_id", None)
        d.setdefault("sub_node_name", None)
        d.setdefault("operation_type", None)
        return cls(**d)

    @staticmethod
    def new(
        run_id: str,
        event_type: PipelineEventType,
        stage: str | None,
        data: dict,
        step: int = 1,
        sub_node_id: str | None = None,
        sub_node_name: str | None = None,
        operation_type: str | None = None,
    ) -> "PipelineEvent":
        return PipelineEvent(
            event_id=uuid.uuid4().hex[:12],
            run_id=run_id,
            type=event_type,
            stage=stage,
            timestamp=datetime.now().isoformat(),
            data=data,
            step=step,
            sub_node_id=sub_node_id,
            sub_node_name=sub_node_name,
            operation_type=operation_type,
        )
