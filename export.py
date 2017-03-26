#!/usr/local/bin/python2 -tt
# -*- coding: utf-8 -*-

import pycurl
from cStringIO import StringIO
import os
import config
from lxml import etree
import sys
from uuid import uuid4 as newuuid
import time
import traceback as tr

headers = {}

def header(str):
    global headers
    str = str.strip()
    print "/* %-80s */" % (str)
    tok = str.split(":", 1)
    if len(tok) > 1:
        headers[tok[0]] = tok[1].strip()
    

def setupCurl(c, url):
    '''
    Common configuration for curl instances.
    
    @type c: pycurl.Curl
    @type url: str
    @rtype StringIO
    '''
    global headers
    buf = StringIO()
    headers = {}
    c.setopt(pycurl.TIMEOUT, 1)
    c.setopt(pycurl.COOKIEFILE, '')
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.WRITEFUNCTION, buf.write)
    c.setopt(pycurl.HEADERFUNCTION, header)
    c.setopt(pycurl.CONNECTTIMEOUT, 0)
    c.setopt(pycurl.TIMEOUT, 0)
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.POST, 0)
    c.setopt(pycurl.HTTPHEADER, ["Cache-Control: no-cache, max-age=0, must-revalidate, proxy-revalidate, private"])
    return buf

def getCookie(c):
    '''
    Hopefully receives a fresh cookie.
    '''
    print "aquire cookie"
    buf = setupCurl(c, config.BASE_URL)
    print "GET %s" % (config.BASE_URL)
    c.perform()
    assert c.getinfo(pycurl.HTTP_CODE) == 200, "failed to aquire cookie"
    return True

def aquireToken(c):
    '''
    Aquires a login token.
    
    @type c: pycurl.Curl
    '''
    print "aquire token"
    buf = setupCurl(c, config.LOGIN_URL)
    print "GET %s" % (config.LOGIN_URL)
    c.perform()
    assert c.getinfo(pycurl.HTTP_CODE) == 200, "failed to aquire token"
    parser = etree.HTMLParser()
    buf.reset()
    tree = etree.parse(buf, parser=parser, base_url=config.LOGIN_URL)
    token = tree.xpath(".//meta[@name='csrf-token']")
    return token[0].attrib["content"]
    
def login(token, username, password, c):
    '''
    Perform login on website.
    
    @type username: str
    @type password: str
    @type c: pycurl.Curl
    '''
    global headers
    print "login with token %s" % token
    buf = setupCurl(c, config.LOGIN_SUBMIT)
    c.setopt(pycurl.POST, 1)
    c.setopt(pycurl.POSTFIELDS, "authenticity_token=%s&user[email]=%s&user[password]=%s&user[remember_me]=1&utf8=%s&button=" % (token, username, password, "%E2%9C%93"))
    print "POST %s" % (config.LOGIN_SUBMIT)
    c.perform()
    assert c.getinfo(pycurl.HTTP_CODE) == 302, "failed to login"

    print "follow redirect to %s to verify login status" % (headers["Location"])
    buf = setupCurl(c, headers["Location"])
    c.setopt(pycurl.POST, 0)
    c.perform()
    assert c.getinfo(pycurl.HTTP_CODE) == 200, "failed to login"

def getVersion(c, i = 5):
    '''
    '''
    print "fetch version"
    buf = setupCurl(c, config.VERSION_URL)
    print "GET %s" % (config.VERSION_URL)
    c.perform()
    assert c.getinfo(pycurl.HTTP_CODE) == 200, "failed to fetch version"
    
    parser = etree.HTMLParser()
    buf.reset()
    tree = etree.parse(buf, parser=parser, base_url=config.VERSION_URL)
    versionString = tree.xpath(".//p[@class='release']")

    print "fetch export timestamp"
    buf = setupCurl(c, config.EXPORT_URL)
    print "GET %s" % (config.EXPORT_URL)
    c.perform()
    assert c.getinfo(pycurl.HTTP_CODE) == 200, "failed to fetch version"

    parser = etree.HTMLParser()
    buf.reset()
    tree = etree.parse(buf, parser=parser, base_url=config.VERSION_URL)
    qry = ".//a[contains(@href, 'download_static_export?export_locale=%s')]" % (config.EXPORT_LOCALE)
    exportString = tree.xpath(qry)

    return "%s: %s" % (exportString[0].text.strip(), versionString[0].text.strip())

def download(c):
    '''
    Perform download of fahrplan.
    
    @type c: pycurl.Curl
    '''
    print "download fahrplan"
    buf = setupCurl(c, config.STATIC_EXPORT)
    c.setopt(pycurl.TIMEOUT, 6000)
    print "GET %s" % (config.STATIC_EXPORT)
    c.perform()
    assert c.getinfo(pycurl.HTTP_CODE) == 200, "failed to download fahrplan"
    
    print "store fahrplan to disk"
    dumpfile = open("fahrplan.tar.gz", "wb")
    buf.reset()
    dumpfile.write(buf.getvalue())
    dumpfile.close()
    print "done"

def installOnRemoteSite():
    '''
    Installs the Fahrplan on the given server.
    '''
    print "copy fahrplan to server"
    assert os.system("scp fahrplan.tar.gz nexus@events.ccc.de:/usr/jails/events.ccc.de/tmp")

    print "install fahrplan on server"
    assert os.system('ssh -t %s "sudo /root/exec_import.sh"' % (config.SSH_HOST)) == 0

def restartVarnish():
    '''
    Restarts the varnish on the remote site.
    '''
    print "restarting varnish"
    assert os.system('ssh %s "sudo /usr/local/etc/rc.d/varnishd restart"' % (config.SSH_HOST)) == 0

def getOldVersion():
    f = open("version", "r")
    return f.readline().decode('utf-8')

