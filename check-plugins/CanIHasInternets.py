import socket
import os
import yaml

class CanIHasInternets ():

	conf = {}

	# plugin boilerplate
	def __init__(self, plugin_dir, conf, logger=None):

		self.conf = conf
		self.logger = None

		if logger != None:
			self.logger = logger

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

			if self.logger != None:
				self.logger.debug('[check_plugin_load] %s loaded', self.__class__.__name__)


	# method tells us if we have an internet connection
	def isConnected(self):

		try:
			# see if we can resolve the host name -- tells us if there is a DNS server listening
			host = socket.gethostbyname(self.conf['CheckURL'])
			# connect to the host -- tells us if the host is actually reachable
			s = socket.create_connection((host, 80), 2)
			return True
		except Exception, e:
			print e
			pass
			return False

	def run(self):

		if 'AlwaysPass' in self.conf:
			if self.conf['AlwaysPass'] == True:
				if self.logger != None:
					self.logger.debug('[check_plugin_bypass] %s bypassed!', self.__class__.__name__)
				return True

		return self.isConnected()			