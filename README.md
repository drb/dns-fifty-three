# dns-fifty-three

A DynDNS-like clone using Amazon Route 53 with conditional updates.

Plugins allow DNS updates to fire only when conditions set by plugin rules are met — for example, only updating when connected to a specific Wi-Fi SSID, so your home DNS record doesn't get overwritten while you're on a coffee-shop network.

## Prerequisites

- Python 3.10+
- An AWS account with Route 53 access

Install dependencies:

```
pip install -r requirements.txt
```

## Configuration

Copy and edit `config.yaml`:

- **awsKey / awsSecret** — AWS credentials (or omit to use environment variables / IAM roles)
- **zoneId** — Route 53 hosted zone ID
- **recordName** — the A record to update (e.g. `home.example.com`)
- **pluginDir** — path to check plugins (default `./check-plugins`)
- **debugLog** — log file path
- **pid** — PID file path for daemon mode

### IP resolution

The service resolves your public IP via [ifconfig.me](https://ifconfig.me). If that fails, it falls back to an optional `ipResolverFallback` URL that returns `{"client_ip":"x.x.x.x"}`.

A standalone self-hosted IP resolver is included in `ip-resolver-service/` — see [IP Resolver Service](#ip-resolver-service) below.

## Usage

```bash
# Start as a daemon
python3 dns-53-service.py start

# Stop
python3 dns-53-service.py stop

# Restart
python3 dns-53-service.py restart

# Run in the foreground (logs to stdout)
python3 dns-53-service.py foreground
```

## Plugin architecture

Plugins live in the `check-plugins` directory. Every plugin must be a Python module containing a class whose name matches the filename, accepting `plugin_dir`, `conf`, and an optional `logger` in the constructor. The class must implement a `run()` method that returns `True` or `False`.

```python
class TruthCheck:

    def __init__(self, plugin_dir, conf, logger=None):
        self.conf = conf

    def run(self):
        return True
```

All plugins must return `True` for the DNS update to proceed.

## IP Resolver Service

`ip-resolver-service/app.py` is a lightweight Flask app you can self-host as a fallback IP resolver. It returns the caller's IP as JSON.

```bash
cd ip-resolver-service
pip install flask
flask --app app run --host 0.0.0.0 --port 5000
```

Then set `ipResolverFallback` in `config.yaml` to point at it.
