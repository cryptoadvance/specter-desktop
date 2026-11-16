# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 2.3.x   | ✅        |
| < 2.3   | ❌        |

Only the latest release receives security fixes. Older releases are not
patched; please reproduce issues on the current version before reporting.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting on this repository:

1. Go to <https://github.com/cryptoadvance/specter-desktop/security/advisories/new>
2. Describe the problem, including the affected version, your operating system,
   the hardware wallet model and firmware involved, and the steps to reproduce.
3. Attach a proof of concept or script if you have one.

The report stays private to the maintainers until an advisory is published.
GitHub also lets us request a CVE through the same advisory.

If you cannot use GitHub, open an issue that contains **no details** and only
asks for a private contact channel.

### What helps

- Exact version and installation method (release binary, pip, source checkout)
- Whether the hardware wallet was connected, and its model/firmware
- Logs with secrets removed — never send seeds, xprvs, descriptors of funded
  wallets, or screenshots that show them
- A minimal reproduction rather than a full wallet setup

### Please do not

- Test against wallets holding real funds. Use testnet or a throwaway seed.
- Post details in public issues, pull requests, social media, or our Telegram
  support group (<https://t.me/spectersupport>) before a fix is released.

## What to expect

- We aim to acknowledge a report within three business days.
- We confirm the issue, agree on a disclosure timeline with you, and prepare a
  fix plus a GitHub security advisory.
- We credit reporters in the advisory unless you ask us not to.

## Scope

In scope:

- The Specter Desktop application, including its server and UI
- The hardware wallet bridge (HWI integration) and device communication
- Build, packaging and update mechanisms shipped with releases
- Interactions with Specter DIY firmware

Out of scope:

- Vulnerabilities in third-party hardware wallets or their firmware
  (report those to the respective vendor)
- Issues that require an already compromised machine, physical access to the
  device, or social engineering of the user
- Missing hardening headers or best-practice findings without a concrete impact

## Safe harbor

We welcome good-faith research. We will not pursue legal action against
researchers who follow this policy, avoid privacy violations and data
destruction, and give us reasonable time to fix the issue before disclosure.
