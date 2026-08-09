"""
ai/diagnosis.py
----------------
This module produces the "AI diagnosis" for a troubleshooting case.

For this first version we use a MOCK AI function (no API key needed).
It looks at keywords in the case's symptom / topology_note / show_outputs
and returns a structured JSON-style dictionary, similar to what a real
LLM call would return if we asked it to diagnose the case.

WHY MOCKED?
- The assignment says: "Do not require an API key for the first working
  version" and "use a mock AI diagnosis function that returns realistic
  structured JSON based on each case."
- Keeping this logic in its own file/function (`get_ai_diagnosis`) means
  that later you can replace the *inside* of this function with a real
  call to the Anthropic API (using the prompt in prompts/diagnose_prompt.md)
  without having to change app.py at all.

Required output fields (see prompts/diagnose_prompt.md for the full spec):
    root_cause    - short sentence describing the most likely root cause
    confidence     - "High", "Medium", or "Low"
    evidence       - short explanation of which clues led to this diagnosis
    next_command   - a Cisco IOS command the engineer should run next
    fix_steps      - list of steps to resolve the issue
"""

import re


# Each rule below is checked in order. The first rule whose keywords match
# the case's combined text (symptom + topology_note + show_outputs) wins.
# This keeps the mock "AI" deterministic and easy to explain in a demo,
# while still feeling like a realistic structured diagnosis.
DIAGNOSIS_RULES = [
    {
        "keywords": ["duplicate", "same ip", "ip conflict"],
        "root_cause": "Duplicate IP address configured on two hosts in the same subnet.",
        "confidence": "High",
        "evidence": "ARP table / show output lists the same IP address bound to two different MAC addresses.",
        "next_command": "show ip arp | include <suspect-ip>",
        "fix_steps": [
            "Identify both devices using the duplicate IP from the ARP table.",
            "Reassign a unique IP to one of the devices (static or via DHCP).",
            "Clear the ARP cache on the switch/router.",
            "Verify connectivity from both hosts after the change."
        ],
    },
    {
        "keywords": ["subnet mask", "255.255.255.252", "/30", "incorrect mask"],
        "root_cause": "Incorrect subnet mask is isolating the host from the rest of its intended subnet.",
        "confidence": "High",
        "evidence": "Device IP configuration shows a subnet mask that does not match the rest of the VLAN/subnet.",
        "next_command": "show running-config interface <vlan-or-int>",
        "fix_steps": [
            "Confirm the correct subnet mask used by the rest of the VLAN.",
            "Update the host or interface configuration with the correct mask.",
            "Renew the IP configuration on the affected host if using DHCP.",
            "Re-test connectivity to other hosts on the subnet."
        ],
    },
    {
        "keywords": ["gateway", "default gateway"],
        "root_cause": "Client default gateway does not match the router/switch SVI address, so off-subnet traffic is dropped.",
        "confidence": "High",
        "evidence": "Client's configured default gateway differs from the actual SVI/router interface IP shown in the topology note.",
        "next_command": "show ip interface brief | include Vlan",
        "fix_steps": [
            "Verify the actual gateway IP on the router/switch SVI.",
            "Correct the DHCP scope or static IP configuration on affected clients.",
            "Release/renew IP configuration on client devices.",
            "Confirm clients can now reach other VLANs / the internet."
        ],
    },
    {
        "keywords": ["administratively down", "shut down", "shutdown", "down down", "notconnect"],
        "root_cause": "Physical or logical interface is administratively shut down or not connected.",
        "confidence": "High",
        "evidence": "show interfaces / show ip interface brief output shows the interface status as 'administratively down' or 'notconnect'.",
        "next_command": "show interfaces <interface> status",
        "fix_steps": [
            "Check the interface with 'show ip interface brief'.",
            "If administratively down, run 'no shutdown' on the interface.",
            "If notconnect, check the physical cable / PoE / SFP.",
            "Confirm 'up/up' status and re-test connectivity."
        ],
    },
    {
        "keywords": ["vlan 40", "inactive", "missing vlan", "does not exist"],
        "root_cause": "The VLAN assigned to the port has not been created on the switch, leaving affected ports inactive.",
        "confidence": "High",
        "evidence": "show vlan brief does not list the VLAN, and the port shows the access VLAN as 'inactive'.",
        "next_command": "show vlan brief",
        "fix_steps": [
            "Create the missing VLAN using 'vlan <id>' / 'name <name>' in global config.",
            "Re-apply or verify the access VLAN on the affected switchports.",
            "Confirm the port state changes from inactive to connected.",
            "Test end-device connectivity."
        ],
    },
    {
        "keywords": ["missing route", "no 0.0.0.0/0", "no default route", "10.30.0.0/24"],
        "root_cause": "A required route (static, default, or connected) is missing from the routing table.",
        "confidence": "High",
        "evidence": "show ip route output does not contain an entry for the destination subnet the user is trying to reach.",
        "next_command": "show ip route",
        "fix_steps": [
            "Determine the correct next-hop or exit interface for the missing subnet.",
            "Add the missing static route (or fix the dynamic routing protocol config).",
            "Verify the route now appears in 'show ip route'.",
            "Test end-to-end connectivity to the previously unreachable subnet."
        ],
    },
    {
        "keywords": ["dhcp pool", "leased addresses", "apipa", "169.254"],
        "root_cause": "The DHCP scope is exhausted, so new clients cannot obtain a valid IP address.",
        "confidence": "Medium",
        "evidence": "show ip dhcp pool shows leased addresses equal to total addresses, and clients report APIPA (169.254.x.x) addresses.",
        "next_command": "show ip dhcp pool",
        "fix_steps": [
            "Expand the DHCP pool range or reduce the lease time.",
            "Clear stale/expired leases if applicable.",
            "Verify new clients can obtain an address.",
            "Monitor pool utilization going forward."
        ],
    },
    {
        "keywords": ["ip helper-address", "relay", "different subnet"],
        "root_cause": "DHCP relay (ip helper-address) is missing on the client VLAN's SVI, so DHCP requests never reach the server.",
        "confidence": "Medium",
        "evidence": "The VLAN SVI configuration has no 'ip helper-address' pointing to the DHCP server subnet.",
        "next_command": "show running-config interface vlan <id>",
        "fix_steps": [
            "Add 'ip helper-address <dhcp-server-ip>' to the affected VLAN SVI.",
            "Confirm the DHCP server can route back to the client subnet.",
            "Test a DHCP request from a client on that VLAN.",
            "Verify the client receives a correct IP, gateway, and DNS."
        ],
    },
    {
        "keywords": ["dns", "nslookup", "name resolution"],
        "root_cause": "DNS resolution is failing due to an unreachable, decommissioned, or stale DNS server/record.",
        "confidence": "Medium",
        "evidence": "nslookup output shows a timeout or a record still pointing at an old/retired server IP.",
        "next_command": "nslookup <hostname> <dns-server>",
        "fix_steps": [
            "Verify the DNS server IP handed out by DHCP is still valid and reachable.",
            "Update DHCP scope options or static DNS settings to point to a working DNS server.",
            "Correct any stale DNS records on the internal DNS server.",
            "Flush the client's DNS cache and re-test name resolution."
        ],
    },
    {
        "keywords": ["traceroute", "routing loop", "bounce"],
        "root_cause": "A routing loop exists between two routers due to conflicting route entries.",
        "confidence": "High",
        "evidence": "Traceroute output shows the path bouncing back and forth between the same two hops repeatedly.",
        "next_command": "show ip route <destination>",
        "fix_steps": [
            "Compare routing tables on both routers for the affected destination.",
            "Remove or correct the conflicting static/dynamic route causing the loop.",
            "Verify a stable, single path with traceroute.",
            "Monitor for recurrence after the fix."
        ],
    },
    {
        "keywords": ["ospf neighbor", "neighbor table empty", "area 0"],
        "root_cause": "OSPF neighbor adjacency has failed, likely due to area, timer, authentication, or ACL mismatch.",
        "confidence": "Medium",
        "evidence": "show ip ospf neighbor returns an empty neighbor table on a link that should have an adjacency.",
        "next_command": "show ip ospf interface <interface>",
        "fix_steps": [
            "Compare OSPF area, hello/dead timers, and network type on both sides.",
            "Check for an ACL or firewall blocking OSPF multicast (224.0.0.5/6).",
            "Correct the mismatched OSPF parameter.",
            "Confirm the neighbor reaches the FULL state."
        ],
    },
    {
        "keywords": ["access-list", "acl", "deny tcp", "deny ip"],
        "root_cause": "An access control list is blocking legitimate traffic, either through an explicit deny or ACL ordering.",
        "confidence": "Medium",
        "evidence": "show access-lists output contains a deny statement matching the affected traffic, or a permit-any placed before the intended deny.",
        "next_command": "show access-lists <acl-number-or-name>",
        "fix_steps": [
            "Review the ACL line-by-line for the affected source/destination/port.",
            "Reorder or correct the ACL entries (most specific rules first).",
            "Apply the corrected ACL and clear any cached sessions if needed.",
            "Re-test the previously blocked traffic."
        ],
    },
    {
        "keywords": ["nat", "translations", "overload", "static tcp"],
        "root_cause": "NAT (dynamic overload or static mapping) is misconfigured, breaking inside-to-outside or outside-to-inside connectivity.",
        "confidence": "Medium",
        "evidence": "show ip nat translations is empty, or the static NAT entry references an outdated IP/port.",
        "next_command": "show ip nat translations",
        "fix_steps": [
            "Verify 'ip nat inside' / 'ip nat outside' are applied to the correct interfaces.",
            "Confirm the NAT ACL or static mapping matches current addressing/ports.",
            "Correct the NAT configuration.",
            "Test connectivity from an inside host to an outside destination (and vice versa for static NAT)."
        ],
    },
    {
        "keywords": ["wpa2", "ssid", "wireless", "wlan"],
        "root_cause": "Wireless connectivity issue caused by an SSID security/config mismatch, channel interference, or AP uplink failure.",
        "confidence": "Medium",
        "evidence": "WLC output shows a security mode, channel, or AP status inconsistent with what clients expect.",
        "next_command": "show wlan <id>",
        "fix_steps": [
            "Compare the SSID security settings with what client devices are configured for.",
            "Check for channel overlap between nearby access points.",
            "Verify the AP's uplink switchport status if coverage is missing entirely.",
            "Re-test client association after correcting the mismatch."
        ],
    },
    {
        "keywords": ["trunk", "allowed on trunk", "native vlan"],
        "root_cause": "Trunk link is misconfigured (missing VLAN in allowed list or native VLAN mismatch).",
        "confidence": "High",
        "evidence": "show interfaces trunk output shows a VLAN missing from the allowed list, or differing native VLANs on each side.",
        "next_command": "show interfaces trunk",
        "fix_steps": [
            "Compare the allowed VLAN list and native VLAN on both ends of the trunk.",
            "Add the missing VLAN to the trunk's allowed list, or align the native VLAN.",
            "Re-check the trunk with 'show interfaces trunk'.",
            "Confirm traffic for the affected VLAN now passes correctly."
        ],
    },
    {
        "keywords": ["spanning-tree", "blk", "root bridge"],
        "root_cause": "Spanning Tree Protocol is blocking a port that is needed for traffic to flow, due to root bridge placement.",
        "confidence": "Medium",
        "evidence": "show spanning-tree output shows the relevant port in a Blocking (BLK) state.",
        "next_command": "show spanning-tree vlan <id>",
        "fix_steps": [
            "Identify the current root bridge and confirm it is the intended one.",
            "Adjust STP priority so the desired switch becomes root, if needed.",
            "Verify the previously blocked port now forwards where appropriate.",
            "Re-test connectivity for the affected department."
        ],
    },
    {
        "keywords": ["err-disabled", "port security", "security violation"],
        "root_cause": "Port security violation has placed the switchport into an err-disabled state.",
        "confidence": "High",
        "evidence": "show port-security interface reports a security violation, and interface status is err-disabled.",
        "next_command": "show port-security interface <interface>",
        "fix_steps": [
            "Confirm which device/MAC triggered the violation.",
            "Decide whether to allow the new device (update the allowed MAC) or keep the old one.",
            "Re-enable the port with 'shutdown' then 'no shutdown', or clear the violation.",
            "Verify the port returns to a connected/forwarding state."
        ],
    },
    {
        "keywords": ["duplex", "collisions", "fcs errors"],
        "root_cause": "Duplex mismatch between two connected devices is causing collisions and errors.",
        "confidence": "Medium",
        "evidence": "show interfaces output shows half-duplex on one side and rising collision/FCS error counters.",
        "next_command": "show interfaces <interface>",
        "fix_steps": [
            "Set both ends of the link to the same duplex/speed (preferably auto/auto).",
            "Clear interface counters and monitor for further errors.",
            "Confirm throughput returns to expected levels.",
            "Document the corrected configuration."
        ],
    },
    {
        "keywords": ["mtu"],
        "root_cause": "MTU mismatch between links is causing fragmentation issues for large packets.",
        "confidence": "Medium",
        "evidence": "show interfaces output shows an MTU value lower than the rest of the network on the new link.",
        "next_command": "show interfaces <interface> | include MTU",
        "fix_steps": [
            "Determine the standard MTU used across the rest of the network.",
            "Update the MTU on the mismatched interface/link to match.",
            "Test large-packet transfers (e.g., ping with large size, file transfer).",
            "Confirm voice/video quality improves if applicable."
        ],
    },
    {
        "keywords": ["hsrp", "standby"],
        "root_cause": "HSRP (first-hop redundancy) is not configured or functioning correctly on the standby router.",
        "confidence": "Medium",
        "evidence": "show standby brief shows the standby router state as unknown or not properly tracking the active router.",
        "next_command": "show standby brief",
        "fix_steps": [
            "Verify HSRP group, priority, and virtual IP match on both routers.",
            "Check that the standby router can see hello packets from the active router.",
            "Correct any mismatched HSRP configuration.",
            "Test failover by shutting down the active router's interface (in a maintenance window)."
        ],
    },
    {
        "keywords": ["etherchannel", "port-channel", "po1"],
        "root_cause": "One or more member links of the EtherChannel bundle are not properly bundled, reducing available bandwidth.",
        "confidence": "Medium",
        "evidence": "show etherchannel summary shows a member port in a suspended/down (D) state instead of bundled (P).",
        "next_command": "show etherchannel summary",
        "fix_steps": [
            "Check that both ends of each member link use matching EtherChannel mode (active/passive or on/on).",
            "Verify matching VLAN/trunk configuration on all member ports.",
            "Correct the mismatched member link configuration.",
            "Confirm all expected ports show as bundled (P) in 'show etherchannel summary'."
        ],
    },
    {
        "keywords": ["qos", "policy-map", "voice traffic", "class-default"],
        "root_cause": "QoS policy is missing a priority class for voice/critical traffic, causing quality issues under load.",
        "confidence": "Medium",
        "evidence": "show policy-map interface output does not show a dedicated voice (EF) class in the applied policy.",
        "next_command": "show policy-map interface <interface>",
        "fix_steps": [
            "Review the current QoS policy-map for a missing voice/EF class.",
            "Re-add the priority class for voice traffic with the correct match criteria.",
            "Re-apply the policy to the interface.",
            "Monitor call quality and interface queue drops."
        ],
    },
    {
        "keywords": ["voice vlan: none", "voice vlan none", "missing voice vlan", "no voice vlan", "voice vlan 50"],
        "root_cause": "Voice VLAN 50 is not configured on access interface Fa0/10, so IP phones cannot join the voice VLAN and obtain DHCP addresses.",
        "confidence": 0.92,
        "evidence": [
            "The topology note says Fa0/10 has data VLAN 10 only and no voice VLAN command.",
            "The show interfaces Fa0/10 switchport output shows 'Voice VLAN: none'."
        ],
        "next_command": "show running-config interface Fa0/10",
        "fix_steps": [
            "Enter interface configuration mode for Fa0/10.",
            "Configure the voice VLAN: switchport voice vlan 50",
            "Verify with: show interfaces Fa0/10 switchport",
            "Renew or reconnect the IP phone and confirm it receives a DHCP address.",
        ],
    },
    {
        "keywords": ["access vlan", "wrong vlan", "vlan 5", "vlan 25"],
        "root_cause": "The switchport is assigned to the wrong access VLAN, isolating the device from its intended network.",
        "confidence": "High",
        "evidence": "show interfaces switchport shows an access VLAN different from what the topology note specifies.",
        "next_command": "show interfaces <interface> switchport",
        "fix_steps": [
            "Confirm the correct VLAN for this port from network documentation.",
            "Change the access VLAN on the port to the correct VLAN ID.",
            "Verify the device now receives an appropriate IP address.",
            "Test connectivity to the intended department resources."
        ],
    },
]

