from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    MESSAGE_START = "message_start"
    CONTENT_DELTA = "content_delta"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    MESSAGE_END = "message_end"


@dataclass
class Event:
    type: EventType
    content: str | None = None
    tool_index: int | None = None
    tool_name: str | None = None
    tool_arguments: str | None = None
    finish_reason: str | None = None


@dataclass
class ToolProperty:
    type: str
    description: str
    enum: list[str] | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, ToolProperty]
    required: list[str] = field(default_factory=list)

    def to_openai(self) -> dict:
        properties = {}
        for key, prop in self.parameters.items():
            prop_dict = {
                "type": prop.type,
                "description": prop.description,
            }
            if prop.enum:
                prop_dict["enum"] = prop.enum
            properties[key] = prop_dict

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": self.required,
                },
            },
        }

    def to_anthropic(self) -> dict:
        properties = {}
        for key, prop in self.parameters.items():
            prop_dict = {
                "type": prop.type,
                "description": prop.description,
            }
            if prop.enum:
                prop_dict["enum"] = prop.enum
            properties[key] = prop_dict

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": self.required,
            },
        }
