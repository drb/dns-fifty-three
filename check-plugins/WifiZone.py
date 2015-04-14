import yaml

import subprocess
import os
import platform

import logging

# Sample data returned from the OSX Airport wifi check
#
# agrCtlRSSI: -47
# agrExtRSSI: 0
# agrCtlNoise: -88
# agrExtNoise: 0
# state: running
# op mode: station
# lastTxRate: 145
# maxRate: 144
# lastAssocStatus: 0
# 802.11 auth: open
# link auth: wpa2-psk
# BSSID: 0:1d:aa:a2:13:30
# SSID: HAL

# Checks the local connection's SSID
class WifiZone ():

	conf = {}

	def __init__(self, plugin_dir, conf):

		self.conf = conf

		# the check plugin's naming convention shuold be __class__.__name__ . yaml i.e. WifiZone.yaml
		config_path = plugin_dir + '/' + self.__class__.__name__ + '.yaml'

		# if the path exists, merge the yaml contents with the global config
		if os.access("./", os.R_OK) != False and os.path.exists(config_path):

			# load the plugin config
			stream = open(config_path, 'r')
			conf = yaml.safe_load(stream)
			stream.close()

			# merge plugin config with main process		
			self.conf = dict(self.conf.items() + conf.items())

			logging.basicConfig(filename=self.conf['debugLog'], level=logging.DEBUG, format='%(asctime)s %(message)s')
			logging.debug('[check_plugin_load] %s loaded', self.__class__.__name__)

	def run(self):

		if 'AlwaysPass' in self.conf:
			if self.conf['AlwaysPass'] == True:
				logging.debug('[check_plugin_bypass] %s bypassed!', self.__class__.__name__)
				return True

		output = False

		os_name = os.name
		platform_system = platform.system()
		platform_release = platform.release()

		# OSX Check
		if 'Darwin' == platform_system:

			ls_output = subprocess.check_output(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/A/Resources/airport', '-I'])

			# todo have checks from other systems
			tokens = ls_output.split('\n')

			for token in tokens:

				parts = token.strip()

				if len(parts) > 0:

					try:
						key, value = parts.split(':', 1)
					except Exception, ex:
						logging.debug('[error] %s', ex)
									
					# check the name of the SSID against the one in the config
					# todo make this check all keys in the config if they're there
					if key.strip().lower() == 'ssid':
						value = str(value).strip()
						if str(value) == self.conf['SSID']:
							output = True
		else:
			logging.debug('[warning] %s does not have a method implemented to extract wifi zone yet.', self.__class__.__name__)

		return output