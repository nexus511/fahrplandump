import logging
import traceback
import json
import os

class Config(object):
    '''
    Class providing access to the client configuration.
    '''
    
    def __init__(self, file = "config.json"):
        '''
        Constructor.
        
        @param file: The configuration file to be loaded.
        '''
        self.__log = logging.getLogger("Config")
        self.__file = os.path.abspath(file)
        self.__valid = False

        try:
            os.chmod(self.__file, 0600)
            fp = open(self.__file, "rb")
            self.__values = json.load(fp)
            self.__checkConfig()
            self.__valid = True
            fp.close()
        except Exception, e:
            self.__log.error("failed to load configuration from %s: %s"
                             % (file, str(e)))
            self.__log.debug(traceback.format_exc())

    def isValid(self):
        '''
        True, if configuration has been read properly.
        '''
        return self.__valid

    def __checkConfig(self):
        '''
        Checks the configuration for missing values. If the config is not valid,
        an exception is raised.
        '''
        # TODO(nexus511): implement
        pass
    
    def getValues(self):
        '''
        Returns the configuration object.
        '''
        return self.__values

    def getUsername(self):
        return self.__values["frab"]["username"]
    
    def getPassword(self):
        return self.__values["frab"]["password"]
    
    def getFrabHost(self):
        return self.__values["frab"]["hostname"]
    
    def getFrabSchema(self):
        return self.__values["frab"]["schema"]
    
    def getWebHost(self):
        return self.__values["web"]["hostname"]

    def getTempDir(self):
        return os.path.abspath(self.__values["tempdir"])

    def getWebRoot(self):
        return os.path.abspath(self.__values["web"]["webroot"])
    
    def getSignInForm(self):
        return self.__values["sites"]["signInForm"]
    
    def getHtmlExportForm(self, conference):
        return self.__values["sites"]["htmlExportForm"] % (conference)
    
    def getHtmlDownload(self, conference, locale = "en"):
        return self.__values["sites"]["htmlDownload"] % (conference, locale)
    
    def getProfilePath(self):
        return self.__values["sites"]["profilePath"]

    def getSignInSubmit(self):
        return self.getSignInForm()

    def getConferenceNames(self):
        rc = []
        for entry in self.__values["conferences"]:
            rc.append(entry["acronym"])
        return rc
    
    def getConferenceLocation(self, conference):
        root = self.getWebRoot()
        for entry in self.__values["conferences"]:
            if entry["acronym"] == conference:
                return os.path.abspath(os.path.join(root, entry["location"]))
        raise Exception("conference not found")
    
    def getConferenceWeb(self, conference):
        host = self.getWebHost()
        web = self.__values["web"]
        for entry in self.__values["conferences"]:
            if entry["acronym"] == conference:
                schema = web["schema"]
                hostname = web["hostname"]
                location = entry["location"]
                return "%s://%s/%s" % (schema, hostname, location)
        raise Exception("conference not found")

    def getCaches(self):
        return self.__values["web"]["caches"]
