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
checkConfig['interval'] = 1800 # call every 10 minutes;

class Dns53(Daemon):

	conf = {}
	plugins = None
	s = sched.scheduler(time.time, time.sleep)

	def __init__(self, pid):

		print '[log] Daemon loaded'

		# load the config
		stream = open("config.yaml", 'r')
		self.conf = yaml.safe_load(stream)
		stream.close()

		# cache the check plugins
		self.loadCheckPlugins(self.conf['pluginDir'])

	# loads the check files into memory
	def loadCheckPlugins(self, plugins_root_path):

		if plugins_root_path != '':

			if os.access(plugins_root_path, os.R_OK) == False:
				print '[log] Check plugin path is not readable'
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

					print '[log] Unable to read dir so skipping this plugin.', plugins_root_path
					continue

				try:
					# import the check plugin
					import imp
					importedPlugin = imp.load_source(plugin_name, plugin_path)

					# attempt to create an instance of the plugin
					pluginClass = getattr(importedPlugin, plugin_name)

					try:
						pluginObj = pluginClass(self.conf['pluginDir'], self.conf)

					except TypeError:

						print TypeError

					# store this in the class, the plugins will be cycled on the next pass
					self.plugins.append(pluginObj)

				except Exception, ex:
					print '[error] Error loading check plugin', ex

		# execute all cached plugins
		if self.plugins != None:

			# stores the output - True indicate a check pass, and all checks must pass for the DNS update to occur
			output = {}

			for plugin in self.plugins:

				try:
					output[plugin.__class__.__name__] = plugin.run()

				except Exception, ex:
					print '[error] Error running plugin', ex

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

			print '[check]', plugin_name, result

			if result == False:
				checks_passed = False

		if checks_passed:

			# @todo 

			f = urllib2.urlopen(self.conf['ipResolver']).read()
			j = json.loads(f)

			ip = j['client_ip']
			host_name = self.conf['recordName']

			current_record = None

			# @todo check if yaml keys exist, otherwise default to ENV variables or fail
			conn = boto.connect_route53(self.conf['awsKey'], self.conf['awsSecret'])

			# dict of all entries for this zone
			existing_entries = conn.get_all_rrsets(self.conf['zoneId'])

			# find the target cname in the entries
			for x in existing_entries:
				host_name_period = host_name
				if host_name[-1] != '.':
					host_name_period = host_name_period + '.'

				if x.name == host_name_period:
					current_record = x
					break
				else:
					x = None

			# a matching record was found, so test it against the IP we retrieved form the webservice and check if it needs an update
			if x != None:

				# array of ips against the dns entry
				if ip in current_record.resource_records:
					print '[log] No changes required'
				else:
					print '[log] Need to update', ', '.join(current_record.resource_records), 'to', ip

					changes = ResourceRecordSets(conn, self.conf['zoneId'])

					# rmeove the old record first (passing in the existing ip, otherwise this won't work)
					change = changes.add_change("DELETE", host_name, "A")
					change.add_value(','.join(current_record.resource_records))
					
					# now recreate the record with the new ip
					change = changes.add_change("CREATE", host_name, "A")
					change.add_value(ip)

					try:
						#check the result
						result = changes.commit()
					except Exception, e:
						print '[error]', e

			# if it needs to be created, do it now
			else:
				print host_name, '[log] Record needs to be created for', host_name

				changes = ResourceRecordSets(conn, self.conf['zoneId'])

				change = changes.add_change("CREATE", host_name, "A")
				change.add_value(ip)
				result = changes.commit()

		# schedule the next check
		self.setNextCheck()

check = Dns53('/dev/null/pid.pid')
check.run()