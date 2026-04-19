# SERVER_RUNTIME

Last Updated: 2026-04-19
Owner: PM / Planner / Server Maintainer

## Canonical Live Host

The canonical live runtime host is **old Air**.

This machine is the source of truth for:

- Telegram bot
- Flask web dashboard
- Cloudflare Tunnel
- live recommendation behavior
- runtime logs

The main machine is **not** the live runtime source of truth. It is primarily used for:

- development
- planning
- quant research
- heavy backtests

If live behavior differs from local behavior on the main machine, trust old Air first.

## Compute vs Runtime

Default rule:

- old Air is the canonical live runtime host
- the main machine is the default compute host for heavy jobs

Heavy jobs include:

- full backtests
- research view generation
- matrix / audit / bootstrap style runs
- long-running research artifact generation

Operational policy:

- heavy compute should run on the main machine
- generated artifacts should then be copied or deployed to old Air if needed by live web
- old Air should not be the default machine for heavy backtest or research artifact generation unless explicitly required
- if a live page depends on a heavy generated artifact, the artifact should be refreshed on the main machine first, then published to old Air

## Managed Services

Old Air runs these `launchd` services:

- `com.spxstrat.bot`
- `com.spxstrat.web`
- `com.spxstrat.cloudflared`
- `com.spxstrat.cloudflared-b`

Expected responsibilities:

- `bot`: Telegram polling, scheduled push, intraday monitoring
- `web`: local Flask dashboard on `127.0.0.1:5050`
- `cloudflared`: primary public ingress connector from Cloudflare to local web
- `cloudflared-b`: secondary connector for the same tunnel on the same host

## Key Paths On Old Air

- Project: `/Users/macbook/SPX_strat`
- LaunchAgents: `/Users/macbook/Library/LaunchAgents`
- Bot/Web logs: `/Users/macbook/Library/Logs/spx-strat`
- Cloudflared logs: `/Users/macbook/Library/Logs/cloudflared`
- Cloudflare config: `/Users/macbook/.cloudflared/config.yml`
- Secondary connector config: `/Users/macbook/.cloudflared/config-connector-b.yml`

## Access

For all agents and humans, the preferred way to access old Air is **SSH alias access**. This is the most convenient and lowest-token way to work with the live host because it avoids re-explaining connection details in every prompt.

Recommended local SSH config on the main machine:

```sshconfig
Host oldair
  HostName 192.168.68.117
  User macbook
```

Verified on 2026-04-18:

- `ssh -G oldair` resolves to `hostname 192.168.68.117`
- `ifconfig` on old Air reports `inet 192.168.68.117`
- `tailscale ip -4` on old Air reports `100.114.226.33`

Recommended access model:

- When on the same local network, using the LAN IP is fine:
  - `192.168.68.117`
- When away from home or when LAN routing is inconvenient, prefer the Tailscale IPv4:
  - `100.114.226.33`
- Keep using the `oldair` SSH alias as the human-friendly entry point; update the alias target as needed for the current network path

Optional SSH config variant for Tailscale access:

```sshconfig
Host oldair
  HostName 100.114.226.33
  User macbook
```

After this is set, use:

```bash
ssh oldair
```

Use old Air SSH access for:

- runtime health checks
- log inspection
- service restart
- reading canonical live files and cache

Do not treat old Air as the default development machine; use it primarily as the canonical live runtime host.

Operational rule:

- A separate always-on server maintainer agent is not required by default
- When a task involves old Air, the current role may SSH into old Air and perform the needed work directly
- All operations on old Air must follow both `SERVER_RUNTIME.md` and `doc/old_air_server_maintainer.md`

## Runtime Read Paths

Use these when an agent or researcher needs live state from old Air:

- current recommendation: `/api/recommendation`
- current position: `/api/position`
- live performance: `/api/performance/live`
- trade log: `/api/trade-log`
- backtest latest cache: `/api/backtest/latest-cached`
- backtest cache file: `data/backtest_results_cache.json`

## Common Commands

### Status

```bash
launchctl print gui/$(id -u)/com.spxstrat.bot | sed -n '1,40p'
launchctl print gui/$(id -u)/com.spxstrat.web | sed -n '1,40p'
launchctl print gui/$(id -u)/com.spxstrat.cloudflared | sed -n '1,60p'
launchctl print gui/$(id -u)/com.spxstrat.cloudflared-b | sed -n '1,60p'
```

### Restart

```bash
launchctl kickstart -k gui/$(id -u)/com.spxstrat.bot
launchctl kickstart -k gui/$(id -u)/com.spxstrat.web
launchctl kickstart -k gui/$(id -u)/com.spxstrat.cloudflared
launchctl kickstart -k gui/$(id -u)/com.spxstrat.cloudflared-b
```

### Logs

```bash
tail -f /Users/macbook/Library/Logs/spx-strat/bot.err.log
tail -f /Users/macbook/Library/Logs/spx-strat/web.err.log
tail -f /Users/macbook/Library/Logs/cloudflared/err.log
tail -f /Users/macbook/Library/Logs/cloudflared/err-b.log
```

### Local Health

```bash
curl -I http://127.0.0.1:5050
ps aux | grep cloudflared
```

## Access Model

- Public web is served through Cloudflare Tunnel
- Local Flask app listens on `127.0.0.1:5050`
- Tunnel config currently lives on old Air at `/Users/macbook/.cloudflared/config.yml`
- Current ingress target is `http://127.0.0.1:5050`
- `spx-strat` is currently a **locally configured tunnel**; do not click dashboard migration casually because it is irreversible
- Current mitigation for intermittent `502` is a same-host dual-connector layout:
  - primary connector: `com.spxstrat.cloudflared`
  - secondary connector: `com.spxstrat.cloudflared-b`
- Current connector tuning on old Air:
  - `protocol: http2`
  - dedicated metrics endpoints
    - primary: `127.0.0.1:60123`
    - secondary: `127.0.0.1:60124`
- This improves connector-level redundancy, but it is **not** full host-level HA because both connectors still share the same old Air host

If public web fails with `502`:

1. check local Flask health
2. check both `com.spxstrat.cloudflared` and `com.spxstrat.cloudflared-b`
3. inspect `cloudflared` logs
4. verify `/Users/macbook/.cloudflared/config.yml` still points `www.portimperialventures.com` to `http://127.0.0.1:5050`
5. if local Flask and local tunnel metrics are healthy but Access login still ends in `502`, suspect Cloudflare-side Access / tunnel edge behavior before changing old Air again
6. use the local-first health script before restarting connectors:

```bash
bash scripts/check_oldair_cloudflared.sh
bash scripts/check_oldair_cloudflared.sh --heal
```

## Coordination Rules

- Quant Researcher should use old Air when the task depends on live recommendation history or current runtime behavior
- Planner should treat old Air as the canonical runtime when summarizing deployment or operational state
- Developer should not assume the main machine represents production runtime
- Server Maintainer owns runtime diagnostics and low-risk operational recovery on old Air

## Related Docs

- `AGENTS.md`
- `PROJECT_STATUS.md`
- `PROMPTS.md`
- `doc/old_air_server_maintainer.md`
