from enigma import eTimer

from config import config, ConfigSelection, ConfigSubsection
from os import environ, unlink, symlink, walk, path
import time

def InitTimeZones():
	config.timezone = ConfigSubsection()
	config.timezone.area = ConfigSelection(default = "Europe", choices = timezones.getTimezoneAreaList())
	def timezoneAreaChoices(configElement):
		timezones.updateTimezoneChoices(configElement.getValue(), config.timezone.val)
	config.timezone.area.addNotifier(timezoneAreaChoices, initial_call = False, immediate_feedback = True)

	config.timezone.val = ConfigSelection(default = timezones.getTimezoneDefault(), choices = timezones.getTimezoneList())
	def timezoneNotifier(configElement):
		timezones.activateTimezone(configElement.getValue(), config.timezone.area.getValue())
	config.timezone.val.addNotifier(timezoneNotifier, initial_call = True, immediate_feedback = True)
	config.timezone.val.callNotifiersOnSaveAndCancel = True

def sorttzChoices(tzchoices):
	sort_list = []
	for tzitem in tzchoices:
		if tzitem[0].startswith("GMT"):
			if len(tzitem[0][3:]) > 1 and (tzitem[0][3:4] == "-" or tzitem[0][3:4] == "+") and tzitem[0][4:].isdigit():
				sortkey = int(tzitem[0][3:])
			else:
				sortkey = 0
		else:
			sortkey = tzitem[1]
		sort_list.append((tzitem, sortkey))
	sort_list.sort(key=lambda listItem: listItem[1])
	return [i[0] for i in sort_list]

def sorttz(tzlist):
	return [i[0] for i in sorttzChoices(zip(tzlist, tzlist))]

