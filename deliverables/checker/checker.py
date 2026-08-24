"""
src/checker.py

Deterministic, rule-based network fault checker.

This module runs BEFORE any AI call. It inspects the raw evidence text
(symptom + topology_note + show_outputs) with regex/string parsing and
returns a list of RuleResult objects for every rule that matches.

Design notes
------------
- Rules inspect the *evidence text*, not the case_id. The same functions
  run against arbitrary user-typed evidence in the Streamlit "custom
  evidence" box, not just the 30 supplied cases.
- Whitespace and case are normalized before matching so that formatting
  differences in the CLI text don't cause false negatives.
- More than one rule can match the same evidence (e.g. a case could show
  both an ACL problem and a VLAN problem); the checker returns every
  match rather than stopping at the first one.
- Rules are intentionally somewhat specific to the vocabulary that shows
  up in real Cisco `show` output because that is what keeps false
  positives low on free-form input, while still being pattern-based
  rather than a lookup keyed on case_id.
"""

from __future__ import annotations

import re
from typing import Callable, List, Optional

from src.models import RuleResult


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace so regexes don't have to worry
    about casing or irregular spacing in pasted CLI output."""
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip().lower()


RuleFunc = Callable[[str, str], Optional[RuleResult]]
# Each rule function receives (normalized_text, raw_text) and returns a
# RuleResult (with matched=True) or None if it doesn't match.


def _make_result(
    rule_id: str,
    title: str,
    root_cause: str,
    evidence: List[str],
    osi_layer: str,
    severity: str,
    suggested_command: str,
    suggested_fix: str,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        matched=True,
        title=title,
        root_cause=root_cause,
        evidence=evidence,
        osi_layer=osi_layer,
        severity=severity,
        suggested_command=suggested_command,
        suggested_fix=suggested_fix,
    )


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------


def rule_interface_admin_down(norm: str, raw: str) -> Optional[RuleResult]:
    """1. Administratively down interface/sub-interface."""
    m = re.search(
        r"([a-z]+[a-z0-9/.]*?)\s+is\s+administratively\s+down",
        norm,
    )
    if not m:
        return None
    iface = m.group(1)
    return _make_result(
        "R01_INTERFACE_ADMIN_DOWN",
        "Interface administratively down",
        f"Interface {iface} is administratively shut down, blocking traffic through it.",
        [f"'{iface} is administratively down' found in show output"],
        "Layer 1/2",
        "High",
        f"show interfaces {iface}",
        f"Enter interface {iface} and run 'no shutdown' to re-enable it.",
    )


def rule_dhcp_pool_exhaustion(norm: str, raw: str) -> Optional[RuleResult]:
    """2. DHCP pool exhaustion."""
    if "dhcp" not in norm:
        return None
    total_m = re.search(r"total addresses\s+(\d+)", norm)
    leased_m = re.search(r"leased\s+(\d+)", norm)
    zero_avail = "zero available" in norm or "0 available" in norm
    exhausted = False
    if total_m and leased_m:
        try:
            exhausted = int(total_m.group(1)) <= int(leased_m.group(1))
        except ValueError:
            exhausted = False
    if not (exhausted or zero_avail):
        return None
    return _make_result(
        "R02_DHCP_POOL_EXHAUSTION",
        "DHCP scope/pool exhausted",
        "The DHCP pool has no free addresses left, so new clients fall back to APIPA (169.254.x.x).",
        ["DHCP pool shows leased addresses equal to total addresses / zero available"],
        "Layer 7",
        "High",
        "show ip dhcp pool",
        "Increase the DHCP pool size, shorten the lease time, or exclude/reclaim unused addresses.",
    )


def rule_dns_disabled(norm: str, raw: str) -> Optional[RuleResult]:
    """3. DNS disabled/configuration issue."""
    if "no ip domain-lookup" not in norm and "domain-lookup" not in norm:
        if "name-server" not in norm or "not active" not in norm:
            return None
    if "no ip domain-lookup" not in norm and "not active" not in norm:
        return None
    return _make_result(
        "R03_DNS_DISABLED",
        "DNS resolution disabled/misconfigured",
        "Name resolution is disabled ('no ip domain-lookup') or the configured DNS server is inactive, so hostnames fail to resolve even though raw IP connectivity works.",
        ["'no ip domain-lookup' and/or an inactive 'ip name-server' entry found in evidence"],
        "Layer 7",
        "Medium",
        "show running-config | include domain-lookup|name-server",
        "Enable lookups with 'ip domain-lookup' and confirm 'ip name-server <ip>' points to a reachable DNS server.",
    )


def rule_ospf_hello_mismatch(norm: str, raw: str) -> Optional[RuleResult]:
    """4. OSPF hello mismatch."""
    hellos = re.findall(r"hello[- ]interval\s+(\d+)", norm)
    if "ospf" in norm and len(hellos) >= 2 and len(set(hellos)) > 1:
        return _make_result(
            "R04_OSPF_HELLO_MISMATCH",
            "OSPF hello/dead timer mismatch",
            f"Neighboring routers advertise mismatched OSPF hello intervals ({', '.join(sorted(set(hellos)))}), preventing adjacency from forming.",
            [f"hello-interval values found: {hellos}"],
            "Layer 3",
            "High",
            "show ip ospf interface",
            "Set matching 'ip ospf hello-interval' (and dead-interval) values on both sides of the link.",
        )
    return None


def rule_acl_blocking_traffic(norm: str, raw: str) -> Optional[RuleResult]:
    """5. ACL blocking specified traffic (explicit deny)."""
    if re.search(r"access-list\s+\d+\s+deny\s+\w+.*eq\s+\d+", norm) or re.search(
        r"deny\s+tcp.*eq\s+(80|443|21|20|22|23|25|53)", norm
    ):
        m = re.search(r"eq\s+(\d+)", norm)
        port = m.group(1) if m else "the target service"
        return _make_result(
            "R05_ACL_EXPLICIT_DENY",
            "ACL explicitly blocking required traffic",
            f"An access-list entry explicitly denies traffic to port {port}, blocking the required service.",
            ["'deny ... eq <port>' entry found in the ACL"],
            "Layer 4",
            "Medium",
            "show access-lists",
            "Edit the ACL to permit the required port/protocol, or remove the offending deny statement.",
        )
    return None


def rule_nat_missing_overload(norm: str, raw: str) -> Optional[RuleResult]:
    """6 / 25. NAT/PAT overload keyword missing."""
    has_nat_list_stmt = "ip nat inside source list" in norm
    overload_missing = "missing overload" in norm or (
        has_nat_list_stmt and "overload" not in norm
    )
    if has_nat_list_stmt and overload_missing:
        return _make_result(
            "R06_NAT_MISSING_OVERLOAD",
            "PAT/NAT overload keyword missing",
            "The dynamic NAT statement maps inside addresses to an interface without the 'overload' keyword, so only one internal host can translate at a time (or PAT is not active at all).",
            ["'ip nat inside source list ... interface ...' present without 'overload'"],
            "Layer 3",
            "High",
            "show ip nat translations",
            "Append the 'overload' keyword to the NAT statement so multiple internal hosts can share the public IP (PAT).",
        )
    return None


def rule_guest_acl_permissive(norm: str, raw: str) -> Optional[RuleResult]:
    """7. Guest isolation / overly permissive ACL."""
    if "guest" in norm and re.search(r"permit\s+ip\s+\S+\s+\S+\s+any", norm):
        return _make_result(
            "R07_GUEST_ACL_PERMISSIVE",
            "Overly permissive ACL on Guest VLAN",
            "The guest-facing ACL permits IP traffic from the guest subnet to 'any' destination, so guest clients can reach internal/private servers instead of being isolated to the internet only.",
            ["ACL rule 'permit ip <guest-subnet> ... any' found"],
            "Layer 3/4",
            "High",
            "show access-lists GUEST_ACL",
            "Restrict the guest ACL to permit only internet-bound traffic and explicitly deny access to internal RFC1918 ranges.",
        )
    return None


def rule_vlan_missing_from_trunk(norm: str, raw: str) -> Optional[RuleResult]:
    """8. VLAN not allowed on trunk."""
    m = re.search(r"switchport trunk allowed vlan\s+([0-9, ]+)", norm)
    if m:
        missing_hint = re.search(r"vlan\s+(\d+)\s+missing", norm) or re.search(
            r"missing from allowed list.*?vlan\s*(\d+)?", norm
        )
        allowed = m.group(1).strip()
        detail = f"VLAN(s) missing from allowed list {allowed}"
        return _make_result(
            "R08_VLAN_PRUNED_FROM_TRUNK",
            "VLAN missing/pruned from trunk allowed list",
            f"The trunk's allowed-VLAN list ({allowed}) does not include a VLAN that traffic needs to cross, so that VLAN's frames are dropped on the trunk.",
            [f"'switchport trunk allowed vlan {allowed}'"],
            "Layer 2",
            "Medium",
            "show interfaces trunk",
            "Add the missing VLAN to the trunk with 'switchport trunk allowed vlan add <vlan-id>'.",
        )
    return None


def rule_wrong_default_gateway(norm: str, raw: str) -> Optional[RuleResult]:
    """9. Wrong default gateway on a host (gateway configured differs
    from the gateway the topology expects)."""
    target_m = re.search(r"cannot ping default gateway\s+(\d{1,3}(?:\.\d{1,3}){3})", norm)
    configured_m = re.search(
        r"(?:gateway set to|shows default gateway|shows the default gateway)\s+(\d{1,3}(?:\.\d{1,3}){3})",
        norm,
    )
    if target_m and configured_m:
        expected = target_m.group(1)
        configured = configured_m.group(1)
        if expected != configured:
            return _make_result(
                "R09_WRONG_DEFAULT_GATEWAY",
                "Host default gateway misconfigured",
                f"The host is configured with default gateway {configured}, but the network expects {expected}. The host will never reach off-subnet destinations.",
                [f"Host default gateway shown as {configured}", f"Symptom references expected gateway {expected}"],
                "Layer 3",
                "High",
                "show running-config (or ipconfig on the host)",
                f"Reconfigure the host's default gateway to {expected}.",
            )
    return None


def rule_management_svi_shutdown(norm: str, raw: str) -> Optional[RuleResult]:
    """10. Management SVI shutdown."""
    if re.search(r"interface vlan\s*1\b", norm) and "shutdown" in norm and "no shutdown" not in norm:
        return _make_result(
            "R10_MGMT_SVI_SHUTDOWN",
            "Management SVI (VLAN interface) is shut down",
            "The switch's management VLAN interface (typically VLAN 1) is administratively shut down, blocking SSH/management access even though the switch itself is forwarding traffic.",
            ["'interface Vlan1' block contains 'shutdown' with no matching 'no shutdown'"],
            "Layer 2",
            "Low",
            "show ip interface brief",
            "Enter the VLAN interface and run 'no shutdown' to restore management access.",
        )
    return None


def rule_duplicate_ip(norm: str, raw: str) -> Optional[RuleResult]:
    """11. Duplicate IP address indicators."""
    if "dup_addr" in norm or "duplicate address" in norm or "duplicate ip" in norm:
        ip_m = re.search(r"duplicate address\s+(\d{1,3}(?:\.\d{1,3}){3})", norm)
        ip = ip_m.group(1) if ip_m else "an address on the segment"
        return _make_result(
            "R11_DUPLICATE_IP",
            "Duplicate IP address on the segment",
            f"Two hosts are statically configured with the same IP address ({ip}), causing intermittent connectivity and ARP conflicts for both.",
            ["'%IP-4-DUP_ADDR' (or equivalent duplicate-address) log message found"],
            "Layer 3",
            "High",
            "show ip arp",
            "Identify both hosts holding the duplicate address and reassign one of them to a unique, unused IP.",
        )
    return None


def rule_wrong_subnet_mask(norm: str, raw: str) -> Optional[RuleResult]:
    """12. Wrong subnet mask (gateway falls outside the host's subnet)."""
    ip_mask = re.search(r"ip\s+(\d{1,3}(?:\.\d{1,3}){3})\s+mask\s+(\d{1,3}(?:\.\d{1,3}){3})", norm)
    gw = re.search(r"gateway\s+(\d{1,3}(?:\.\d{1,3}){3})", norm)
    outside = "outside" in norm and ("subnet" in norm or "boundary" in norm)
    if ip_mask and gw and outside:
        return _make_result(
            "R12_GATEWAY_OUTSIDE_SUBNET",
            "Default gateway is outside the host's subnet",
            f"With mask {ip_mask.group(2)}, host {ip_mask.group(1)} and gateway {gw.group(1)} fall in different subnets, so the host cannot reach the gateway directly.",
            [f"Host {ip_mask.group(1)}/{ip_mask.group(2)}, gateway {gw.group(1)} flagged as outside subnet boundary"],
            "Layer 3",
            "High",
            "show ip interface brief / verify subnet math",
            "Correct the subnet mask or reassign the gateway/host addressing so the gateway falls inside the host's subnet.",
        )
    return None


def rule_wrong_access_vlan(norm: str, raw: str) -> Optional[RuleResult]:
    """13/14. Missing VLAN or wrong access VLAN on a switchport."""
    m = re.search(r"switchport access vlan\s+(\d+)", norm)
    if m:
        # Only flag as "wrong" when the surrounding evidence mentions a
        # different intended VLAN number (e.g. via topology note),
        # otherwise this alone isn't necessarily a fault.
        vlan_mentions = re.findall(r"vlan\s+(\d+)", norm)
        configured_vlan = m.group(1)
        others = [v for v in vlan_mentions if v != configured_vlan]
        if others:
            return _make_result(
                "R13_WRONG_ACCESS_VLAN",
                "Switchport assigned to the wrong access VLAN",
                f"The port is configured with 'switchport access vlan {configured_vlan}', which does not match the VLAN ({', '.join(sorted(set(others)))}) the device is expected to be in.",
                [f"'switchport access vlan {configured_vlan}' found alongside a reference to VLAN {', '.join(sorted(set(others)))}"],
                "Layer 2",
                "Medium",
                "show interfaces status",
                f"Change the port's access VLAN with 'switchport access vlan {others[0]}' to match the intended VLAN.",
            )
    return None


def rule_trunk_mismatch_access(norm: str, raw: str) -> Optional[RuleResult]:
    """15. Inter-switch link mistakenly configured as access instead of
    trunk on both ends."""
    access_count = len(re.findall(r"switchport mode access", norm))
    if access_count >= 2 and ("cannot ping each other across switch" in norm or "vlan" in norm):
        return _make_result(
            "R14_LINK_SHOULD_BE_TRUNK",
            "Inter-switch link configured as access instead of trunk",
            "The link between the two switches is set to access mode on both ends, so only a single VLAN can traverse it, breaking connectivity for hosts on the same VLAN across switches.",
            ["'switchport mode access' found on both ends of the inter-switch link"],
            "Layer 2",
            "High",
            "show interfaces switchport",
            "Reconfigure the inter-switch link as a trunk ('switchport mode trunk') on both ends and allow the required VLANs.",
        )
    return None


def rule_missing_route(norm: str, raw: str) -> Optional[RuleResult]:
    """16. Missing route (no matching route statement referenced)."""
    has_route_word = re.search(r"\broutes?\b", norm) is not None
    if has_route_word and "missing" in norm and "ospf" not in norm and "static" not in norm:
        return _make_result(
            "R15_MISSING_ROUTE",
            "Missing route to destination network",
            "The routing table lacks a route (static or dynamic) to the destination network mentioned in the symptom, so traffic cannot be forwarded there.",
            ["Symptom/evidence references missing routes to a remote network"],
            "Layer 3",
            "High",
            "show ip route",
            "Add the missing route via a static route or ensure the correct dynamic routing protocol is advertising the network.",
        )
    return None


def rule_invalid_static_route(norm: str, raw: str) -> Optional[RuleResult]:
    """17. Incorrect static route (unreachable next hop)."""
    m = re.search(r"ip route\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})", norm)
    if m and ("unreachable" in norm):
        return _make_result(
            "R16_INVALID_STATIC_ROUTE",
            "Static route points to an unreachable next hop",
            f"The static route 'ip route {m.group(1)} {m.group(2)} {m.group(3)}' uses a next-hop address that is not reachable, so traffic matching this route is silently dropped.",
            [f"'ip route {m.group(1)} {m.group(2)} {m.group(3)}' flagged as unreachable next-hop"],
            "Layer 3",
            "High",
            "show ip route / ping <next-hop>",
            "Correct the next-hop IP address in the static route, or point it to a valid, reachable next hop or exit interface.",
        )
    return None


def rule_default_route_issue(norm: str, raw: str) -> Optional[RuleResult]:
    """18. Incorrect/missing default route."""
    if ("default route" in norm or "0.0.0.0 0.0.0.0" in norm) and (
        "missing" in norm or "incorrect" in norm or "wrong" in norm
    ):
        return _make_result(
            "R17_DEFAULT_ROUTE_ISSUE",
            "Default route missing or incorrect",
            "The router lacks a correct default route (0.0.0.0/0), so traffic to unknown/external destinations has no path out.",
            ["Evidence references a missing or incorrect default route"],
            "Layer 3",
            "High",
            "show ip route 0.0.0.0",
            "Configure (or correct) a default route: 'ip route 0.0.0.0 0.0.0.0 <next-hop-or-exit-interface>'.",
        )
    return None


def rule_ospf_passive_interface(norm: str, raw: str) -> Optional[RuleResult]:
    """19. OSPF network/advertisement issue via passive-interface on an
    active link."""
    if "passive-interface" in norm and "ospf" in norm:
        m = re.search(r"passive-interface\s+([a-z0-9/.]+)", norm)
        iface = m.group(1) if m else "the link"
        return _make_result(
            "R18_OSPF_PASSIVE_ON_ACTIVE_LINK",
            "OSPF passive-interface suppresses adjacency on an active link",
            f"'{iface}' is marked passive-interface under OSPF, so hello packets are suppressed on a link that actually needs an adjacency, preventing the neighboring router from learning routes.",
            [f"'passive-interface {iface}' found under 'router ospf'"],
            "Layer 3",
            "High",
            "show ip ospf interface brief",
            f"Remove '{iface}' from the passive-interface list (or use 'no passive-interface {iface}') so OSPF hellos are sent on that link.",
        )
    return None


def rule_ospf_neighbor_mismatch(norm: str, raw: str) -> Optional[RuleResult]:
    """20. OSPF neighbor/config mismatch (area, network type, etc.),
    distinct from the hello-timer-specific rule above."""
    if "ospf" in norm and re.search(r"area\s+\d+.*area\s+\d+", norm):
        areas = re.findall(r"area\s+(\d+)", norm)
        if len(set(areas)) > 1:
            return _make_result(
                "R19_OSPF_AREA_MISMATCH",
                "OSPF area ID mismatch between neighbors",
                f"Neighboring routers are configured with mismatched OSPF area IDs ({', '.join(sorted(set(areas)))}), which prevents adjacency from forming on that link.",
                [f"Multiple distinct OSPF area IDs found: {areas}"],
                "Layer 3",
                "High",
                "show ip ospf interface",
                "Ensure both routers configure the same OSPF area ID on the shared link.",
            )
    return None


def rule_acl_wildcard_mask(norm: str, raw: str) -> Optional[RuleResult]:
    """21. ACL wildcard mask issue."""
    m = re.search(r"access-list\s+\d+.*?(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})", norm)
    if m and "wildcard" in norm:
        return _make_result(
            "R20_ACL_WILDCARD_MASK_ISSUE",
            "Incorrect ACL wildcard mask",
            f"The wildcard mask {m.group(2)} used in the ACL does not correctly cover the intended source network {m.group(1)}, causing the rule to match the wrong set of hosts.",
            [f"ACL entry uses network {m.group(1)} with wildcard {m.group(2)}"],
            "Layer 3/4",
            "Medium",
            "show access-lists",
            "Recalculate and correct the wildcard mask so it matches exactly the intended subnet.",
        )
    return None


def rule_acl_missing_rule(norm: str, raw: str) -> Optional[RuleResult]:
    """22. Missing ACL rule (a required port is absent from the ACL)."""
    missing_port = re.search(r"missing (?:port\s+)?(\d+)", norm)
    if missing_port and "access-list" in norm:
        port = missing_port.group(1)
        return _make_result(
            "R21_ACL_MISSING_RULE",
            "ACL is missing a required permit rule",
            f"The access-list does not include a permit entry for port {port}, so traffic that legitimately needs that port is implicitly denied.",
            [f"ACL evidence notes a missing rule for port {port}"],
            "Layer 4",
            "Medium",
            "show access-lists",
            f"Add a 'permit tcp ... eq {port}' entry to the ACL for the required service.",
        )
    return None


def rule_acl_wrong_placement(norm: str, raw: str) -> Optional[RuleResult]:
    """23. ACL applied on the wrong interface/direction."""
    if "access-list" in norm and re.search(r"wrong (interface|direction)", norm):
        return _make_result(
            "R22_ACL_WRONG_PLACEMENT",
            "ACL applied to the wrong interface or direction",
            "The access-list is applied on the wrong interface or in the wrong direction (in/out), so it fails to filter the traffic it was intended to control.",
            ["Evidence indicates the ACL is bound to the wrong interface/direction"],
            "Layer 3/4",
            "Medium",
            "show ip interface | include access list",
            "Reapply the ACL to the correct interface and direction using 'ip access-group <name> in|out'.",
        )
    return None


def rule_nat_missing_inside(norm: str, raw: str) -> Optional[RuleResult]:
    """24. NAT inside/outside direction issue."""
    if "nat" in norm and ("missing ip nat inside" in norm or "missing ip nat outside" in norm):
        side = "inside" if "missing ip nat inside" in norm else "outside"
        return _make_result(
            "R23_NAT_MISSING_DIRECTION",
            f"NAT '{side}' direction not applied on the interface",
            f"A NAT translation rule exists, but the interface is missing the 'ip nat {side}' command, so the router never applies translation to traffic crossing that interface.",
            [f"'ip nat {side}' missing from the relevant interface configuration"],
            "Layer 3",
            "High",
            "show ip nat statistics",
            f"Apply 'ip nat {side}' on the correct interface so the NAT rule takes effect.",
        )
    return None


def rule_port_security_violation(norm: str, raw: str) -> Optional[RuleResult]:
    """26. Port security violation."""
    if "psecure_violation" in norm or "port_security" in norm or "port security" in norm and "violation" in norm:
        return _make_result(
            "R24_PORT_SECURITY_VIOLATION",
            "Port security violation / err-disabled port",
            "The switchport exceeded its configured maximum secure MAC address count, triggering a security violation that put the port into an err-disabled (or restricted) state.",
            ["'%PORT_SECURITY-2-PSECURE_VIOLATION' (or equivalent) log message found"],
            "Layer 2",
            "Medium",
            "show port-security interface <if>",
            "Identify the offending device, clear the violation, and re-enable the port ('shutdown' then 'no shutdown'), adjusting the max MAC count/violation action if needed.",
        )
    return None


def rule_dhcp_relay_missing_helper(norm: str, raw: str) -> Optional[RuleResult]:
    """27. DHCP relay issue (missing ip helper-address)."""
    if "helper-address" in norm and "missing" in norm:
        return _make_result(
            "R25_DHCP_RELAY_MISSING_HELPER",
            "DHCP relay (ip helper-address) missing",
            "The router's LAN-facing interface has no 'ip helper-address' configured, so DHCP Discover broadcasts from clients on that segment are never relayed to the remote DHCP server.",
            ["'ip helper-address' missing from the interface configuration"],
            "Layer 7",
            "High",
            "show running-config interface <if>",
            "Add 'ip helper-address <dhcp-server-ip>' to the client-facing interface to relay DHCP requests.",
        )
    return None


def rule_hsrp_timer_mismatch(norm: str, raw: str) -> Optional[RuleResult]:
    """28. HSRP issue (timer mismatch causing flapping/active takeover)."""
    hellos = re.findall(r"standby\s+\d+\s+priority\s+\d+\s+hello\s+(\d+)", norm)
    if "standby" in norm and len(hellos) >= 2 and len(set(hellos)) > 1:
        return _make_result(
            "R26_HSRP_TIMER_MISMATCH",
            "HSRP hello timer mismatch between peers",
            f"HSRP peers advertise different hello timers ({', '.join(sorted(set(hellos)))}), which causes the standby router to repeatedly believe the active router has failed and take over the Active role.",
            [f"standby hello timers found: {hellos}"],
            "Layer 3",
            "Medium",
            "show standby brief",
            "Configure matching HSRP hello/hold timers on both the active and standby routers.",
        )
    return None


def rule_ipv6_ra_suppressed(norm: str, raw: str) -> Optional[RuleResult]:
    """29. IPv6 SLAAC issue (Router Advertisements suppressed)."""
    if "ipv6 nd suppress-ra" in norm:
        return _make_result(
            "R27_IPV6_RA_SUPPRESSED",
            "IPv6 Router Advertisements suppressed",
            "'ipv6 nd suppress-ra' is enabled on the router's LAN interface, so it stops sending Router Advertisements, preventing SLAAC clients from receiving prefix information and a default route.",
            ["'ipv6 nd suppress-ra' found in interface configuration"],
            "Layer 3",
            "Medium",
            "show ipv6 interface <if>",
            "Remove suppression with 'no ipv6 nd suppress-ra' on the interface so RAs are sent again.",
        )
    return None


def rule_cdp_disabled(norm: str, raw: str) -> Optional[RuleResult]:
    """30. CDP issue (globally disabled)."""
    if "no cdp run" in norm:
        return _make_result(
            "R28_CDP_DISABLED_GLOBALLY",
            "CDP disabled globally",
            "Cisco Discovery Protocol is disabled device-wide ('no cdp run'), so the device no longer advertises itself to, or discovers, directly connected Cisco neighbors.",
            ["'no cdp run' found in the running configuration"],
            "Layer 2",
            "Low",
            "show cdp neighbors",
            "Re-enable CDP globally with 'cdp run' (and, if needed, 'cdp enable' on the specific interface).",
        )
    return None


def rule_native_vlan_mismatch(norm: str, raw: str) -> Optional[RuleResult]:
    """Native VLAN mismatch on a trunk (extra VLAN-trunking check)."""
    natives = re.findall(r"native vlan\s+(\d+)", norm)
    if len(natives) >= 2 and len(set(natives)) > 1:
        return _make_result(
            "R29_NATIVE_VLAN_MISMATCH",
            "Native VLAN mismatch on trunk link",
            f"The two ends of the trunk use different native VLANs ({', '.join(sorted(set(natives)))}), which causes VLAN leakage and native-VLAN mismatch warnings/log flooding.",
            [f"native VLAN values found: {natives}"],
            "Layer 2",
            "Low",
            "show interfaces trunk",
            "Configure the same native VLAN on both ends of the trunk link.",
        )
    return None


def rule_vtp_domain_mismatch(norm: str, raw: str) -> Optional[RuleResult]:
    """VTP domain name mismatch (case-sensitive) — extra switching check."""
    m = re.findall(r"vtp domain\s+(\S+)", norm)
    if len(m) >= 2 and len(set(m)) > 1:
        return _make_result(
            "R30_VTP_DOMAIN_MISMATCH",
            "VTP domain name mismatch",
            f"The switches are configured with different VTP domain names ({', '.join(sorted(set(m)))}, case-sensitive), so VLAN database updates are not exchanged between them.",
            [f"VTP domain values found: {m}"],
            "Layer 2",
            "Medium",
            "show vtp status",
            "Set an identical, case-matching VTP domain name on every switch in the VTP domain.",
        )
    return None


def rule_dai_untrusted_uplink(norm: str, raw: str) -> Optional[RuleResult]:
    """Dynamic ARP Inspection trust missing on uplink — extra security check."""
    if "arp inspection" in norm and "trust" in norm and "missing" in norm:
        return _make_result(
            "R31_DAI_UNTRUSTED_UPLINK",
            "DAI trust not configured on uplink port",
            "Dynamic ARP Inspection is enabled, but the switch uplink is not configured as a trusted port ('ip arp inspection trust'), so legitimate ARP replies relayed from upstream are dropped.",
            ["'ip arp inspection trust' missing on the uplink interface"],
            "Layer 2",
            "High",
            "show ip arp inspection interfaces",
            "Configure 'ip arp inspection trust' on the uplink/trunk port connecting to the rest of the network.",
        )
    return None


def rule_radius_secret_mismatch(norm: str, raw: str) -> Optional[RuleResult]:
    """RADIUS shared-secret mismatch — extra wireless/AAA check."""
    if "radius-server host" in norm and ("incorrect" in norm or "mismatch" in norm):
        return _make_result(
            "R32_RADIUS_SECRET_MISMATCH",
            "RADIUS shared secret mismatch",
            "The RADIUS shared secret configured on the network device does not match the one configured on the RADIUS server, so 802.1X/WPA2-Enterprise authentication requests are rejected.",
            ["'radius-server host ... key <incorrect-secret>' found"],
            "Layer 7",
            "High",
            "test aaa group radius <user> <password>",
            "Reconfigure matching shared secrets on both the network device and the RADIUS server.",
        )
    return None


def rule_missing_dot1q_encapsulation(norm: str, raw: str) -> Optional[RuleResult]:
    """Missing 802.1Q encapsulation on a router sub-interface — extra
    inter-VLAN routing check."""
    m = re.search(r"([a-z]+[a-z0-9/]*\.\d+)", norm)
    if "encapsulation" in norm and "missing" in norm and "dot1q" in norm.replace(" ", ""):
        iface = m.group(1) if m else "the sub-interface"
        return _make_result(
            "R34_MISSING_DOT1Q_ENCAPSULATION",
            "Missing 802.1Q encapsulation on router sub-interface",
            f"Sub-interface {iface} has no 'encapsulation dot1Q <vlan-id>' statement, so it cannot tag/untag frames for its VLAN and inter-VLAN routing fails for that VLAN.",
            [f"'encapsulation dot1Q' missing on {iface}"],
            "Layer 2/3",
            "High",
            f"show interfaces {iface}",
            f"Configure 'encapsulation dot1Q <vlan-id>' on {iface} to match the VLAN it should route for.",
        )
    return None


def rule_ospf_redistribution_missing_subnets(norm: str, raw: str) -> Optional[RuleResult]:
    """OSPF redistribution missing 'subnets' keyword — extra OSPF check."""
    if "redistribute" in norm and "ospf" in norm and "subnets" in norm and "missing" in norm:
        return _make_result(
            "R33_OSPF_REDISTRIBUTE_MISSING_SUBNETS",
            "OSPF redistribution missing 'subnets' keyword",
            "The redistribute statement into OSPF omits the 'subnets' keyword, so only classful major networks are redistributed and subnetted routes from the other protocol are silently dropped.",
            ["'redistribute ...' found without the 'subnets' keyword"],
            "Layer 3",
            "Medium",
            "show ip ospf database external",
            "Add the 'subnets' keyword to the redistribute statement, e.g. 'redistribute eigrp 100 subnets'.",
        )
    return None


def rule_acl_https_missing_permit(norm: str, raw: str) -> Optional[RuleResult]:
    """Detect outbound HTTPS blocked by an ACL that permits HTTP but not 443."""
    if (
        ("https" in norm or "ssl/tls" in norm or "port 443" in norm)
        and "access-list" in norm
        and "eq 80" in norm
        and "443" in norm
        and ("missing" in norm or "without" in norm)
    ):
        return _make_result(
            "R35_ACL_HTTPS_MISSING_PERMIT",
            "ACL blocking SSL/TLS port 443",
            "The outbound ACL permits HTTP on port 80 but does not permit HTTPS on port 443, so external SSL/TLS web connections are blocked.",
            ["ACL evidence shows an HTTP permit on port 80 while port 443 is missing."],
            "Layer 4",
            "Medium",
            "show access-lists OUTBOUND",
            "Add an appropriate permit for TCP destination port 443 before the ACL's applicable deny rule.",
        )
    return None


# Ordered list of all rules. Order matters only for presentation; every
# rule is still evaluated independently.
ALL_RULES: List[RuleFunc] = [
    rule_interface_admin_down,
    rule_dhcp_pool_exhaustion,
    rule_dns_disabled,
    rule_ospf_hello_mismatch,
    rule_acl_blocking_traffic,
    rule_nat_missing_overload,
    rule_guest_acl_permissive,
    rule_vlan_missing_from_trunk,
    rule_wrong_default_gateway,
    rule_management_svi_shutdown,
    rule_duplicate_ip,
    rule_wrong_subnet_mask,
    rule_wrong_access_vlan,
    rule_trunk_mismatch_access,
    rule_missing_route,
    rule_invalid_static_route,
    rule_default_route_issue,
    rule_ospf_passive_interface,
    rule_ospf_neighbor_mismatch,
    rule_acl_wildcard_mask,
    rule_acl_https_missing_permit,
    rule_acl_missing_rule,
    rule_acl_wrong_placement,
    rule_nat_missing_inside,
    rule_port_security_violation,
    rule_dhcp_relay_missing_helper,
    rule_hsrp_timer_mismatch,
    rule_ipv6_ra_suppressed,
    rule_cdp_disabled,
    rule_native_vlan_mismatch,
    rule_vtp_domain_mismatch,
    rule_dai_untrusted_uplink,
    rule_radius_secret_mismatch,
    rule_ospf_redistribution_missing_subnets,
    rule_missing_dot1q_encapsulation,
]


def run_checker(symptom: str, topology_note: str, show_outputs: str) -> List[RuleResult]:
    """Run every deterministic rule against the combined evidence text.

    Returns a list of matched RuleResult objects (possibly empty). Never
    raises — a rule that throws an internal error is skipped rather than
    crashing the whole checker, and is reported back via a synthetic
    "rule error" entry so problems are visible instead of silently eaten.
    """
    combined_raw = "\n".join(
        [symptom or "", topology_note or "", show_outputs or ""]
    )
    norm = _normalize(combined_raw)

    results: List[RuleResult] = []
    for rule_fn in ALL_RULES:
        try:
            result = rule_fn(norm, combined_raw)
        except Exception as exc:  # pragma: no cover - defensive, keeps UI alive
            results.append(
                RuleResult(
                    rule_id=f"ERROR_{rule_fn.__name__}",
                    matched=True,
                    title="Rule execution error",
                    root_cause=f"Rule '{rule_fn.__name__}' raised an internal error and was skipped: {exc}",
                    evidence=[],
                    osi_layer="",
                    severity="Info",
                )
            )
            continue
        if result is not None and result.matched:
            results.append(result)

    return results
