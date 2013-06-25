import subprocess

# Checks the local connection's SSID
class WifiZone ():

	#ssid = 'HAL'

    def __init__(self):

        print '__init__ from plugin', self.__class__.__name__

    def run(self):

        ls_output = subprocess.check_output(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/A/Resources/airport', '-I'])

        output = False
        tokens = ls_output.split('\n')

        for token in tokens:

        	parts = token.strip()
        	key, value = parts.split(':', 1)
        	
        	if key.strip() == 'SSID':
        		value = value.strip()
        		if value == 'HAL':
        			output = True

        return output