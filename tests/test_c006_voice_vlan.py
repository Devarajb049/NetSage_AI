import pytest

from ai.diagnosis import get_ai_diagnosis
from checker.rule_checker import check_missing_vlan


@pytest.fixture
def c006_case():
    return {
        "case_id": "C006",
        "symptom": "Phones on VLAN 50 (voice VLAN) cannot get IP addresses via DHCP.",
        "topology_note": "SW4 access port Fa0/10 configured with data VLAN 10 only, no voice VLAN command applied.",
        "show_outputs": "SW4# show interfaces Fa0/10 switchport\nAdministrative Mode: static access\nAccess Mode VLAN: 10 (DATA)\nVoice VLAN: none",
        "expected_fault": "Missing VLAN - voice VLAN 50 not configured on the access port",
    }


def test_c006_ai_diagnosis_detects_voice_vlan_missing(c006_case):
    result = get_ai_diagnosis(c006_case)

    assert "Voice VLAN 50" in result["root_cause"]
    assert result["confidence"] == 0.92
    assert isinstance(result["evidence"], list)
    assert any("voice vlan" in evidence.lower() for evidence in result["evidence"])
    assert result["next_command"] == "show running-config interface Fa0/10"
    assert result["fix_steps"][1] == "Configure the voice VLAN: switchport voice vlan 50"


def test_c006_rule_checker_fails_on_missing_voice_vlan(c006_case):
    result = check_missing_vlan(c006_case)
    assert result["result"] == "FAIL"
    assert "Voice VLAN 50" in result["detail"]


def test_c006_ai_comparison_matches_expected_fault(c006_case):
    from ai.compare_answers import compare_diagnosis

    result = get_ai_diagnosis(c006_case)
    match = compare_diagnosis(result["root_cause"], c006_case["expected_fault"])
    assert match == "Match"
