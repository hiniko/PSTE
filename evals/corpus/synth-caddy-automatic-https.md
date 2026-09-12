---
model: claude-sonnet-5
generated_by: 2.1.220 (Claude Code)
generated_on: 2026-09-11
environment: container, evals/Dockerfile.clean
isolation: |
  No CLAUDE.md, no plugin, no hook, no memory, and no configured skill.
  The container holds none of them, so none can reach the model.
constrained: false
grounding_url: https://raw.githubusercontent.com/caddyserver/website/master/src/docs/markdown/automatic-https.md
grounding_licence: Apache-2.0
question: |
  Write a documentation page for automatic HTTPS in the Caddy web server. A copy of an upstream page for this topic is mounted at /grounding/synth-caddy-automatic-https.md. Use it only to check facts and stay accurate. Do not paraphrase it, follow its structure, or reuse its wording: write your own independent documentation page, organised and expressed the way you normally would. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository.
---

# Automatic HTTPS in Caddy

One of Caddy's defining features is that it handles TLS for you. Point it at a domain name and it will get a certificate, keep that certificate renewed, and redirect plain HTTP traffic over to HTTPS — all without extra flags, cron jobs, or a separate ACME client bolted on the side. This page explains how that machinery works and what to expect from it.

## When it kicks in

Caddy doesn't need a special "enable HTTPS" switch. It turns on automatic HTTPS the moment it sees a domain name or IP address somewhere in your configuration — a site address in the Caddyfile, a host matcher in a JSON route, a `--domain`/`--from` flag on the command line, or an entry in the `automate` certificate loader. If Caddy knows what host it's serving, it assumes you want that host served securely.

There are a handful of ways to opt out, in whole or in part:

- Turn it off explicitly (`auto_https off` in the Caddyfile, or the equivalent JSON option)
- Leave hostnames/IPs out of the config entirely
- Bind only to the HTTP port
- Prefix a Caddyfile address with `http://`
- Load certificates manually yourself (Caddy won't manage certs it didn't provision, unless you tell it to via `ignore_loaded_certificates`)

One notable special case: hostnames ending in `.ts.net` are handled by Tailscale, not Caddy's own ACME logic — Caddy fetches those certs from the local `tailscaled` instance at handshake time instead.

## What actually happens

Once automatic HTTPS is live for a site, Caddy will:

1. Obtain a certificate for every qualifying hostname
2. Keep renewing it in the background for as long as the site is configured
3. Add a redirect from HTTP (port 80) to HTTPS (port 443)

This is additive, not destructive — automatic HTTPS never overrides something you configured explicitly. If you already have your own listener on port 80, Caddy slots its redirect routes in after your host-matched routes but ahead of any catch-all route you've defined, so your own HTTP handling still wins where it's more specific.

You can tune or disable individual pieces of this (skip the redirect, exclude specific domains, etc.) through the `automatic_https` JSON options, or via global options in the Caddyfile.

## Which hostnames qualify

Caddy will manage a certificate for any hostname that's non-empty, made up only of letters, digits, hyphens, dots, and an optional wildcard, and doesn't start or end with a dot.

For a *publicly trusted* certificate (one signed by a real CA that browsers recognize), the hostname additionally can't be `localhost` or end in `.local`, `.internal`, or `.home.arpa`, can't be a bare IP address, and can only use a wildcard as the very first label — `*.example.com` is fine, `*.sub.example.com` or `foo.*.example.com` are not.

Anything that doesn't clear that second bar — `localhost`, `127.0.0.1`, a private hostname — still gets HTTPS, just not from a public CA.

## HTTPS for things the public internet can't verify

For internal names and IP addresses, there's no ACME authority willing to vouch for them, so Caddy runs its own miniature certificate authority instead. On first use it generates a root and an intermediate certificate (backed by Smallstep's certificate libraries) and stores them in its data directory under `pki/authorities/local`. The intermediate signs the actual leaf certificates for your sites; the root itself is only used to sign intermediates and is otherwise kept out of memory except when actively needed.

For clients to trust these certificates, the root has to land in the local trust store. Caddy tries to install it there automatically the first time it's used, which is why you may get a one-time password prompt — after that, it shows up as something like "Caddy Local Authority" in your system's trust settings. You can skip this behavior (`skip_install_trust` / `install_trust: false`) or force it later with `caddy trust`, and remove it just as easily with `caddy untrust`. In containers or under a locked-down service account, automatic installation may simply fail silently — at that point it's on you to get the root cert into whatever trust store needs it.

None of this touches ACME or DNS validation; it's purely local, and only useful to clients that trust that specific root.

## Proving you own the domain: ACME challenges

For public certificates, the CA needs proof you control the domain before it will issue anything. Caddy supports the three standard ACME challenge mechanisms, and if more than one is available it picks between them somewhat randomly at first, gradually favoring whichever has been working best for your setup.

