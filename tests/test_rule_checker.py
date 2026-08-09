from checker.rule_checker import (
    check_duplicate_ip,
    check_subnet_mask,
    check_gateway_mismatch,
    check_interface_down,
    check_missing_vlan,
    check_missing_routes,
)


def make_case(**kwargs):
    case = {
        "show_outputs": "",
        "symptom": "",
        "topology_note": "",
    }
    case.update(kwargs)
    return case


def test_check_duplicate_ip_detects_duplicate():
    case = make_case(show_outputs="192.168.1.5\n192.168.1.5")
    result = check_duplicate_ip(case)
    assert result["result"] == "FAIL"


def test_check_subnet_mask_flags_restrictive_mask():
    case = make_case(show_outputs="255.255.255.252", symptom="Subnet mask mismatch")
    result = check_subnet_mask(case)
    assert result["result"] == "FAIL"


def test_check_gateway_mismatch_detects_difference():
    case = make_case(show_outputs="Default Gateway: 192.168.1.1\nVlan10 192.168.1.2")
    result = check_gateway_mismatch(case)
    assert result["result"] == "FAIL"


def test_check_interface_down_detects_down_state():
    case = make_case(show_outputs="GigabitEthernet0/1 is administratively down")
    result = check_interface_down(case)
    assert result["result"] == "FAIL"


def test_check_missing_vlan_detects_inactive_vlan():
    case = make_case(show_outputs="VLAN 40 inactive")
    result = check_missing_vlan(case)
    assert result["result"] == "FAIL"


def test_check_missing_routes_requires_routing_table():
    case = make_case(
        show_outputs="show ip route\nO 10.0.0.0/24 is directly connected",
        topology_note="Route to 10.0.0.0/24 required",
    )
    result = check_missing_routes(case)
    assert result["result"] == "PASS"
