from checker.rule_checker import check_missing_vlan
case = {
    'case_id': 'C006',
    'symptom': 'Phones on VLAN 50 (voice VLAN) cannot get IP addresses via DHCP.',
    'topology_note': 'SW4 access port Fa0/10 configured with data VLAN 10 only, no voice VLAN command applied.',
    'show_outputs': 'SW4# show interfaces Fa0/10 switchport\nAdministrative Mode: static access\nAccess Mode VLAN: 10 (DATA)\nVoice VLAN: none',
    'expected_fault': 'Missing VLAN - voice VLAN 50 not configured on the access port',
}
print('show_outputs lower:', case['show_outputs'].lower())
print('topology_note lower:', case['topology_note'].lower())
print('expected_fault lower:', case['expected_fault'].lower())
print('check_missing_vlan:', check_missing_vlan(case))
