dns-fifty-three
===============

A DynDNS-like clone using Amazon Route53, with conditional updates.

Plugins allow the DNS updates to be fired only when the conditions set by the plugin rules are true.

Currently, the only rule is to check if the machine is connected to a particular wireless SSID, as I was sick of the DynDNS agent updating my DNS records for my home IP to be wherever the hell I happened to be connected to.

And that will probably be all they ever do ;)

Pre-requisites
-------------

A YAML parser is required for the config files.

`pip install pyyaml`

BOTO is required to communicate with Route53.

`sudo pip install -U boto`

Plugin architecture
-------------------

Plugins are written in Python, and live in the directory `check-plugins`.

All plugins need to consist of a class, accepting 2 required arguments `plugin_dir`, `conf`, and 1 optional argument `logger` in the constructor. The only requisite method is `run()`, this must return a boolean True or False to indicate if the check passed.

    class TruthCheck ():
    
      conf = {}
    
      def __init__(self, plugin_dir, conf, logger):
    
            # do something
    
      def run(self):
    
            return True

#### Starting the service in the foreground

This will die with the SSH session

`python dns-53-service.py foreground`

#### Starting the service as a daemon

`python dns-53-service.py start`

#### Stopping the service

`python dns-53-service.py stop`

#### Restarting the service

`python dns-53-service.py restart`
