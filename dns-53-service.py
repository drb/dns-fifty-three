import sys
import os
import yaml
import sched
import time
import boto
import urllib2
import json

from boto.route53.record import ResourceRecordSets
from daemon import Daemon

checkConfig = {}
checkConfig['interval'] = 600 # call every 10 minutes;

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
	def loadCheckPlugins(self, plugins_root_path):

		if plugins_root_path != '':

			if os.access(plugins_root_path, os.R_OK) == False:
				print 'Plugin path is set but not readable by agent. Skipping plugins.'
				return False

		else:
			return False

		# load the plugins once
		if self.plugins == None:

			sys.path.append(plugins_root_path)

			self.plugins = []
			plugins = []

			# Loop through all the plugin files
			for root, dirs, files in os.walk(plugins_root_path):
				for name in files:

					name = name.split('.', 1)

					try:
						if name[1] == 'py':

							plugins.append(name[0])

					except IndexError, e:

						continue

			# Loop through all the found plugins, import them then create new objects
			for plugin_name in plugins:
				
				plugin_path = os.path.join(plugins_root_path, '%s.py' % plugin_name)

				if os.access(plugins_root_path, os.R_OK) == False:
					print 'Unable to read dir so skipping this plugin.', plugins_root_path
					continue

				try:
					# Import the plugin, but only from the pluginDirectory (ensures no conflicts with other module names elsehwhere in the sys.path
					import imp
					importedPlugin = imp.load_source(plugin_name, plugin_path)

					# Find out the class name and then instantiate it
					pluginClass = getattr(importedPlugin, plugin_name)

					try:
						pluginObj = pluginClass(self.conf)

					except TypeError:

						print TypeError

					# Store in class var so we can execute it again on the next cycle
					self.plugins.append(pluginObj)

				except Exception, ex:
					print 'Error loading check plugin', ex

		# Now execute the objects previously created
		if self.plugins != None:

			# Execute the plugins
			output = {}

			for plugin in self.plugins:

				try:
					output[plugin.__class__.__name__] = plugin.run()

				except Exception, ex:
					print 'Error running plugin', ex

				print plugin.__class__.__name__, 'output', output

			# Each plugin needs to return True to fire the DNS update request
			return output

		else:

			return False


	# Schedules the next check
	def setNextCheck(self):
		self.s.enter(checkConfig['interval'], 1, self.doChecks, (self.s, "a message"))

	# daemon entry
	def run(self):
		self.setNextCheck();
		self.s.run()

	# Does the checks against the prerequisites
	def doChecks(self, sched, msg):

		checks_passed = True

		plugin_checks = self.loadCheckPlugins(self.conf['pluginDir'])

		for plugin_name, result in plugin_checks.items():
			print plugin_name, result
			if result == False:
				checks_passed = False

		if checks_passed:

			f = urllib2.urlopen(self.conf['ipResolver']).read()
			j = json.loads(f)

			ip = j['client_ip']
			host_name = self.conf['recordName']

			current_record = None
			conn = boto.connect_route53()

			# dict of all entries for this zone
			existing_entries = conn.get_all_rrsets(self.conf['zoneId'])


			# find the target cname in the entries
			for x in existing_entries:
				host_name_period = host_name
				if host_name[-1] != '.':
					host_name_period = host_name_period + '.'

				if x.name == host_name_period:
					print "i found ", host_name, x.resource_records
					current_record = x
					break
				else:
					x = None

			# a matching record was found, so test it against the IP we retrieved form the webservice and check if it needs an update
			if x != None:

				if ip in current_record.resource_records:
					print 'no change required'
				else:
					print 'need to update', current_record.resource_records, 'to', ip

					changes = ResourceRecordSets(conn, self.conf['zoneId'])

					# rmeove the old record first (passing in the existing ip, otherwise this won't work)
					change = changes.add_change("DELETE", host_name, "A")
					change.add_value(','.join(current_record.resource_records))
					
					# now recreate the record with the new ip
					change = changes.add_change("CREATE", host_name, "A")
					change.add_value(ip)

					#check the result
					result = changes.commit()

			# if it needs to be created, do it now
			else:
				print host_name, 'record needs to be created'

				changes = ResourceRecordSets(conn, self.conf['zoneId'])

				change = changes.add_change("CREATE", host_name, "A")
				change.add_value(ip)
				result = changes.commit()

		# schedule the next check
		self.setNextCheck()

check = Dns53('/dev/null/pid.pid')
check.run()