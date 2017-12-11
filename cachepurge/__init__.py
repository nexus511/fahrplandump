import logging
import os
import pycurl
from cStringIO import StringIO

class CachePurger(object):
    '''
    Helper class to pruge webcaches.
    '''
    
    def __init__(self, config):
        '''
        Constructor.
        
        @param config: The configuration.
        @type config: configuration.Config
        '''
        self.__config = config
        self.__log = logging.getLogger("CachePurger")
        self.__curl = pycurl.Curl()
    
    def purge(self, conference):
        '''
        Purges the webcache for the given conference.
        
        @param conference: Name of the conference to purge.
        '''
        self.__log.debug("try purging %s" % (conference))
        
        location = self.__config.getConferenceLocation(conference)
        baseUrl = self.__config.getConferenceWeb(conference)

        urls = self.__getPurgeUrls(location, baseUrl)
        self.__purgeAll(urls)
    
    def __getPurgeUrls(self, location, baseUrl):
        '''
        Retrieves the list of URLs ato be purged.
        '''
        urls = []
        for proto in [None, 'https']:
            urls.append((baseUrl, proto))
            urls.append((baseUrl + "/", proto))
            
            for basedir, folders, files in os.walk(location):
                basedir = basedir[len(location) + 1:]
                for file in files:
                    urls.append(("%s/%s/%s" % (baseUrl, basedir, file), proto))

                for folder in folders:
                    urls.append(("%s/%s/%s" % (baseUrl, basedir, folder), proto))
                    urls.append(("%s/%s/%s/" % (baseUrl, basedir, folder), proto))
        return urls
    
    def __purgeAll(self, urls):
        '''
        Purges all URLs in the list.
        '''
        for cache in self.__config.getCaches():
            for url, proto in urls:
                self.__purge(url, cache, proto)
    
    def __purge(self, url, cache, proto = None):
        '''
        Purges the given site for the given proto.
        '''
        self.__log.debug("purge %s" % (url))
        headers = []
        buffer = StringIO()
        c = self.__curl
        c.setopt(c.URL, url.encode("utf-8"))
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(c.HEADERFUNCTION, headers.append)
        c.setopt(c.CUSTOMREQUEST, "PURGE")
        resolve = [ "%s:%s:%s" % (self.__config.getWebHost(), cache["port"], cache["address"]), ]
        c.setopt(c.RESOLVE, resolve)
        if proto != None:
            c.setopt(c.HTTPHEADER, ['X-Forwarded-Proto: https'])
        c.perform()
        self.__log.debug("%s: PURGE %s" % (headers[0].strip()[9:], url))
