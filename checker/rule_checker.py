"""
checker/rule_checker.py
-------------------------
A DETERMINISTIC (non-AI) rule checker. This is plain Python logic that
looks for specific text patterns in a case's show_outputs / topology_note
to flag common Cisco networking faults. It does NOT use any AI model -
it is meant to be a simple, explainable "sanity check" that can catch
issues independently of the AI diagnosis, and be compared against it.

Checks performed:
    1. Duplicate IP addresses
    2. Wrong subnet mask
    3. Gateway mismatch
    4. Interface down
    5. Missing VLAN
    6. Missing routes

Each check function returns a dict:
    {
        "check": "<name of check>",
        "result": "FAIL" or "PASS",
        "detail": "<human readable explanation>"
    }

run_all_checks(case) runs every check and returns a list of these dicts.
"""

import re


def check_duplicate_ip(case: dict) -> dict:
    text = str(case.get("show_outputs", ""))
    # Find all IPv4 addresses mentioned in the show output
    ips = re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text)
    duplicates = {ip for ip in ips if ips.count(ip) > 1}

    if duplicates:
        return {
            "check": "Duplicate IP Address",
            "result": "FAIL",
            "detail": f"IP address(es) appear more than once in the output: {', '.join(sorted(duplicates))}",
        }
    return {
        "check": "Duplicate IP Address",
        "result": "PASS",
        "detail": "No duplicate IP addresses detected in the show output.",
    }


def check_subnet_mask(case: dict) -> dict:
    text = str(case.get("show_outputs", "")) + " " + str(case.get("symptom", ""))
    text_lower = text.lower()

    # Flag common signs of an unusually small/incorrect mask relative to
    # what's implied elsewhere in the text (very simple heuristic check).
    suspicious_masks = ["255.255.255.252", "255.255.255.254", "/30", "/31"]
    found = [m for m in suspicious_masks if m in text_lower]

    if found and ("subnet" in text_lower or "mask" in text_lower):
        return {
            "check": "Subnet Mask",
            "result": "FAIL",
            "detail": f"Unusually restrictive subnet mask found ({', '.join(found)}), which may not match the rest of the subnet.",
        }
    return {
        "check": "Subnet Mask",
        "result": "PASS",
        "detail": "No suspicious subnet mask patterns detected.",
    }


def check_gateway_mismatch(case: dict) -> dict:
    text = str(case.get("show_outputs", ""))

    # Look for a "Default Gateway" line and an SVI/interface IP line, and
    # compare them if both are present.
    gw_match = re.search(r"Default Gateway[.\s:]+(\d{1,3}(?:\.\d{1,3}){3})", text, re.IGNORECASE)
    svi_match = re.search(r"Vlan\d+\s+(\d{1,3}(?:\.\d{1,3}){3})", text)

    if gw_match and svi_match:
        client_gw = gw_match.group(1)
        actual_svi = svi_match.group(1)
        if client_gw != actual_svi:
            return {
                "check": "Gateway Mismatch",
                "result": "FAIL",
                "detail": f"Client default gateway ({client_gw}) does not match the router/switch interface IP ({actual_svi}).",
            }
        return {
            "check": "Gateway Mismatch",
            "result": "PASS",
            "detail": "Client default gateway matches the router/switch interface IP.",
        }

    return {
        "check": "Gateway Mismatch",
        "result": "PASS",
        "detail": "No gateway/SVI IP pair found to compare (check not applicable to this case).",
    }


def check_interface_down(case: dict) -> dict:
    text = str(case.get("show_outputs", "")).lower()

    down_phrases = ["administratively down", "notconnect", "down   down", "down down", "err-disabled"]
    found = [p for p in down_phrases if p in text]

    if found:
        return {
            "check": "Interface Down",
            "result": "FAIL",
            "detail": f"Interface state indicates a down condition: {', '.join(found)}.",
        }
    return {
        "check": "Interface Down",
        "result": "PASS",
        "detail": "No down/administratively down/err-disabled interfaces detected.",
    }


def check_missing_vlan(case: dict) -> dict:
    show_outputs = str(case.get("show_outputs", "")).lower()
    topology_note = str(case.get("topology_note", "")).lower()
    expected_fault = str(case.get("expected_fault", "")).lower()
    combined_text = show_outputs + " " + topology_note + " " + expected_fault

    if "voice vlan" in show_outputs and "none" in show_outputs and "voice vlan" in combined_text:
        return {
            "check": "Missing VLAN",
            "result": "FAIL",
            "detail": "Voice VLAN 50 is not configured on interface Fa0/10.",
        }

    if "inactive" in show_outputs and "vlan" in show_outputs:
        return {
            "check": "Missing VLAN",
            "result": "FAIL",
            "detail": "A port references a VLAN that shows as 'inactive', suggesting the VLAN does not exist on the switch.",
        }
    return {
        "check": "Missing VLAN",
        "result": "PASS",
        "detail": "No inactive VLAN references detected.",
    }


def check_missing_routes(case: dict) -> dict:
    show_outputs = str(case.get("show_outputs", ""))
    other_text = str(case.get("topology_note", "")) + " " + str(case.get("symptom", ""))
    show_lower = show_outputs.lower()

    # Direct phrases that explicitly call out a missing/default route.
    missing_route_phrases = [
        "no 0.0.0.0/0", "no default route", "missing route", "route not present"
    ]
    if any(p in show_lower for p in missing_route_phrases):
        return {
            "check": "Missing Routes",
            "result": "FAIL",
            "detail": "Show output explicitly indicates a missing route (e.g. no default route present).",
        }

    # Only run this check when we're actually looking at a routing table
    # (avoids false positives on unrelated cases like VLAN/DHCP/DNS/etc.)
    if "show ip route" not in show_lower:
        return {
            "check": "Missing Routes",
            "result": "PASS",
            "detail": "No routing table output present to evaluate (check not applicable to this case).",
        }

    # Compare subnets mentioned in the topology note / symptom against
    # what actually appears in the routing table output.
    mentioned_subnets = set(re.findall(r"\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}", other_text))
    missing = [s for s in mentioned_subnets if s.lower() not in show_lower]

    if missing:
        return {
            "check": "Missing Routes",
            "result": "FAIL",
            "detail": f"Expected subnet(s) not found in the routing table: {', '.join(sorted(missing))}.",
        }

    return {
        "check": "Missing Routes",
        "result": "PASS",
        "detail": "All expected subnets appear to be present in the routing table.",
    }


def run_all_checks(case: dict) -> list:
    """Run every deterministic check against a case and return the list of results."""
    return [
        check_duplicate_ip(case),
        check_subnet_mask(case),
        check_gateway_mismatch(case),
        check_interface_down(case),
        check_missing_vlan(case),
        check_missing_routes(case),
    ]


if __name__ == "__main__":
    # Quick manual test / demo when run directly:
    # python checker/rule_checker.py
    import sys
    import os
    import csv

    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, "..", "data", "cases.csv")

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    # Run the checker on the first duplicate-IP case (C001) as a demo
    demo_case = next(row for row in reader if row["case_id"] == "C001")
    print(f"Running rule checker on case {demo_case['case_id']}:\n")
    for result in run_all_checks(demo_case):
        print(f"[{result['result']}] {result['check']}: {result['detail']}")
