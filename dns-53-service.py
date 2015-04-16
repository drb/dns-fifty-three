#!/usr/bin/python

import sys
import os
import yaml
import sched
import time
import boto
import urllib2
import json
import logging

from boto.route53.record import ResourceRecordSets
from daemon import Daemon

checkConfig = {}
checkConfig['interval'] = (60 * 25) # call every 25 minutes

# load the config
stream = open("config.yaml", 'r')
conf = yaml.safe_load(stream)
stream.close()

logger = logging.getLogger('dns53.root')
logger.setLevel(logging.DEBUG)
logFormat = logging.Formatter("%(asctime)s - %(message)s")

fileHandler = logging.FileHandler(conf['debugLog'])
fileHandler.setFormatter(logFormat)
fileHandler.setLevel(logging.DEBUG)
logger.addHandler(fileHandler)


class Dns53(Daemon):

	conf = {}
	plugins = None
	s = sched.scheduler(time.time, time.sleep)

	def setup(self):
		logger.debug('[log] Daemon loaded')

		# load the config
		self.conf = conf

		# cache the check plugins
		self.loadCheckPlugins(self.conf['pluginDir'])

	# loads the check files into memory
	def loadCheckPlugins(self, plugins_root_path):

		if plugins_root_path != '':

			if os.access(plugins_root_path, os.R_OK) == False:
				logger.debug('[log] Check plugin path is not readable')
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

					logger.debug('[log] Unable to read dir so skipping this plugin. %s', plugins_root_path)
					continue

				try:
					# import the check plugin
					import imp
					importedPlugin = imp.load_source(plugin_name, plugin_path)

					# attempt to create an instance of the plugin
					pluginClass = getattr(importedPlugin, plugin_name)

					try:
						#pass in configuration object and logger
						pluginObj = pluginClass(self.conf['pluginDir'], self.conf, logger)
					except TypeError:
						logger.debug(TypeError)

					# store this in the class, the plugins will be cycled on the next pass
					self.plugins.append(pluginObj)

				except Exception, ex:
					logger.debug('[error] Error loading check plugin %s', ex)

		# execute all cached plugins
		if self.plugins != None:

			# stores the output - True indicate a check pass, and all checks must pass for the DNS update to occur
			output = {}

			for plugin in self.plugins:

				try:
					output[plugin.__class__.__name__] = plugin.run()

				except Exception, ex:
					logger.debug('[error] Error running plugin %s', ex)

			# Each plugin needs to return True to fire the DNS update request
			return output

		else:

			return False


	# Schedules the next check
	def setNextCheck(self):
		self.s.enter(checkConfig['interval'], 1, self.doChecks, (self.s, ""))

	# daemon entry
	def run(self):
		self.setup()
		self.doChecks(self.s, "")
		self.s.run()

	# Does the checks against the prerequisites
	def doChecks(self, sched, msg):

		checks_passed = True

		plugin_checks = self.loadCheckPlugins(self.conf['pluginDir'])

		for plugin_name, result in plugin_checks.items():

			logger.debug('[check] %s %s', plugin_name, result)

			if result == False:
				checks_passed = False

		if checks_passed:

			f = urllib2.urlopen(self.conf['ipResolver'] + '?zoneId=' + self.conf['zoneId']).read()
			j = json.loads(f)

			existing_entries = None
			x = None
			ip = j['client_ip']
			host_name = self.conf['recordName']

			current_record = None

			# ENV - AWS_ACCESS_KEY_ID
			# ENV - AWS_SECRET_ACCESS_KEY

			# @todo check if yaml keys exist, otherwise default to ENV variables or fail
			conn = boto.connect_route53(self.conf['awsKey'], self.conf['awsSecret'])

			# dict of all entries for this zone
			try:
				existing_entries = conn.get_all_rrsets(self.conf['zoneId'])
			except Exception, e:
				logger.error('[error] %s', e)

			if existing_entries != None:
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
					logger.debug('[log] No changes required')
				else:
					logger.debug('[log] Need to update %s to %s', ','.join(current_record.resource_records), ip)

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
						logger.debug('[error] %s', e)

			# if it needs to be created, do it now
			else:
				logger.debug('[log] Record needs to be created for %s', host_name)

				changes = ResourceRecordSets(conn, self.conf['zoneId'])

				change = changes.add_change("CREATE", host_name, "A")
				change.add_value(ip)

				try:
					#check the result
					result = changes.commit()
				except Exception, e:
					logger.debug('[error] %s', e)

		# schedule the next check
		self.setNextCheck()


if __name__ == "__main__":

	# pid needs to be set in the config file
    check = Dns53(conf['pid'])

    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            check.start()
        elif 'stop' == sys.argv[1]:
            check.stop()
        elif 'restart' == sys.argv[1]:
            check.restart()
        elif 'foreground' == sys.argv[1]:
        	# when in foreground mode, output logs to stdout
			ch = logging.StreamHandler(sys.stdout)
			ch.setFormatter(logFormat)
			ch.setLevel(logging.DEBUG)
			logger.addHandler(ch)
			try:
				check.run()
			except Exception, e:
				logger.debug('[error] %s', e);
        else:
            logger.debug("Unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        logger.debug("usage: %s start|stop|restart", sys.argv[0])
        sys.exit(2)