**HTTP challenge** — Caddy serves a token over port 80 that the CA fetches directly. Needs port 80 reachable from the internet (or forwarded to Caddy's HTTP port). On by default, zero config.

**TLS-ALPN challenge** — similar idea, but the proof is embedded in a TLS handshake on port 443 using a special SNI/ALPN combination. Needs port 443 reachable. Also on by default, zero config.

**DNS challenge** — Caddy publishes a `TXT` record under `_acme-challenge` for the domain. This one needs no open ports at all and works even for servers with no public IP, but it does require credentials for your DNS provider so Caddy can create and remove the record itself. Enabling it turns the other two off by default. If your DNS host has no API of its own, you can delegate the `_acme-challenge` subdomain via CNAME to a zone that does. Provider support comes from community-maintained plugins.

Wildcard certificates are the one case where you don't get a choice: Let's Encrypt requires the DNS challenge for those, since there's no HTTP or TLS endpoint that could prove ownership of an entire subdomain space.

## Getting certificates for domains you didn't list

Normally Caddy needs every domain spelled out in the config so it can request certificates up front. **On-Demand TLS** flips that around: Caddy waits until a TLS handshake actually arrives for an unfamiliar SNI, holds that handshake open for a few seconds while it fetches a certificate, and completes it once the cert is ready. Every handshake after that is fast, since the certificate is cached and renewed quietly in the background.

This is the feature that makes sense when you're fronting customer-supplied domains, SaaS tenants, or anything where the domain list changes faster than you'd want to reload config for. It's a poor fit for a normal handful of sites you already know the names of.

Because anyone who can complete a TLS handshake to your server could otherwise trigger unlimited certificate requests, on-demand TLS *requires* a guardrail: an "ask" endpoint that Caddy calls before requesting a cert, so you can check the domain against your own records (e.g., "does this match a customer account?") and approve or deny it. There's no way to enable on-demand TLS without also configuring this restriction.

## Testing without burning rate limits

Let's Encrypt's production rate limits are not generous, and hitting them can leave you unable to get real certificates for hours or days. While iterating on config, point the ACME issuer at the staging endpoint instead:

```
https://acme-staging-v02.api.letsencrypt.org/directory
```

Staging certs aren't trusted by browsers, but they let you validate that the whole issuance flow works before switching back to production.

## When something goes wrong

Certificate management runs in the background by default, so a hiccup here doesn't block startup or take a site down — it just means that site might not have a valid cert yet. Caddy's retry sequence on failure looks roughly like:

1. Retry once immediately, in case it was transient
2. Try the next enabled challenge type
3. Once all challenge types are exhausted, fall back to the next configured CA
4. Once all CAs are exhausted, back off exponentially, up to once a day, for up to 30 days

By default Caddy has two CAs configured — Let's Encrypt and ZeroSSL — and will fail over between them automatically. During retries against Let's Encrypt specifically, Caddy switches to their staging environment to avoid making a bad rate-limit situation worse.

There's also an internal cap (currently 10 attempts per ACME account per 10 seconds) so that pointing Caddy at a config with thousands of domains doesn't hammer the CA — it'll work through the list steadily rather than all at once. One side effect worth knowing: changing the config aborts any in-flight ACME transactions, so if you're bootstrapping a lot of certificates at once, batch your config changes rather than reloading repeatedly.

## Where certificates and keys live

Everything — certificates, private keys, ACME account info — goes into Caddy's configured storage backend, which defaults to the filesystem under `$HOME`. That directory needs to be writable and, importantly, *persistent*; if it gets wiped on every restart, Caddy will look like it's re-provisioning certificates constantly (and may hit rate limits doing so). Before attempting any ACME work, Caddy sanity-checks that storage is writable and has room.

If multiple Caddy instances point at the same storage backend, they automatically coordinate as a cluster rather than racing each other for the same certificate.

## Wildcard certificates

A wildcard cert covers `*.example.com`-style names, but only when the wildcard is the leftmost label — `sub.*.example.com` or `*.*.example.com` don't qualify, since that's a constraint of the public CA system, not something Caddy can work around.

In the Caddyfile, site names are taken literally: a site block for `*.example.com` gets a wildcard cert, one for `sub.example.com` gets a cert just for that name — they're two different requests, not the same wildcard cert reused. Since Caddy 2.10, if you do have a wildcard cert covering a subdomain, Caddy will reuse it for that subdomain rather than separately requesting an individual certificate for it.

Wildcards are convenient at scale but come with a tradeoff worth knowing: a single wildcard key covers every subdomain under it, so a leaked key exposes everything at once, and by themselves wildcards don't hide *which* subdomains exist — the actual hostname still appears in the TLS handshake unless you're also using Encrypted ClientHello.

## Hiding the hostname itself: Encrypted ClientHello (ECH)

Normally the domain name you're connecting to (the SNI) is sent in plaintext during the TLS handshake, which is enough for a network observer to see what site you're visiting even though the rest of the traffic is encrypted. ECH closes that gap by wrapping the real ("inner") ClientHello inside a decoy ("outer") one that uses a public, shared name instead of your real domain.

Caddy can generate, publish, and rotate ECH configurations on its own — it publishes the necessary parameters as an HTTPS-type DNS record, which requires a `caddy-dns` provider plugin so Caddy can write that record for you. A minimal Caddyfile setup looks like:

```caddy
{
	dns <provider config...>
	ech example.com
}
```

Here `example.com` is the *public name* — an "outer" identity that your server must also hold a real certificate for, since it's used as a fallback SNI when a client can't yet decrypt the real one (say, because it hasn't picked up a rotated key yet). Getting real privacy benefit out of ECH isn't just a config flag, though — a few things matter in practice:

- Your DNS records need to already exist for a domain before Caddy will publish an HTTPS/ECH record for it, and it won't publish one if the domain has a CNAME.
- Clients only get the benefit if they resolve DNS securely (DoH/DoT) — plaintext DNS lookups leak the same information ECH is trying to protect.
- Privacy scales with your *anonymity set*: the more sites sharing the same public name, the harder it is for an observer to distinguish between them. Using a different public name per domain defeats the purpose.
- If you also care about hiding which subdomains exist (not just the base domain), pair ECH with a wildcard certificate and be mindful that DNSSEC zone walking can leak subdomains through NSEC records regardless.

Verifying it works currently means reaching for Wireshark and checking that the ServerName field in the ClientHello shows your public name rather than the real one — tooling here is still thin, and it's normal to see an `encrypted_client_hello` extension on connections that aren't really using ECH (most modern browsers send a decoy one, "GREASE," even when talking to servers that don't support it at all).
