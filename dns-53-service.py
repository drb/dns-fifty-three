#import boto
#from boto.route53.record import ResourceRecordSets
#conn = boto.connect_route53()
#changes = ResourceRecordSets(conn, "ZXXXXXXXXXXXXXX")
#change = changes.add_change("CREATE", boto.config.get("dns", "name"),"CNAME")
#change.add_value(boto.config.get("Instance", "public-hostname"))
#changes.commit()

import sys
import os
import yaml
import sched
import time
import boto
from daemon import Daemon

checkConfig = {}
checkConfig['interval'] = 5;

class Dns53(Daemon):

	conf = {}
	plugins = None
	s = sched.scheduler(time.time, time.sleep)

	def __init__(self, pid):
		# load the config
		stream = open("53.yaml", 'r')
		self.conf = yaml.safe_load(stream)
		stream.close()

		# cache the check plugins
		self.loadCheckPlugins(self.conf['pluginDir'])

	# loads the check files into memory
	def loadCheckPlugins(self, pluginsPath):

		if pluginsPath != '':

			if os.access(pluginsPath, os.R_OK) == False:
				print 'Plugin path is set but not readable by agent. Skipping plugins.'
				return False

		else:
			return False

		# Have we already imported the plugins?
		# Only load the plugins once
		if self.plugins == None:

			sys.path.append(pluginsPath)

			self.plugins = []
			plugins = []

			# Loop through all the plugin files
			for root, dirs, files in os.walk(pluginsPath):
				for name in files:

					name = name.split('.', 1)

					# Only pull in .py files (ignores others, inc .pyc files)
					try:
						if name[1] == 'py':

							plugins.append(name[0])

					except IndexError, e:

						continue

			# Loop through all the found plugins, import them then create new objects
			for pluginName in plugins:
				
				pluginPath = os.path.join(pluginsPath, '%s.py' % pluginName)

				if os.access(pluginsPath, os.R_OK) == False:
					print 'Unable to read dir so skipping this plugin.', pluginsPath
					continue

				try:
					# Import the plugin, but only from the pluginDirectory (ensures no conflicts with other module names elsehwhere in the sys.path
					import imp
					importedPlugin = imp.load_source(pluginName, pluginPath)

					# Find out the class name and then instantiate it
					pluginClass = getattr(importedPlugin, pluginName)

					try:
						pluginObj = pluginClass()

					except TypeError:

						print TypeError

					# Store in class var so we can execute it again on the next cycle
					self.plugins.append(pluginObj)

				except Exception, ex:
					import traceback

		# Now execute the objects previously created
		if self.plugins != None:

			# Execute the plugins
			output = {}

			for plugin in self.plugins:

				try:
					output[plugin.__class__.__name__] = plugin.run()

				except Exception, ex:
					import traceback

				print output
				#self.mainLogger.debug('getPlugins: %s output: %s', plugin.__class__.__name__, output[plugin.__class__.__name__])
				#self.mainLogger.info('getPlugins: executed %s', plugin.__class__.__name__)

			#self.mainLogger.debug('getPlugins: returning')

			# Each plugin should output a dictionary so we can convert it to JSON later
			return output

		else:
			print 'getPlugins: no plugins, returning false'

			return False


	def setNextCheck(self):
		self.s.enter(checkConfig['interval'], 1, self.doChecks, (self.s, "a message"))

	def run(self):
		self.setNextCheck();
		self.s.run()

	# Does the checks against the prerequisites
	def doChecks(self, sched, msg):
		print 'Doing checks', self.conf['zoneId']
		self.setNextCheck()

check = Dns53('/dev/null/pid.pid')
check.run()