class Timezones:
	tzbase = "/usr/share/zoneinfo"
	gen_label = "Generic"
	AT_POLL_DELAY = 3  # Minutes

	def __init__(self):
		self.timezones = {}
		self.readTimezonesFromSystem()
		try:
			from Plugins.Extensions.AutoTimer.plugin import autotimer, autopoller
			# Create attributes autotimer & autopoller for backwards compatibility.
			# Their use is deprecated.
			self.autopoller = autopoller
			self.autotimer = autotimer
		except ImportError:
			self.autopoller = None
			self.autotimer = None
		self.timer = eTimer()
		self.ATupdate = None

	def startATupdate(self):
		if self.ATupdate:
			self.timer.stop()
		if self.query not in self.timer.callback:
			self.timer.callback.append(self.query)
		print "[Timezones] AutoTimer poll will be run in", self.AT_POLL_DELAY, "minutes"
		self.timer.startLongTimer(self.AT_POLL_DELAY * 60)

	def stopATupdate(self):
		self.ATupdate = None
		if self.query in self.timer.callback:
			self.timer.callback.remove(self.query)
		self.timer.stop()

	def query(self):
		print "[Timezones] AutoTimer poll running"
		self.stopATupdate()
		try:
			from Plugins.Extensions.AutoTimer.plugin import autotimer, autopoller
			self.autopoller = autopoller
			self.autotimer = autotimer
			if autotimer is not None:
				print "[Timezones] AutoTimer parseEPG"
				autotimer.parseEPG(autoPoll=True)
			if autopoller is not None:
				autopoller.start()
		except ImportError, KeyError:
			pass

	def readTimezonesFromSystem(self):
		tzfiles = [];
		for (root, dirs, files) in walk(Timezones.tzbase):
			root = root[len(Timezones.tzbase):]
			if root == "":
				root = "/" + Timezones.gen_label
			for f in files:
				if f[-4:] == '.tab' or f[-2:] == '-0' or f[-2:] == '+0': # no need for '.tab', -0, +0
					files.remove(f)

			for f in files:
				fp = "%s/%s" % (root, f)
				fp = fp[1:]	# Remove leading "/"
				(section, zone) = fp.split("/", 1)
				if not section in self.timezones:
					self.timezones[section] = []
				self.timezones[section].append(zone)

			if len(self.timezones) == 0:
				self.timezones[Timezones.gen_label] = ['UTC']

	# Return all Area options
	def getTimezoneAreaList(self):
		return sorted(self.timezones.keys())

	userFriendlyTZNames = {
		"Asia/Ho_Chi_Minh": _("Ho Chi Minh City"),
		"Australia/LHI": None, # Exclude
		"Australia/Lord_Howe": _("Lord Howe Island"),
		"Australia/North": _("Northern Territory"),
		"Australia/South": _("South Australia"),
		"Australia/West": _("Western Australia"),
		"Brazil/DeNoronha": _("Fernando de Noronha"),
		"Pacific/Chatham": _("Chatham Islands"),
		"Pacific/Easter": _("Easter Island"),
		"Pacific/Galapagos": _("Galapagos Islands"),
		"Pacific/Gambier": _("Gambier Islands"),
		"Pacific/Johnston": _("Johnston Atoll"),
		"Pacific/Marquesas": _("Marquesas Islands"),
		"Pacific/Midway": _("Midway Islands"),
		"Pacific/Norfolk": _("Norfolk Island"),
		"Pacific/Pitcairn": _("Pitcairn Islands"),
		"Pacific/Wake": _("Wake Island"),
	}

	@staticmethod
	def getUserFriendlyTZName(area, tzname):
		return Timezones.userFriendlyTZNames.get(area + '/' + tzname, tzname.replace('_', ' '))

	# Return all zone entries for an Area, sorted.
	def getTimezoneList(self, area=None):
		if area == None:
			area = config.timezone.area.getValue()
		return sorttzChoices((tzname, self.getUserFriendlyTZName(area, tzname)) for tzname in self.timezones[area] if self.getUserFriendlyTZName(area, tzname))

	default_for_area = {
		'Europe': 'London',
		'Generic': 'UTC',
	}
	def getTimezoneDefault(self, area=None, choices=None):
		if area == None:
			try:
				area = config.timezone.area.getValue()
			except:
				print "[Timezones] getTimezoneDefault, no area found, using Europe"
				area = "Europe"
		if choices == None:
			choices = self.getTimezoneList(area=area)
		return Timezones.default_for_area.setdefault(area, choices[0][0])

	def updateTimezoneChoices(self, area, zone_field):
		choices = self.getTimezoneList(area=area)
		default = self.getTimezoneDefault(area=area, choices=choices)
		zone_field.setChoices(choices = choices, default = default)
		return

	def activateTimezone(self, tz, tzarea):
		try:
			from Plugins.Extensions.AutoTimer.plugin import autotimer, autopoller
			self.autopoller = autopoller
			self.autotimer = autotimer
			if config.plugins.autotimer.autopoll.value:
				print "[Timezones] trying to stop main AutoTimer poller"
				if autopoller is not None:
					autopoller.stop()
				self.ATupdate = True
		except ImportError, KeyError:
			pass

		if tzarea == Timezones.gen_label:
			fulltz = tz
		else:
			fulltz = "%s/%s" % (tzarea, tz)

		tzneed = "%s/%s" % (Timezones.tzbase, fulltz)
		if not path.isfile(tzneed):
			print "[Timezones] Attempt to set timezone", fulltz, "ignored. UTC used"
			fulltz = "UTC"
			tzneed = "%s/%s" % (Timezones.tzbase, fulltz)

		print "[Timezones] setting timezone to", fulltz
		environ['TZ'] = fulltz
		try:
			unlink("/etc/localtime")
		except OSError:
			pass
		try:
			symlink(tzneed, "/etc/localtime")
		except OSError:
			pass
		try:
			time.tzset()
		except:
			from enigma import e_tzset
			e_tzset()
		try:
			from Plugins.Extensions.AutoTimer.plugin import autotimer, autopoller
			self.autopoller = autopoller
			self.autotimer = autotimer
			if config.plugins.autotimer.autopoll.value:
				self.startATupdate()
		except ImportError, KeyError:
			pass

timezones = Timezones()
