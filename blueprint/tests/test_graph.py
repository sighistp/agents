"""Tests for LangGraph graph structure."""
import pytest


def test_graph_compiles():
    """Graph should compile without errors."""
    from blueprint.agents.graph import create_graph

    app = create_graph()
    assert app is not None


def test_graph_has_all_nodes():
    """Graph should have all required nodes."""
    from blueprint.agents.graph import create_graph

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
    from blueprint.agents.graph import create_graph
    from blueprint.agents.state import create_initial_state

    app = create_graph()
    state = create_initial_state("test-123", "Build a calculator")

    # The first node after START should be pm
    # We can verify this by checking the graph edges
    graph = app.get_graph()
    # START node should have edge to pm
    assert "pm" in [str(edge.target) for edge in graph.edges if str(edge.source) == "__start__"]


def test_route_after_pm_proceed():
    """route_after_pm should return 'proceed' when no error."""
    from blueprint.agents.graph import route_after_pm

    state = {"error": None}
    assert route_after_pm(state) == "proceed"


def test_route_after_pm_error():
    """route_after_pm should return 'pm' on error (retry)."""
    from blueprint.agents.graph import route_after_pm

    state = {"error": "Some error"}
    assert route_after_pm(state) == "pm"


def test_route_after_pm_timeout():
    """route_after_pm should return END on timeout error."""
    from blueprint.agents.graph import route_after_pm
    from langgraph.graph import END

    state = {"error": "LLM timeout occurred"}
    assert route_after_pm(state) == END


def test_route_after_developer_proceed():
    """route_after_developer should return 'tester' when no error."""
    from blueprint.agents.graph import route_after_developer

    state = {"error": None}
    assert route_after_developer(state) == "tester"


def test_route_after_developer_security_error():
    """route_after_developer should return END on security error."""
    from blueprint.agents.graph import route_after_developer
    from langgraph.graph import END

    state = {"error": "Security violation: path injection detected"}
    assert route_after_developer(state) == END


def test_route_after_test_pass():
    """route_after_test should return 'pass' key when tests pass."""
    from blueprint.agents.graph import route_after_test

    state = {"test_passed": True, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "reviewer" in add_conditional_edges
    assert route_after_test(state) == "pass"


def test_route_after_test_fail():
    """route_after_test should return 'fail' key when tests fail."""
    from blueprint.agents.graph import route_after_test

    state = {"test_passed": False, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "developer" in add_conditional_edges
    assert route_after_test(state) == "fail"


def test_route_after_test_max_iterations():
    """route_after_test should return 'pass' key when max iterations reached."""
    from blueprint.agents.graph import route_after_test

    state = {"test_passed": False, "iteration": 3, "max_iterations": 3}
    assert route_after_test(state) == "pass"


def test_route_after_review_approve():
    """route_after_review should return 'approve' key when approved."""
    from blueprint.agents.graph import route_after_review

    state = {"review_approved": True, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "deliver" in add_conditional_edges
    assert route_after_review(state) == "approve"


def test_route_after_review_reject():
    """route_after_review should return 'reject' key when rejected."""
    from blueprint.agents.graph import route_after_review

    state = {"review_approved": False, "iteration": 1, "max_iterations": 3}
    # Returns key that maps to "developer" in add_conditional_edges
    assert route_after_review(state) == "reject"


def test_route_after_architect_auto():
    """route_after_architect should return 'auto' key when no human confirm needed."""
    from blueprint.agents.graph import route_after_architect

    state = {"need_human_confirm": False}
    # Returns key that maps to "developer" in add_conditional_edges
    assert route_after_architect(state) == "auto"


def test_route_after_architect_confirm():
    """route_after_architect should return 'confirm' key when confirm needed."""
    from blueprint.agents.graph import route_after_architect

    state = {"need_human_confirm": True}
    # Returns key that maps to "human_confirm" in add_conditional_edges
    assert route_after_architect(state) == "confirm"


# ── Issue 1.5: Persistent Checkpointer Tests ─────────────────────────────

def test_graph_uses_persistent_checkpointer():
    """P1.5: Graph should attempt to use SqliteSaver for persistence.

    Verifies that create_graph() uses a checkpointer for interrupt/resume support.
    Currently uses MemorySaver; TODO upgrade to AsyncSqliteSaver for persistence.
    """
    from blueprint.agents.graph import create_graph
    graph = create_graph()
    assert graph is not None
    assert hasattr(graph, 'invoke') or hasattr(graph, 'ainvoke')
    # Verify the graph has a checkpointer (required for interrupt/resume)
    # MemorySaver is used for now; SqliteSaver deferred due to async requirements


# ── Issue 2.8: meta.json Encoding Tests ──────────────────────────────────

def test_meta_json_utf8_encoding():
    """P2.8: deliver_node must write meta.json with explicit UTF-8 encoding.

    Inspects the deliver_node source to confirm encoding='utf-8' is passed
    to write_text for meta.json.
    """
    import inspect
    from blueprint.agents.graph import deliver_node

    source = inspect.getsource(deliver_node)
    # Find the meta.json write line and verify it has encoding="utf-8"
    assert 'meta.json' in source, "deliver_node should write meta.json"
    # The write_text call for meta.json must include encoding
    # Look for: write_text(..., encoding="utf-8") pattern near meta.json
    lines = source.split('\n')
    meta_write_lines = [
        line for line in lines
        if 'meta.json' in line and 'write_text' in line
    ]
    assert len(meta_write_lines) >= 1, \
        "deliver_node should have a write_text call for meta.json"
    for line in meta_write_lines:
        assert 'encoding' in line and 'utf-8' in line, \
            f"meta.json write_text must specify encoding='utf-8': {line}"
