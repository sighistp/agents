from blueprint.agents.tester import _extract_test_passed

def test_pytest_output_passed():
    assert _extract_test_passed("5 passed, 0 failed in 0.1s", False) is True

def test_pytest_output_failed():
    assert _extract_test_passed("3 passed, 2 failed in 0.1s", False) is False

def test_pytest_output_errors():
    assert _extract_test_passed("1 passed, 1 error in 0.1s", False) is False

def test_execution_error():
    assert _extract_test_passed("all tests passed", True) is False

def test_all_passed_keyword():
    assert _extract_test_passed("all passed", False) is True

def test_zero_failed():
    assert _extract_test_passed("10 passed, 0 failed", False) is True

def test_chinese_output():
    assert _extract_test_passed("全部通过（5组测试，0失败）", False) is True

def test_mixed_output():
    assert _extract_test_passed("3 passed, 1 failed: division by zero", False) is False
