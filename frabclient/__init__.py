import pycurl

from cStringIO import StringIO
import logging
from lxml import etree
import time
import json

class ClientException(Exception):
    '''
    Client specific exception class.
    '''
    
    def __init__(self, msg):
        '''
        Constructor.
        
        @param msg: Error message of the exception.
        '''
        Exception.__init__(self, msg)


class CurlWrapper(object):
    '''
    Curl wrapper for frab access.
    '''
    
    def __init__(self, session):
        '''
        Constructor.
        
        @param session: The client session.
        @type session: frabclient.SessionManager
        '''
        self.__curl = pycurl.Curl()
        self.__log = logging.getLogger("CurlWrapper")
        self.__session = session
        
    def query(self, url, post = None, timeout = 0):
        '''
        Initializes the values of the new cURL request.
        
        @param url: The URL to be requested.
        @param post: If set, POST will be used instead of GET and content will
            be used as POST payload.
        '''
        self.__url = url
        self.__headers = {}
        self.__buffer = StringIO()
        
        rc = 0
        c = self.__curl
        c.setopt(pycurl.TIMEOUT, 1)
        # c.setopt(pycurl.COOKIEFILE, '') we handle cookies our own now
        c.setopt(pycurl.URL, url)
        c.setopt(pycurl.WRITEFUNCTION, self.__buffer.write)
        c.setopt(pycurl.HEADERFUNCTION, self.__storeHeader)
        c.setopt(pycurl.CONNECTTIMEOUT, 0)
        c.setopt(pycurl.TIMEOUT, 0)
        c.setopt(pycurl.SSL_VERIFYPEER, 0)
        if post:
            self.__log.info("++ POST %s" % (url))
            c.setopt(pycurl.POST, 1)
            c.setopt(pycurl.POSTFIELDS, post)
        else:
            self.__log.info("++ GET %s" % (url))
            c.setopt(pycurl.POST, 0)

        # assemble header        
        cookie = self.__session.getCookie()
        reqHeader = [ "Cache-Control: no-cache, max-age=0, must-revalidate, proxy-revalidate, private", ]
        if cookie:
            self.__log.debug("++ request cookie: %s" % (cookie))
            reqHeader += [ "Cookie: %s" % (cookie), ]
        else:
            self.__log.debug("++ cookie-less request")

        c.setopt(pycurl.HTTPHEADER, reqHeader)
        c.perform()
        if self.__headers.has_key("Set-Cookie"):
            cookie = self.__headers["Set-Cookie"].split(";")[0]
            self.__log.info("++ keep cookie: %s" % (cookie))
            self.__session.setCookie(cookie)
            self.__session.save()

        rc = c.getinfo(pycurl.HTTP_CODE)
        self.__buffer.reset()
        self.__log.info("++ response %d" % (rc))
        return rc
    
    def __storeHeader(self, line):
        '''
        Stores a line of header data.
        
        @param line: Line of http header data.
        '''
        line = line.strip()
        tok = line.split(":", 1)
        if len(tok) > 1:
            self.__headers[tok[0]] = tok[1].strip()
        self.__log.debug(">> %s" % (line))
    
    def getHeader(self):
        '''
        Returns the HTTP header map.
        '''
        return self.__headers
    
    def getResponse(self):
        '''
        Returns the response data.
        '''
        return self.__buffer
    
    def getUrl(self):
        '''
        Returns the URL last queried.
        '''
        return self.__url
    