# Fallback used only if nothing matches (should rarely trigger with the
# 30 built-in sample cases, but keeps the function robust for new cases).
DEFAULT_DIAGNOSIS = {
    "root_cause": "Unable to confidently determine a specific root cause from the available evidence.",
    "confidence": "Low",
    "evidence": "No strong keyword matches were found in the symptom, topology note, or show output text.",
    "next_command": "show tech-support",
    "fix_steps": [
        "Gather additional show command output relevant to the reported symptom.",
        "Escalate to a senior engineer if the issue persists.",
        "Document findings for the next diagnostic pass."
    ],
}


def get_ai_diagnosis(case: dict) -> dict:
    """
    Mock AI diagnosis function.

    Parameters
    ----------
    case : dict
        A single case row (as a dict) with at least the fields:
        symptom, topology_note, show_outputs.

    Returns
    -------
    dict with keys: root_cause, confidence, evidence, next_command, fix_steps

    NOTE FOR FUTURE UPGRADE:
    To connect a real LLM, replace the body of this function with a call
    to the Anthropic API using the system prompt in
    prompts/diagnose_prompt.md, sending the case's symptom/topology_note/
    show_outputs as the case details, and parsing the returned JSON into
    this same dictionary shape. The rest of the app (app.py) does not
    need to change.
    """
    combined_text = " ".join([
        str(case.get("symptom", "")),
        str(case.get("topology_note", "")),
        str(case.get("show_outputs", "")),
    ]).lower()

    for rule in DIAGNOSIS_RULES:
        for kw in rule["keywords"]:
            if kw in combined_text:
                # Return a copy so callers can't accidentally mutate the rule
                diagnosis = {
                    "root_cause": rule["root_cause"],
                    "confidence": rule["confidence"],
                    "evidence": rule["evidence"],
                    "next_command": rule["next_command"],
                    "fix_steps": list(rule["fix_steps"]),
                }
                return diagnosis

    return dict(DEFAULT_DIAGNOSIS)
