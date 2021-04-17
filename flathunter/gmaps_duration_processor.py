"""Calculate Google-Maps distances between specific locations and the target flat"""
import logging
import datetime
import time
import urllib
import requests

from flathunter.abstract_processor import Processor

class GMapsDurationProcessor(Processor):
    """Implementation of Processor class to calculate travel durations"""

    GM_MODE_TRANSIT = 'transit'
    GM_MODE_BICYCLE = 'bicycling'
    GM_MODE_DRIVING = 'driving'

    __log__ = logging.getLogger('flathunt')

    def __init__(self, config):
        self.config = config

    def process_expose(self, expose):
        """Calculate the durations for an expose"""
        expose['durations'] = self.get_formatted_durations(expose['address']).strip()
        return expose

    def get_formatted_durations(self, address):
        """Return a formatted list of GoogleMaps durations"""
        out = ""
        for duration in self.config.get('durations', list()):
            if 'destination' in duration and 'name' in duration:
                dest = duration.get('destination')
                name = duration.get('name')
                for mode in duration.get('modes', list()):
                    if 'gm_id' in mode and 'title' in mode \
                                       and 'key' in self.config.get('google_maps_api', dict()):
                        duration = self.get_gmaps_distance(address, dest, mode['gm_id'])
                        out += "%s: %s\n" % (name, duration)

        return out.strip()

    def get_gmaps_distance(self, address, dest, mode):
        """Get the distance"""
        # get timestamp for next monday at 9:00:00 o'clock
        now = datetime.datetime.today().replace(hour=9, minute=0, second=0)
        next_monday = now + datetime.timedelta(days=(7 - now.weekday()))
        arrival_time = str(int(time.mktime(next_monday.timetuple())))

        # decode from unicode and url encode addresses
        address = urllib.parse.quote_plus(address.strip().encode('utf8'))
        dest = urllib.parse.quote_plus(dest.strip().encode('utf8'))
        self.__log__.debug("Got address: %s", address)

        # get google maps config stuff
        base_url = self.config.get('google_maps_api', dict()).get('url')
        gm_key = self.config.get('google_maps_api', dict()).get('key')

        if not gm_key and mode != self.GM_MODE_DRIVING:
            self.__log__.warning("No Google Maps API key configured and without using a mode "
                                 "different from 'driving' is not allowed. "
                                 "Downgrading to mode 'drinving' thus. ")
            mode = 'driving'
            base_url = base_url.replace('&key={key}', '')

        # retrieve the result
        url = base_url.format(dest=dest, mode=mode, origin=address,
                              key=gm_key, arrival=arrival_time)
        result = requests.get(url).json()
        if result['status'] != 'OK':
            self.__log__.error("Failed retrieving distance to address %s: %s", address, result)
            return None

        # get the fastest route
        distances = dict()
        for row in result['rows']:
            for element in row['elements']:
                if 'status' in element and element['status'] != 'OK':
                    self.__log__.warning("For address %s we got the status message: %s",
                                         address, element['status'])
                    self.__log__.debug("We got this result: %s", repr(result))
                    continue
                self.__log__.debug("Got distance and duration: %s / %s (%i seconds)",
                                   element['distance']['text'],
                                   element['duration']['text'],
                                   element['duration']['value'])
                distances[element['duration']['value']] = '%s (%s)' % \
                                                          (element['duration']['text'],
                                                           element['distance']['text'])
        return distances[min(distances.keys())] if distances else None