class FrabClient(object):
    '''
    Wrapper class that hides the different frab commands and provides a higher
    level interface around the backend.
    '''
    
    def __init__(self, config, session):
        '''
        Constructor for the frab client.
        
        @param config: Configuration object for the client.
        @type config: configuration.Config
        @param session: Session for the connection.
        @type session: frabclient.SessionManager
        '''
        self.__log = logging.getLogger("FrabClient")
        self.__config = config
        if not config.isValid():
            raise ClientException("got an invalid configuration object")
        self.__session = session
        self.curl = CurlWrapper(session)

    def checkLoggedIn(self):
        '''
        Checks, if we are already logged in.
        '''
        if not self.__session.getCookie():
            self.__log.info("we don't have a cookie, so we are not signed in.")
            return False
        
        self.__log.info("check, if session is still valid")
        url = self.__joinUrl(self.__config.getProfilePath())
        rc = self.curl.query(url)
        if (rc == 200):
            self.__log.info("we are logged in")
            return True
        else:
            self.__log.info("ew are not logged in")
            return False
        
    def login(self):
        '''
        Performs a login operation into the backend.
        '''
        # we get a cookie first
        self.__log.info("acquire cookie, even if not necessary")
        url = self.__joinUrl()
        self.__checkResponse(self.curl.query(url))
        cookie = self.__session.getCookie()
        self.__log.info("our cookie is %s" % (cookie))
        
        # now we need our CSRL token
        self.__log.info("acquire CSRF token")
        url = self.__joinUrl(self.__config.getSignInForm())
        self.__checkResponse(self.curl.query(url))
        tree = self.__getHtmlTree()
        token = tree.xpath(".//meta[@name='csrf-token']")[0].attrib["content"]
        self.__log.info("out CSRF token is %s" % (token))
        
        # perform actual login
        self.__log.info("perform login")
        url = self.__joinUrl(self.__config.getSignInSubmit())
        loginData = [ "authenticity_token=" + token,
                      "user[email]=" + self.__config.getUsername(),
                      "user[password]=" + self.__config.getPassword(),
                      "user[remember_me]=1",
                      "utf8=%E2%9C%93",
                      "button=" ]
        rc = self.curl.query(url, "&".join(loginData))
        self.__checkResponse(rc, code = 302)
        
        # follow the redirect, to not confuse the server
        location = self.__getHeader("Location")
        self.__log.info("follow redirect to %s" % (location))
        self.__checkResponse(self.curl.query(location))
        
        # check login status
        self.__log.info("check, if we are properly logged in")
        if not self.checkLoggedIn():
            raise ClientException("login failed")
        self.__log.info("we have successfully been logged in")

    def getVersion(self, conference, locale = "en"):
        '''
        Retrieves the version of the last export for the given locale (if any).
        
        @param conference: The conference to be checked.
        @param locale: The locale to request the fahrplan for.
        '''
        url = self.__joinUrl(self.__config.getHtmlExportForm(conference))
        self.__log.info("request fahrplan version via %s" % (url))
        self.__checkResponse(self.curl.query(url))
        tree = self.__getHtmlTree()
        
        self.__log.info("searching for version string")

        query = ".//a[contains(@href, 'download_static_export?export_locale=%s')]" % (locale)
        exportString = tree.xpath(query)
        
        if len(exportString) == 0:
            return None
        return exportString[0].text.strip()
    
    def download(self, outfile, conference, locale = "en"):
        '''
        Downloads the fahrplan.
        
        @param outfile: The file to write the fahrplan to.
        @param conference: The conference to download for.
        @param locale: The locale to download for.
        '''
        
        url = self.__joinUrl(self.__config.getHtmlDownload(conference, locale))
        self.__log.info("download from %s" % (url))
        self.__checkResponse(self.curl.query(url, timeout = 60000))
        self.__log.info("store downloaded data to %s" % (outfile))
        fp = open(outfile, "wb")
        fp.write(self.curl.getResponse().getvalue())
        fp.flush()
        fp.close()
                

    def __joinUrl(self, path = ""):
        '''
        Helper function to join URLs based on the configuration.
        
        @param path: The path to be joined to the servers FQDN.
        '''
        url = "%s://%s/%s" % (self.__config.getFrabSchema(),
                self.__config.getFrabHost(), path)
        return url

    def __checkResponse(self, rc, code = 200):
        '''
        Ensures, that a specific query triggers a specific response. If a wrong
        response code is returned, a ClientException is raised.
        '''
        if rc == code:
            return rc
        raise ClientException("unexpected server resoponse: %s" % (rc))

    def __getHtmlTree(self):
        '''
        Reads the HTML tree from the curl objects data.
        '''
        parser = etree.HTMLParser()
        return etree.parse(self.curl.getResponse(), parser,
                           base_url = self.curl.getUrl())
    
    def __getHeader(self, field):
        '''
        Reads a specific field from the header of the last request. If this does
        not exist, a ClientException is faised.
        '''
        if not self.curl.getHeader().has_key(field):
            raise ClientException("no field in header named %s" % (field))
        return self.curl.getHeader()[field]

class SessionManager(object):
    '''
    Helper class to store setting information like the logged in cookie or the
    previsously requested versions.
    '''
    
    def __init__(self, store):
        '''
        Constructor.
        
        @param store: The file to store session information to.
        '''
        self.__log = logging.getLogger("SessionManager")
        self.__store = store
        try:
            self.__initSession()
            self.__readSession()
        except:
            pass
        self.__saveSession()
        
    def getCookie(self):
        '''
        Returns the cookie set.
        '''
        return self.__session["cookie"]
    
    def setCookie(self, cookie):
        '''
        Stores the sites cookie.
        '''
        self.__session["cookie"] = cookie
    
    def getLastVersion(self, conference, locale = "en"):
        '''
        Returns the last version downloaded for the given conference.
        
        @param conference: Name of the conference.
        @param locale: Locale for the downloaded version.
        '''
        versions = self.__session["versions"]
        if not versions.has_key(locale):
            return None
        locVersions = versions[locale]
        if not locVersions.has_key(conference):
            return None
        return locVersions[conference]

    def setLastVersion(self, conference, version, locale = "en"):
        '''
        Sets the last version downloaded for a specific conference.
        
        @param conference: The conference to set.
        @param version: The version to set.
        @param locale: The locale downloaded.
        '''
        versions = self.__session["versions"]
        if not versions.has_key(locale):
            versions[locale] = {}
        versions[locale][conference] = version
                
    def save(self):
        '''
        Saves the session to the disk.
        '''
        self.__saveSession()
        
    def __initSession(self):
        '''
        Initializes an empty session object.
        '''
        self.__log.info("initialize empty session")
        self.__session = {
            "cookie": None,
            "versions": {
                "en": {},
                "de": {},
            }
        }
    
    def __readSession(self):
        '''
        Loads the session data from file.
        '''
        self.__log.info("try reading session from %s" % (self.__store))
        fp = open(self.__store, "rb")
        self.__session = json.load(fp)
        self.__log.info("session loaded from file")

    def __saveSession(self):
        '''
        Saves the session information to the session storage file.
        '''
        self.__log.info("try writing session to %s" % (self.__store))
        fp = open(self.__store, "wb")
        json.dump(self.__session, fp)
        self.__log.info("session data stored")

