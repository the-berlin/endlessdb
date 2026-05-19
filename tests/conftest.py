from tests.test_endlessdb import TEST_COVERAGE_SUMMARY


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    terminalreporter.section("EndlessDB checked behavior")
    for index, item in enumerate(TEST_COVERAGE_SUMMARY, start=1):
        terminalreporter.write_line(f"{index}. {item}")
