# CNAME vs A records

For Benjamin Duivesteyn, deAutomation — 6 November 2026

## Overview

An **A record** answers one question: which IPv4 address does this name point at? A **CNAME** answers a different one: this name is an alias for another name, so go and look that name up. Everything else — who maintains the address, what else can live at the name, how a change propagates — follows from that single difference.

The distinction stopped being theoretical on 6 November, when `data.deautomation.co` moved into a Google Cloud DNS zone. The apex stayed an A record, the product hosts became CNAMEs, and at Namecheap only NS records remain. That is now the standard shape for every host we sell.

## Details

### The difference in one table

| Question | A record | CNAME |
| --- | --- | --- |
| What it stores | An IPv4 address (`216.239.32.21`) | Another DNS name (`ghs.googlehosted.com.`) |
| Who owns the address | Us — we edit it when the target changes | The target's owner — we never see the address |
| Extra lookup at resolve time | None | Yes: the resolver re-queries the target |
| Allowed at a zone apex | Yes | No (it would collide with the zone's own SOA and NS) |
| Can other records sit at the same name | Yes (TXT, MX, NS, subdomains) | No — a CNAME must be the only record at its name |
| Can the name have children | Yes (`cwp.data` under `data`) | Not practically — it is an alias, not a branch |
| Changes when the host moves | We update the record | The target updates its A record; we do nothing |

Two related record types matter here. **AAAA** is the same as A for IPv6. **ANAME/ALIAS** is a provider-side trick that behaves like a CNAME at an apex by resolving the target on the provider's side; Google Cloud DNS does not offer it, which is exactly why our apexes are plain A records.

### Where each lives in our estate

| Name | Type | Value | Why |
| --- | --- | --- | --- |
| `data.deautomation.co` | A | `216.239.32.21`<br>`216.239.34.21`<br>`216.239.36.21`<br>`216.239.38.21` | Apex of the delegated zone; must keep the SPF TXT and the product hosts beneath it |
| `clients.deautomation.co` | A | The same four addresses | Same shape, already delegated to Cloud DNS |
| `cwp.data.deautomation.co` | CNAME | `ghs.googlehosted.com.` | Product host pointing at Google's frontend; Google owns the addresses |
| `ppc.data.deautomation.co` | CNAME | `ghs.googlehosted.com.` | Added 6 November for the new PPC site |
| `rc.clients.deautomation.co` | CNAME | `ghs.googlehosted.com.` | Same pattern under the clients zone |
| `data.deautomation.co` | NS | `ns-cloud-c1–c4.googledomains.com.` | Delegation: tells resolvers Google is now authoritative |
| `data.deautomation.co` | TXT | `v=spf1 include:_spf.mailersend.net ~all` | Mail authorisation; cannot sit beside a CNAME |

The NS row is the one people miss. Delegation is not an address record at all: it says who to ask next. It is what lets us add `sgp.data` or `ops.data` later without touching Namecheap again.

Both zones carry the same AAAA set, CAA policy (`pki.goog`, `letsencrypt.org`), DNSSEC and a family label; only `data` needs the SPF TXT. A record added to one zone should be checked against the other.

### What a resolver actually does for `ppc.data.deautomation.co`

1. The stub resolver asks the root, then `.com`, then the `deautomation.co` nameservers at Namecheap.
2. Namecheap returns the **NS** set for `data`: `ns-cloud-c1` through `ns-cloud-c4`.
3. The resolver asks Google for `ppc.data`; the zone answers with a **CNAME** to `ghs.googlehosted.com.`
4. The resolver asks for `ghs.googlehosted.com` and gets an **A** record — `192.178.187.121` at the time of writing.
5. The browser connects to that address, sends `ppc.data.deautomation.co` in the TLS handshake, and Google's frontend routes it to the `ppc-data` Cloud Run service.

Until the Namecheap delegation exists, step 2 never reaches Google, so `ppc.data` is still NXDOMAIN — the CNAME exists only inside the new zone. That is the one reason the record is not live yet.

### Why the apex is an A record

- A zone apex must carry SOA and NS records, and a CNAME cannot coexist with any other record.
- `data` has children (`cwp.data`, `ppc.data`) and a TXT (SPF). A CNAME at `data` would make all of those impossible.
- The four addresses are Google's frontend for the `data-catalogue` mapping. They are stable in practice, and they are ours to keep correct.

### Why the product hosts are CNAMEs

- Google owns `ghs.googlehosted.com` and its addresses, so it can move the frontend without us editing anything.
- Each product host is one mapping and one certificate; the CNAME is the only record the mapping needs.
- Adding a product is a `data-zone` record, not a Namecheap edit.

### Traps worth remembering

- Never put a CNAME at a zone apex. It looks tidy and breaks the zone.
- A CNAME blocks every other record at that name: no TXT, no MX, no NS, no children. Mail and aliases cannot share a name.
- `dig +short TXT cwp.data.deautomation.co` prints the CNAME target, not a TXT answer. Use `dig TXT +noall +answer` when checking mail records.
- TTL matters on cutover day, not after: the old Namecheap records cached for 1800 seconds, the new zone uses 300.
- Records are edited where they are authoritative. After delegation, a Namecheap A/TXT edit for `data` is a no-op.

### What changed on 6 November

A `data-zone` was created and populated with every record `data` needs — A, AAAA, CAA, the SPF TXT and the `cwp.data` CNAME — before the registrar was touched, so delegation cannot point at an empty zone. The `ppc.data` CNAME and its Cloud Run mapping followed. The zone matches `clients-zone` in A, AAAA, CAA, DNSSEC and labelling, and was verified on `ns-cloud-c1`. Delegation is the only remaining step, and it is registrar-side.

## Next steps

1. Add the four `data` NS records at Namecheap, and leave the A, TXT and `cwp.data` rows in place until delegation is confirmed.
2. Confirm propagation with `dig NS data.deautomation.co` and `dig CNAME ppc.data.deautomation.co`; then delete the now-inert registrar copies so the Google zone is the only source.
3. Allow 15–30 minutes for the `ppc.data` certificate, then check the mapping reports `Ready: True`.
4. Add future product hosts (`sgp.data`, `ops.data`) as records in `data-zone`; the registrar is not involved again.

<div style="height: 12mm;"></div>

**Benjamin Duivesteyn**  
Principal, deAutomation  
0490 501 761   hi@deautomation.co  
deautomation.co