def saveVersion(version):
    try:
        f = open("version", "w")
        f.write(version.encode('utf-8'))
        f.close()
        
        f = open("all_versions", "a")
        f.write("%s\n" % (version.encode('utf-8')))
        f.close()
        
    except:
        print "failed writing version file"

def install(version):
    try:
        print "create teporary directory..."
        assert os.system("rm -rf fahrplan_unpack") == 0
        assert os.system("mkdir -p fahrplan_unpack") == 0
        
        print "extract fahrplan..."
        assert os.system("cd fahrplan_unpack ; tar -xf ../fahrplan.tar.gz ; mv -v '%s' 'Fahrplan'" % (config.ACRONYM)) == 0

        print "patch ical..."
        # assert os.system("sed -i '' 's/^URL:\/\//URL:http:\/\//g; /^ORGANIZER.*/d;' fahrplan_unpack/Fahrplan/schedule.ics fahrplan_unpack/Fahrplan/events/*.ics") == 0
        os.system("sed -i '' 's/^URL:\/\//URL:http:\/\//g; /^ORGANIZER.*/d;' fahrplan_unpack/Fahrplan/schedule.ics fahrplan_unpack/Fahrplan/events/*.ics")

        print "install fahrplan..."
        uuid = newuuid()
        assert os.system("rm '%s/Fahrplan/'*.tar.gz ; mv fahrplan.tar.gz '%s/Fahrplan/%s.tar.gz'" % (config.DESTINATION, config.DESTINATION, uuid)) == 0
        assert os.system("cp -R fahrplan_unpack/Fahrplan '%s'" % (config.DESTINATION)) == 0
        fp = open("%s/Fahrplan/version" % (config.DESTINATION), "w")
        fp.write("VER: %s\n" % (version.encode('utf-8')))
        fp.write("URL: https://fahrplan.events.ccc.de/congress/%s/Fahrplan/%s.tar.gz\n" % (config.YEAR, str(uuid)))
        fp.close()

        print "perform xslt transform..."
        try:
                doc = etree.parse("%s/Fahrplan/schedule.xml" % (config.DESTINATION))
                xslt = etree.parse("schedule-to-wiki.xsl")
                transf = etree.XSLT(xslt)
                out = transf(doc)
                fp = open("%s/Fahrplan/wiki-schedule.xml" % (config.DESTINATION), "w")
                fp.write(etree.tostring(out, pretty_print=True))
                fp.close()
        except:
                print "xslt failed. calendar will not be available to wiki."
        
    except:
        tr.print_exc()
        print "failed to install fahrplan"
        return False
    return True

def perform_purge(c, url, proto):
    headers = []
    buffer = StringIO()
    c.setopt(c.URL, "http://%s%s" % (config.SERVERNAME, url))
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.HEADERFUNCTION, headers.append)
    c.setopt(c.CUSTOMREQUEST, "PURGE")
    # c.setopt(c.RESOLVE, ['events.ccc.de:80:192.168.235.3'])
    c.setopt(c.RESOLVE, [config.PURGEADDR])
    if proto != None:
        c.setopt(c.HTTPHEADER, ['X-Forwarded-Proto: https'])
    c.perform()
    print "%s: PURGE %s" % (headers[0].strip()[9:], url)

def perform_get(c, url, proto):
    headers = []
    buffer = StringIO()
    c.setopt(c.URL, "http://events.ccc.de%s" % (url))
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.HEADERFUNCTION, headers.append)
    c.setopt(c.CUSTOMREQUEST, "GET")
    c.setopt(c.RESOLVE, ['events.ccc.de:80:%s' % config.PURGEIP])
    if proto != None:
        c.setopt(c.HTTPHEADER, ['X-Forwarded-Proto: https'])
    c.perform()
    print "%s: GET %s" % (headers[0].strip()[9:], url)


def purge_varnish():
    try:
        print "purging pages in varnish..."
        dst = config.DESTINATION + '/Fahrplan'
        c = pycurl.Curl()
        for proto in [None, 'https']:
            perform_purge(c, config.PURGEBASE, proto)
            perform_purge(c, config.PURGEBASE + '/', proto)
            for basedir, folders, files in os.walk(dst):
                for file in files:
                    url = "/".join(filter(lambda x: x != "", [config.PURGEBASE, basedir[len(dst) + 1:], file]))
                    perform_purge(c, url, proto)
                for folder in folders:
                    url = "/".join(filter(lambda x: x != "", [config.PURGEBASE, basedir[len(dst) + 1:], folder]))
                    perform_purge(c, url, proto)
            for url in config.ADDITIONAL:
                perform_get(c, url, proto)

        c.close()
        
    except:
        tr.print_exc()
        print "failed to purge..."
        return False
    return True

def tryLogin(user, pwd, retries = 3):
    for I in range(retries):
        c = pycurl.Curl()
        try:
            token = aquireToken(c)
            login(token, user, pwd, c)
            return c
        except:
            print "login failed."
    assert False, "login finally failed."

if __name__ == '__main__':
    try:
        c = tryLogin(config.USERNAME, config.PASSWORD, 20)
        
        old_version = ""
        try:
            old_version = getOldVersion()
            print "old version was %s" % (old_version)
        except:
            print "no old version available"
        
        current_version = getVersion(c)
        try:
            print "new version is %s" % (current_version)
        except:
            pass
                
        if old_version == current_version:
            print "version number not changed"
            exit(0)
        
        download(c)
#        assert os.system("mv /var/www/events.ccc.de/congress/2014/Fahrplan/.htaccess{,.old}") == 0
        assert install(current_version)
        assert purge_varnish()
#        installOnRemoteSite()
#	restartVarnish()

        saveVersion(current_version)
    finally:
        pass
    pass


