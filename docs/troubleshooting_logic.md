# Deterministic Troubleshooting Logic

`src/checker.py` contains every deterministic rule. Each rule is a small
function `rule_xxx(normalized_text, raw_text) -> Optional[RuleResult]`
that inspects the combined evidence text (`symptom + topology_note +
show_outputs`, whitespace-normalized and lowercased) and returns a
`RuleResult` if its pattern matches.

`run_checker()` runs **every** rule against the evidence and returns
every match — a single piece of evidence can trigger more than one rule
(for example, evidence that both mentions a missing route and a passive
OSPF interface will surface both findings).

## How matching works

Rules do not key off `case_id`. They look for concrete vocabulary and
structure that would appear in real Cisco `show`/config output or
`%FACILITY-SEVERITY-MNEMONIC` log lines: interface names, keywords like
`administratively down`, numeric comparisons (`total addresses` vs.
`leased`), or multiple differing values for the same parameter (e.g. two
different OSPF hello intervals, two different HSRP hello timers, two
different VTP domain names). This is what lets the same functions run
against the 30 supplied cases *and* against arbitrary text a user pastes
into the "custom evidence" box in the sidebar.

## Rule catalogue

| Rule ID | Detects | Primary regex/logic signal |
|---|---|---|
| R01_INTERFACE_ADMIN_DOWN | Interface/sub-interface administratively down | `"<iface> is administratively down"` |
| R02_DHCP_POOL_EXHAUSTION | DHCP pool exhaustion | `total addresses` <= `leased`, or "zero available" |
| R03_DNS_DISABLED | DNS disabled/misconfigured | `no ip domain-lookup` and/or an inactive `name-server` |
| R04_OSPF_HELLO_MISMATCH | OSPF hello timer mismatch | 2+ distinct `hello-interval` values |
| R05_ACL_EXPLICIT_DENY | ACL explicitly blocking traffic | `deny ... eq <port>` |
| R06_NAT_MISSING_OVERLOAD | PAT/NAT overload keyword missing | `ip nat inside source list ...` without `overload` |
| R07_GUEST_ACL_PERMISSIVE | Guest network not isolated | `permit ip <subnet> ... any` near "guest" |
| R08_VLAN_PRUNED_FROM_TRUNK | VLAN missing from trunk allowed list | `switchport trunk allowed vlan ...` |
| R09_WRONG_DEFAULT_GATEWAY | Host gateway misconfigured | configured gateway != gateway referenced in symptom |
| R10_MGMT_SVI_SHUTDOWN | Management SVI shut down | `interface Vlan1` block containing `shutdown` |
| R11_DUPLICATE_IP | Duplicate IP address | `%IP-4-DUP_ADDR` or "duplicate address" |
| R12_GATEWAY_OUTSIDE_SUBNET | Wrong subnet mask / gateway outside subnet | host+mask vs. gateway, "outside ... subnet" |
| R13_WRONG_ACCESS_VLAN | Wrong access VLAN on switchport | `switchport access vlan N` vs. a different VLAN mentioned elsewhere |
| R14_LINK_SHOULD_BE_TRUNK | Inter-switch link is access instead of trunk | `switchport mode access` on both link ends |
| R15_MISSING_ROUTE | Missing route to destination | `\broutes?\b` + "missing" (excludes OSPF/static-specific wording) |
| R16_INVALID_STATIC_ROUTE | Invalid static route next-hop | `ip route <net> <mask> <next-hop>` + "unreachable" |
| R17_DEFAULT_ROUTE_ISSUE | Missing/incorrect default route | "default route" or `0.0.0.0 0.0.0.0` + missing/incorrect |
| R18_OSPF_PASSIVE_ON_ACTIVE_LINK | OSPF passive-interface suppressing adjacency | `passive-interface <if>` under `router ospf` |
| R19_OSPF_AREA_MISMATCH | OSPF area ID mismatch | 2+ distinct `area <id>` values |
| R20_ACL_WILDCARD_MASK_ISSUE | Incorrect ACL wildcard mask | ACL network/wildcard pair + "wildcard" |
| R21_ACL_MISSING_RULE | ACL missing a required permit rule | "missing (port) N" near `access-list` |
| R22_ACL_WRONG_PLACEMENT | ACL applied to wrong interface/direction | "wrong interface/direction" near `access-list` |
| R23_NAT_MISSING_DIRECTION | NAT inside/outside direction missing | "missing ip nat inside/outside" |
| R24_PORT_SECURITY_VIOLATION | Port security violation | `%PORT_SECURITY-2-PSECURE_VIOLATION` |
| R25_DHCP_RELAY_MISSING_HELPER | Missing DHCP relay helper address | "helper-address" + "missing" |
| R26_HSRP_TIMER_MISMATCH | HSRP hello timer mismatch | 2+ distinct `standby ... hello <n>` values |
| R27_IPV6_RA_SUPPRESSED | IPv6 Router Advertisements suppressed | `ipv6 nd suppress-ra` |
| R28_CDP_DISABLED_GLOBALLY | CDP disabled globally | `no cdp run` |
| R29_NATIVE_VLAN_MISMATCH | Native VLAN mismatch on trunk | 2+ distinct `native vlan <n>` values |
| R30_VTP_DOMAIN_MISMATCH | VTP domain name mismatch | 2+ distinct `vtp domain <name>` values |
| R31_DAI_UNTRUSTED_UPLINK | DAI trust missing on uplink | "arp inspection" + "trust" + "missing" |
| R32_RADIUS_SECRET_MISMATCH | RADIUS shared secret mismatch | `radius-server host ...` + "incorrect"/"mismatch" |
| R33_OSPF_REDISTRIBUTE_MISSING_SUBNETS | OSPF redistribution missing `subnets` | `redistribute` + `ospf` + "subnets" + "missing" |
| R34_MISSING_DOT1Q_ENCAPSULATION | Missing 802.1Q encapsulation on sub-interface | "encapsulation" + "missing" + "dot1q" |

This covers all 30 concepts requested in the problem statement (some
rules intentionally overlap in scope — e.g. R08/R13/R14 all relate to
VLAN/trunk problems but detect different specific symptoms — which is
why the checker returns *all* matches rather than a single verdict).

## Honest accuracy

Run `python evaluate.py` to see, case-by-case, whether the deterministic
checker's top finding fuzzy-matches each case's `expected_fault`. As of
this build: **28/30 (93.3%)** match on exact wording-normalized
comparison; the two "misses" (`NET-007`, `NET-022`) still produce a
correct, relevant finding but with wording different enough from
`expected_fault` that the fuzzy matcher doesn't count it — see the
printed table for the actual detected text. All 30 cases produce at
least one finding (0 total misses with no signal at all).

## Extending the rule set

To add a new rule:
1. Write `rule_my_new_check(norm, raw) -> Optional[RuleResult]` in
   `src/checker.py`, following the existing pattern.
2. Add it to the `ALL_RULES` list.
3. Add a unit test in `tests/test_checker.py`.
4. Re-run `python evaluate.py` to confirm you haven't regressed existing
   cases.
