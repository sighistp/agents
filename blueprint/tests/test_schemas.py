"""Tests for Agent output schemas (Pydantic models)."""
import pytest


def test_pm_output_valid():
    """PM output with valid user stories and features should pass validation."""
    from blueprint.agents.schemas import PMOutput, UserStory, Feature

    output = PMOutput(
        user_stories=[
            UserStory(
                id="US-001",
                title="Create todo",
                description="User can create a new todo item",
                acceptance_criteria=["Given a form, when user submits, then todo is created"],
                priority="high"
            )
        ],
        features=[
            Feature(
                name="Todo CRUD",
                description="Basic todo operations",
                priority="high",
                related_stories=["US-001"]
            )
        ],
        technical_constraints=["Must use Python 3.12+"]
    )

    assert len(output.user_stories) == 1
    assert output.user_stories[0].id == "US-001"
    assert len(output.features) == 1
    assert output.needs_clarification is False
    assert output.clarification_questions == []


def test_pm_output_empty_stories():
    """PM output with empty user stories should fail validation."""
    from blueprint.agents.schemas import PMOutput
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PMOutput(
            user_stories=[],
            features=[],
            technical_constraints=[]
        )


def test_pm_output_with_clarification():
    """PM output with clarification flag should store questions."""
    from blueprint.agents.schemas import PMOutput, UserStory

    output = PMOutput(
        user_stories=[
            UserStory(
                id="US-001",
                title="Create todo",
                description="User can create a new todo item",
                acceptance_criteria=["Given a form, when user submits, then todo is created"],
                priority="high"
            )
        ],
        features=[],
        technical_constraints=[],
        needs_clarification=True,
        clarification_questions=["What database should be used?", "Is authentication required?"]
    )

    assert output.needs_clarification is True
    assert len(output.clarification_questions) == 2


def test_architect_output_valid():
    """Architect output with valid API definitions and data models should pass."""
    from blueprint.agents.schemas import ArchitectOutput, APIEndpoint, DataModel

    output = ArchitectOutput(
        architecture_description="REST API with SQLite backend",
        tech_stack={"backend": "FastAPI", "database": "SQLite"},
        modules=["api", "models", "services"],
        api_definitions=[
            APIEndpoint(
                method="GET",
                path="/api/todos",
                description="List all todos"
            ),
            APIEndpoint(
                method="POST",
                path="/api/todos",
                description="Create a todo",
                request_body={"title": "string"},
                response_body={"id": "int", "title": "string", "done": "bool"}
            )
        ],
        data_models=[
            DataModel(
                name="Todo",
                fields={"id": "int", "title": "str", "done": "bool"},
                relationships=[]
            )
        ]
    )

    assert len(output.api_definitions) == 2
    assert output.api_definitions[0].method == "GET"
    assert len(output.data_models) == 1
    assert output.data_models[0].name == "Todo"


def test_developer_output_valid():
    """Developer output with valid code files should pass."""
    from blueprint.agents.schemas import DeveloperOutput, CodeFile

    output = DeveloperOutput(
        files=[
            CodeFile(
                path="main.py",
                content="print('hello')",
                language="python"
            ),
            CodeFile(
                path="index.html",
                content="<html><body>Hello</body></html>",
                language="html"
            )
        ],
        dependencies=["flask", "requests"]
    )

    assert len(output.files) == 2
    assert output.files[0].path == "main.py"
    assert output.files[1].language == "html"
    assert "flask" in output.dependencies


def test_tester_output_valid():
    """Tester output with test cases and results should pass."""
    from blueprint.agents.schemas import TesterOutput, TestCase, TestResult

    output = TesterOutput(
        test_cases=[
            TestCase(
                id="TC-001",
                name="test_create_todo",
                description="Test creating a todo item",
                code="def test_create_todo(): assert True",
                expected="Pass"
            )
        ],
        test_results=[
            TestResult(
                test_id="TC-001",
                passed=True,
                output="1 passed"
            )
        ],
        all_passed=True,
        coverage_summary="80% coverage"
    )

    assert len(output.test_cases) == 1
    assert len(output.test_results) == 1
    assert output.all_passed is True


def test_reviewer_output_valid():
    """Reviewer output with only warning issues should be auto-approved."""
    from blueprint.agents.schemas import ReviewerOutput, ReviewIssue

    output = ReviewerOutput(
        issues=[
            ReviewIssue(
                file="main.py",
                line=10,
                severity="warning",
                description="Missing docstring",
                suggestion="Add docstring to function"
            )
        ],
        summary="Code quality is good, one minor suggestion"
    )

    assert len(output.issues) == 1
    assert output.issues[0].severity == "warning"
    assert output.approved is True  # Auto-computed: no critical issues


def test_reviewer_output_critical_not_approved():
    """Reviewer output with critical issues should be auto-rejected."""
    from blueprint.agents.schemas import ReviewerOutput, ReviewIssue

    output = ReviewerOutput(
        issues=[
            ReviewIssue(
                file="main.py",
                line=10,
                severity="critical",
                description="SQL injection vulnerability",
                suggestion="Use parameterized queries"
            )
        ],
        summary="Critical security issue found"
    )

    assert output.approved is False  # Auto-computed: has critical issue
    assert output.issues[0].severity == "critical"
