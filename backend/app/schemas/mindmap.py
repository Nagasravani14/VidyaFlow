"""
Pydantic schema and validators for Chapter Mind Maps.

Schema specification:
{"title": str, "branches": [{"label": str, "children": [{"label": str, "note": str|null}]}]}
Limits:
- 4 to 8 branches
- 2 to 6 children per branch
- Labels under 60 characters
- Depth of exactly 2 levels below the root (root -> branches -> children)
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class MindMapChild(BaseModel):
    label: str = Field(..., description="Concept/topic subtopic label")
    note: Optional[str] = Field(default=None, description="Optional brief context, definition or formula")

    @field_validator("label")
    def validate_label(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("Child label cannot be empty")
        if len(s) > 60:
            raise ValueError(f"Child label must be under 60 characters (got {len(s)}: '{s}')")
        return s


class MindMapBranch(BaseModel):
    label: str = Field(..., description="Main theme / section branch label")
    children: List[MindMapChild] = Field(..., description="2 to 6 subtopic children")

    @field_validator("label")
    def validate_label(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("Branch label cannot be empty")
        if len(s) > 60:
            raise ValueError(f"Branch label must be under 60 characters (got {len(s)}: '{s}')")
        return s

    @field_validator("children")
    def validate_children_count(cls, v: List[MindMapChild]) -> List[MindMapChild]:
        if not (2 <= len(v) <= 6):
            raise ValueError(f"Each branch must have between 2 and 6 children, got {len(v)}")
        return v


class MindMapSchema(BaseModel):
    title: str = Field(..., max_length=200, description="Chapter title / Root topic")
    branches: List[MindMapBranch] = Field(..., description="4 to 8 main branches")

    @field_validator("title")
    def validate_title(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("Mind map title cannot be empty")
        return s

    @field_validator("branches")
    def validate_branches_count(cls, v: List[MindMapBranch]) -> List[MindMapBranch]:
        if not (4 <= len(v) <= 8):
            raise ValueError(f"Mind map must have between 4 and 8 branches, got {len(v)}")
        return v
