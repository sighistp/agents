"""Tests for LangGraph graph structure."""
import pytest


def test_graph_compiles():
    """Graph should compile without errors."""
    from devteam.agents.graph import create_graph

    app = create_graph()
    assert app is not None


def test_graph_has_all_nodes():
    """Graph should have all required nodes."""
    from devteam.agents.graph import create_graph

    app = create_graph()
    # Get the graph structure
    graph = app.get_graph()

    # Check nodes exist
    nodes = set(graph.nodes)
    assert "pm" in nodes
    assert "architect" in nodes
    assert "developer" in nodes
    assert "tester" in nodes
    assert "reviewer" in nodes
    assert "human_confirm" in nodes
    assert "deliver" in nodes


def test_graph_starts_with_pm():
    """Graph should start with PM node."""
    from devteam.agents.graph import create_graph
    from devteam.agents.state import create_initial_state

    app = create_graph()
    state = create_initial_state("test-123", "Build a calculator")

    # The first node after START should be pm
    # We can verify this by checking the graph edges
    graph = app.get_graph()
    # START node should have edge to pm
    assert "pm" in [str(edge.target) for edge in graph.edges if str(edge.source) == "__start__"]


def test_route_after_pm_proceed():
    """route_after_pm should return 'proceed' when no error."""
    from devteam.agents.graph import route_after_pm

    state = {"error": None}
    assert route_after_pm(state) == "proceed"


def test_route_after_pm_error():
    """route_after_pm should return 'pm' on error (retry)."""
    from devteam.agents.graph import route_after_pm

    state = {"error": "Some error"}
    assert route_after_pm(state) == "pm"


def test_route_after_pm_timeout():
    """route_after_pm should return END on timeout error."""
    from devteam.agents.graph import route_after_pm
    from langgraph.graph import END

    state = {"error": "LLM timeout occurred"}
    assert route_after_pm(state) == END


def test_route_after_developer_proceed():
    """route_after_developer should return 'tester' when no error."""
    from devteam.agents.graph import route_after_developer

    state = {"error": None}
    assert route_after_developer(state) == "tester"


def test_route_after_developer_security_error():
    """route_after_developer should return END on security error."""
    from devteam.agents.graph import route_after_developer
    from langgraph.graph import END

    state = {"error": "Security violation: path injection detected"}
    assert route_after_developer(state) == END


def test_route_after_test_pass():
    """route_after_test should return 'pass' key when tests pass."""
    from devteam.agents.graph import route_after_test

    state = {"test_passed": True, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "reviewer" in add_conditional_edges
    assert route_after_test(state) == "pass"


def test_route_after_test_fail():
    """route_after_test should return 'fail' key when tests fail."""
    from devteam.agents.graph import route_after_test

    state = {"test_passed": False, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "developer" in add_conditional_edges
    assert route_after_test(state) == "fail"


def test_route_after_test_max_iterations():
    """route_after_test should return 'pass' key when max iterations reached."""
    from devteam.agents.graph import route_after_test

    state = {"test_passed": False, "iteration": 3, "max_iterations": 3}
    assert route_after_test(state) == "pass"


def test_route_after_review_approve():
    """route_after_review should return 'approve' key when approved."""
    from devteam.agents.graph import route_after_review

    state = {"review_approved": True, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "deliver" in add_conditional_edges
    assert route_after_review(state) == "approve"


def test_route_after_review_reject():
    """route_after_review should return 'reject' key when rejected."""
    from devteam.agents.graph import route_after_review

    state = {"review_approved": False, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "developer" in add_conditional_edges
    assert route_after_review(state) == "reject"


def test_route_after_architect_auto():
    """route_after_architect should return 'auto' key when no human confirm needed."""
    from devteam.agents.graph import route_after_architect

    state = {"need_human_confirm": False}
    # Returns key that maps to "developer" in add_conditional_edges
    assert route_after_architect(state) == "auto"


def test_route_after_architect_confirm():
    """route_after_architect should return 'confirm' key when confirm needed."""
    from devteam.agents.graph import route_after_architect

    state = {"need_human_confirm": True}
    # Returns key that maps to "human_confirm" in add_conditional_edges
    assert route_after_architect(state) == "confirm"
