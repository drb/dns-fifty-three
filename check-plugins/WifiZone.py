import subprocess
import os
import platform

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
# SSID: Kaeto

# Checks the local connection's SSID
class WifiZone ():

	conf = {}
	target = 'Kaeto'

	def __init__(self, conf):

		print 'Check plugin loaded', self.__class__.__name__

		self.conf = conf

	def run(self):

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
						print ex
									
					if key.strip().lower() == 'ssid':
						value = str(value).strip()
						if str(value) == self.target:
							output = True
		else:
			print '[warning]', self.__class__.__name__, 'does not have a method implemented to extract wifi zone yet'

		return output