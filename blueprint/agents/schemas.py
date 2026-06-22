"""Pydantic schemas for Agent output validation."""
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class UserStory(BaseModel):
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: Literal["high", "medium", "low"]


class Feature(BaseModel):
    name: str
    description: str
    priority: Literal["high", "medium", "low"]
    related_stories: list[str]


class PMOutput(BaseModel):
    user_stories: list[UserStory]
    features: list[Feature]
    technical_constraints: list[str]
    needs_clarification: bool = False
    clarification_questions: list[str] = []

    @field_validator("user_stories")
    @classmethod
    def user_stories_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError("user_stories cannot be empty")
        return v


class APIEndpoint(BaseModel):
    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: str
    description: str
    request_body: dict | None = None
    response_body: dict | None = None


class DataModel(BaseModel):
    name: str
    fields: dict[str, str]  # {field_name: type}
    relationships: list[str] = []


class ArchitectOutput(BaseModel):
    architecture_description: str
    tech_stack: dict[str, str | None]  # 允许None（如计算器不需要数据库）
    modules: list[str]
    api_definitions: list[APIEndpoint]
    data_models: list[DataModel]


class CodeFile(BaseModel):
    path: str
    content: str
    language: Literal[
        "python", "html", "js", "javascript", "css", "sql",
        "json", "yaml", "markdown", "shell", "typescript",
        "java", "go", "rust", "c", "cpp", "text"
    ]


class DeveloperOutput(BaseModel):
    files: list[CodeFile]
    dependencies: list[str]


class TestCase(BaseModel):
    id: str
    name: str
    description: str
    code: str
    expected: str


class TestResult(BaseModel):
    test_id: str
    passed: bool
    output: str
    error: str | None = None


class TesterOutput(BaseModel):
    test_cases: list[TestCase]
    test_results: list[TestResult]
    all_passed: bool
    coverage_summary: str


class ReviewIssue(BaseModel):
    file: str
    line: int | None = None
    severity: Literal["critical", "important", "minor"]
    description: str
    suggestion: str


class ReviewerOutput(BaseModel):
    issues: list[ReviewIssue]
    approved: bool = False  # Default, will be computed by validator
    summary: str

    @model_validator(mode="after")
    def compute_approved(self) -> "ReviewerOutput":
        """Auto-compute approved based on critical issues."""
        has_critical = any(i.severity == "critical" for i in self.issues)
        self.approved = not has_critical
        return self
