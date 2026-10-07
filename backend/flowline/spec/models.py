"""Typed models for (1) workflows read from Excel and (2) the YAML execution plans."""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ----------------------------------------------------------------------------- Excel side
class TestRequest(BaseModel):
    request: str
    check: str = ""


class WorkflowSpec(BaseModel):
    """One row of the 'Workflows' sheet, parsed. The Excel file is the source of truth."""

    id: str
    name: str
    trigger: str
    inputs_text: str
    steps: list[str]
    decision_logic: str
    tools: list[str]
    expected_output: str
    test_requests: list[TestRequest] = Field(default_factory=list)
    excel_row: int = 0


# ----------------------------------------------------------------------------- Plan side
InputType = Literal["text", "number", "file", "date", "list", "identifier", "choice"]


class InputDef(BaseModel):
    name: str
    type: InputType = "text"
    label: Optional[str] = None
    description: str = ""
    required: bool = False
    default: Any = None
    ask: Optional[str] = None                 # question shown when the value is missing
    patterns: list[str] = Field(default_factory=list)   # offline extraction (first capture group)
    choices: list[str] = Field(default_factory=list)
    synonyms: dict[str, list[str]] = Field(default_factory=dict)
    sample: Optional[str] = None              # sample file offered in the UI for file inputs
    accept: list[str] = Field(default_factory=list)
    multiline: bool = False

    @property
    def display(self) -> str:
        return self.label or self.name.replace("_", " ").capitalize()


class ActionDef(BaseModel):
    action: Literal["continue", "complete", "ask", "escalate", "fail", "goto"] = "continue"
    message: Optional[str] = None
    fields: list[str] = Field(default_factory=list)      # inputs to ask for
    goto: Optional[str] = None                           # step id to resume from
    clear: list[str] = Field(default_factory=list)       # inputs to clear before asking


class StepDef(BaseModel):
    id: str
    title: str
    excel_step: Optional[Union[int, list[int]]] = None   # 1-based index (or indices) into the Excel Steps column
    kind: Literal["tool", "condition"] = "tool"
    # tool step
    tool: Optional[str] = None
    args: dict[str, Any] = Field(default_factory=dict)
    output: Optional[str] = None
    retry: int = 0
    on_error: Literal["fail", "continue"] = "fail"
    when: Optional[str] = None                # tool steps: skip unless true; condition steps: the test
    # condition step
    then: Optional[ActionDef] = None
    otherwise: Optional[ActionDef] = None
    note: Optional[str] = None                # human explanation of the decision rule

    @property
    def excel_steps(self) -> list[int]:
        if self.excel_step is None:
            return []
        return self.excel_step if isinstance(self.excel_step, list) else [self.excel_step]

    @field_validator("kind", mode="before")
    @classmethod
    def _infer_kind(cls, v: Any) -> Any:
        return v or "tool"


class SectionDef(BaseModel):
    type: Literal["summary", "kpis", "table", "content", "alert", "download", "list", "bars", "record"]
    title: Optional[str] = None
    when: Optional[str] = None
    # generic payload; rendered with templates against the run context
    text: Optional[str] = None
    tone: Optional[str] = None
    items: Any = None
    data: Any = None
    columns: list[Any] = Field(default_factory=list)
    highlight: Optional[dict[str, Any]] = None
    empty: Optional[str] = None
    fields: list[dict[str, Any]] = Field(default_factory=list)
    files: list[dict[str, Any]] = Field(default_factory=list)
    label: Optional[str] = None
    value: Optional[str] = None
    format: Optional[str] = None
    threshold: Any = None
    limit: Optional[int] = None


class ResultDef(BaseModel):
    title: str
    subtitle: Optional[str] = None
    sections: list[SectionDef] = Field(default_factory=list)


class ParamDef(BaseModel):
    """A decision parameter. ``from_excel`` reads it out of the Excel Decision_Logic text,
    so changing "10%" to "15%" in the spreadsheet changes behaviour with no code change."""

    default: Any
    from_excel: Optional[str] = None          # regex with one capture group
    description: str = ""
    override_patterns: list[str] = Field(default_factory=list)  # let the user's request override it


class Plan(BaseModel):
    workflow_id: str
    description: str = ""
    examples: list[str] = Field(default_factory=list)       # extra routing utterances
    params: dict[str, ParamDef] = Field(default_factory=dict)
    inputs: list[InputDef] = Field(default_factory=list)
    steps: list[StepDef]
    result: ResultDef

    def input(self, name: str) -> Optional[InputDef]:
        return next((i for i in self.inputs if i.name == name), None)

    def step_index(self, step_id: str) -> int:
        for i, s in enumerate(self.steps):
            if s.id == step_id:
                return i
        raise KeyError(step_id)


class Workflow(BaseModel):
    """An Excel spec joined with its plan (if any) and validation results."""

    spec: WorkflowSpec
    plan: Optional[Plan] = None
    plan_file: Optional[str] = None
    issues: list[str] = Field(default_factory=list)         # blocking problems
    warnings: list[str] = Field(default_factory=list)       # non-blocking notes
    params: dict[str, Any] = Field(default_factory=dict)    # resolved parameter values
    param_sources: dict[str, str] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def executable(self) -> bool:
        return self.plan is not None and not self.issues