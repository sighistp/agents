"""ProjectState definition for LangGraph."""
from typing import Annotated, TypedDict

# Maximum number of messages to keep in state
MAX_MESSAGES = 100


def add_messages_with_limit(existing: list, new: list) -> list:
    """Add messages to existing list, truncating if over limit."""
    combined = existing + new
    if len(combined) > MAX_MESSAGES:
        # Keep the most recent messages
        combined = combined[-MAX_MESSAGES:]
    return combined


class ProjectState(TypedDict):
    """State schema for the multi-agent development workflow."""

    # Project identification
    project_id: str

    # Requirements
    requirement: str
    user_stories: list[dict]
    features: list[dict]

    # Architecture
    architecture: dict
    api_definitions: list[dict]
    data_models: list[dict]

    # Code
    project_dir: str           # 项目工作目录
    files: dict[str, str]  # {file_path: content}

    # Testing
    test_cases: list[dict]
    test_results: list[dict]
    test_passed: bool

    # Review
    review_comments: list[dict]
    review_approved: bool

    # Flow control
    current_agent: str
    iteration: int
    max_iterations: int
    status: str  # running/delivered/failed
    error: str | None
    need_human_confirm: bool
    human_approved: bool | None

    # User feedback (for rethink mechanism)
    user_feedback: str | None
    rethink_count: dict[str, int]  # {"pm": 0, "architect": 0, ...}

    # Retry counts (set by agent nodes, checked by route functions)
    _pm_retry_count: int
    _architect_retry_count: int
    _developer_retry_count: int

    # Messages (auto-appended with limit)
    messages: Annotated[list, add_messages_with_limit]


def create_initial_state(project_id: str, requirement: str) -> ProjectState:
    """Create an initial ProjectState with default values.

    Args:
        project_id: Unique project identifier
        requirement: User's original requirement text

    Returns:
        ProjectState with sensible defaults
    """
    from devteam.config import settings

    from pathlib import Path
    project_dir = str(Path("projects") / project_id)

    return ProjectState(
        project_id=project_id,
        requirement=requirement,
        project_dir=project_dir,
        user_stories=[],
        features=[],
        architecture={},
        api_definitions=[],
        data_models=[],
        files={},
        test_cases=[],
        test_results=[],
        test_passed=False,
        review_comments=[],
        review_approved=False,
        current_agent="pm",
        iteration=0,
        max_iterations=settings.max_iterations,
        status="running",
        error=None,
        need_human_confirm=True,
        human_approved=None,
        user_feedback=None,
        rethink_count={},
        _pm_retry_count=0,
        _architect_retry_count=0,
        _developer_retry_count=0,
        messages=[]
    )
