"""
BaseTool & ToolSchema — 工具系统的抽象基类
所有工具必须继承 BaseTool 并实现 execute()
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class ToolParameter(BaseModel):
    """单个工具参数的 Schema"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: list[str] | None = None


class ToolSchema(BaseModel):
    """工具的 JSON Schema 描述（用于 LLM function calling）"""
    type: str = "function"
    function: dict

    @classmethod
    def build(cls, name: str, description: str, parameters: list[ToolParameter]) -> dict:
        """构建符合 OpenAI function calling 格式的 schema"""
        props = {}
        required = []
        for p in parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            props[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }


class BaseTool(ABC):
    """
    所有工具的基类
    子类需实现:
      - name: 工具名
      - description: 工具描述
      - parameters: 参数列表
      - execute(**kwargs): 异步执行逻辑
    """

    name: str = ""
    description: str = ""
    parameters: list[ToolParameter] = []

    def schema(self) -> dict:
        return ToolSchema.build(self.name, self.description, self.parameters)

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """执行工具，返回结果"""
        ...
