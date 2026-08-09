import pytest

from ai.compare_answers import compare_diagnosis, get_comparison_details


@pytest.mark.parametrize(
    "ai_root_cause, expected_fault, expected_result",
    [
        ("Duplicate IP address on two hosts.", "Duplicate IP detected in the subnet.", "Match"),
        ("Gateway mismatch between client and router.", "Client default gateway is wrong.", "Match"),
        ("DNS server unreachable.", "VLAN is inactive.", "No Match"),
        ("", "Expected fault text.", "No Match"),
        ("Some root cause.", "", "No Match"),
    ],
)
def test_compare_diagnosis(ai_root_cause, expected_fault, expected_result):
    assert compare_diagnosis(ai_root_cause, expected_fault) == expected_result


def test_get_comparison_details_returns_overlap_list():
    details = get_comparison_details(
        "Client default gateway mismatch.",
        "Default gateway is misconfigured on the client.",
    )

    assert details["result"] in {"Match", "Partial Match", "No Match"}
    assert isinstance(details["overlapping_keywords"], list)
