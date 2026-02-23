#!/usr/bin/env python3

import sys
import os
import yaml
import sched
import time
import importlib.util
import urllib.request
import logging

import boto3

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

			if not os.access(plugins_root_path, os.R_OK):
				logger.debug('[log] Check plugin path is not readable')
				return False

		else:
			return False

		# load the plugins once
		if self.plugins is None:

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

					except IndexError as e:

						continue

			# Loop through all the found plugins, import them then create new objects
			for plugin_name in plugins:

				plugin_path = os.path.join(plugins_root_path, '%s.py' % plugin_name)

				if not os.access(plugins_root_path, os.R_OK):

					logger.debug('[log] Unable to read dir so skipping this plugin. %s', plugins_root_path)
					continue

				try:
					# import the check plugin
					spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
					importedPlugin = importlib.util.module_from_spec(spec)
					spec.loader.exec_module(importedPlugin)

					# attempt to create an instance of the plugin
					pluginClass = getattr(importedPlugin, plugin_name)

					try:
						#pass in configuration object and logger
						pluginObj = pluginClass(self.conf['pluginDir'], self.conf, logger)
					except TypeError:
						logger.debug(TypeError)

					# store this in the class, the plugins will be cycled on the next pass
					self.plugins.append(pluginObj)

				except Exception as ex:
					logger.debug('[error] Error loading check plugin %s', ex)

		# execute all cached plugins
		if self.plugins is not None:

			# stores the output - True indicate a check pass, and all checks must pass for the DNS update to occur
			output = {}

			for plugin in self.plugins:

				try:
					output[plugin.__class__.__name__] = plugin.run()

				except Exception as ex:
					logger.debug('[error] Error running plugin %s', ex)

			# Each plugin needs to return True to fire the DNS update request
			return output

		else:

			return False

	def resolve_ip(self):
		"""Resolve the current public IP address.

		Tries https://ifconfig.me first, then falls back to the configured
		ipResolverFallback URL (if present).
		"""
		# Primary: ifconfig.me returns plain-text IP
		try:
			req = urllib.request.Request('https://ifconfig.me', headers={'User-Agent': 'curl/7.0'})
			ip = urllib.request.urlopen(req, timeout=10).read().decode('utf-8').strip()
			logger.debug('[log] Resolved IP via ifconfig.me: %s', ip)
			return ip
		except Exception as e:
			logger.debug('[warning] ifconfig.me failed: %s', e)

		# Fallback: custom resolver from config
		fallback_url = self.conf.get('ipResolverFallback')
		if fallback_url:
			try:
				import json
				data = urllib.request.urlopen(fallback_url, timeout=10).read().decode('utf-8')
				j = json.loads(data)
				ip = j['client_ip']
				logger.debug('[log] Resolved IP via fallback (%s): %s', fallback_url, ip)
				return ip
			except Exception as e:
				logger.debug('[error] Fallback IP resolver failed: %s', e)

		return None

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

			if not result:
				checks_passed = False

		if checks_passed:

			ip = self.resolve_ip()

			if ip is None:
				logger.error('[error] Could not resolve public IP address')
				self.setNextCheck()
				return

			host_name = self.conf['recordName']
			zone_id = self.conf['zoneId']

			# Build boto3 Route53 client
			# Uses awsKey/awsSecret from config if present, otherwise falls back
			# to environment variables / IAM roles (boto3 default credential chain)
			if self.conf.get('awsKey') and self.conf.get('awsSecret'):
				client = boto3.client(
					'route53',
					aws_access_key_id=self.conf['awsKey'],
					aws_secret_access_key=self.conf['awsSecret'],
				)
			else:
				client = boto3.client('route53')

			# Check existing records
			current_ip = None
			try:
				response = client.list_resource_record_sets(
					HostedZoneId=zone_id,
					StartRecordName=host_name,
					StartRecordType='A',
					MaxItems='1',
				)
				for record_set in response.get('ResourceRecordSets', []):
					# Normalize trailing dot for comparison
					record_name = record_set['Name'].rstrip('.')
					target_name = host_name.rstrip('.')
					if record_name == target_name and record_set['Type'] == 'A':
						records = record_set.get('ResourceRecords', [])
						if records:
							current_ip = records[0]['Value']
						break
			except Exception as e:
				logger.error('[error] %s', e)

			if current_ip == ip:
				logger.debug('[log] No changes required')
			else:
				if current_ip is not None:
					logger.debug('[log] Need to update %s to %s', current_ip, ip)
				else:
					logger.debug('[log] Record needs to be created for %s', host_name)

				try:
					client.change_resource_record_sets(
						HostedZoneId=zone_id,
						ChangeBatch={
							'Changes': [{
								'Action': 'UPSERT',
								'ResourceRecordSet': {
									'Name': host_name,
									'Type': 'A',
									'TTL': 300,
									'ResourceRecords': [{'Value': ip}],
								},
							}],
						},
					)
					logger.debug('[log] DNS record updated to %s', ip)
				except Exception as e:
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
			except Exception as e:
				logger.debug('[error] %s', e)
		else:
			logger.debug("Unknown command")
			sys.exit(2)
		sys.exit(0)
	else:
		logger.debug("usage: %s start|stop|restart", sys.argv[0])
		sys.exit(2)
