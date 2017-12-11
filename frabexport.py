import json
import configuration
import sys
import frabclient
import logging
import shutil
import os
import subprocess
import traceback
import cachepurge

logging.basicConfig(level = logging.DEBUG)

def loadConfig():
    config = configuration.Config("config.json")
    if not config.isValid():
        print "invalid configuration. please check config.json."
        sys.exit(1)
    return config

def makeSession(config):
    session = frabclient.SessionManager("session.json")
    return session

def makeConnection(config, session):
    client = frabclient.FrabClient(config, session)
    if not client.checkLoggedIn():
        client.login()
    return client

def updateAllConferences(client, config, session):
    for conference in config.getConferenceNames():
        oldVersion = session.getLastVersion(conference)
        newVersion = client.getVersion(conference)
        
        if oldVersion != newVersion:
            logging.info("%s: last was %s and new is %s" % (conference, oldVersion, newVersion))
            try:
                updateConference(client, config, conference)
                logging.info("set oldversion for %s to %s" % (conference, newVersion))
                session.setLastVersion(conference, newVersion)
                session.save()
            except Exception, e:
                logging.error("updating %s failed: %s" % (conference, str(e)))
                logging.debug(traceback.format_exc())
        else:
            logging.info("%s: version still %s" % (conference, newVersion))

def updateConference(client, purger, config, conference):
    tempdir = os.path.join(config.getTempDir(), conference)
    tempfile = os.path.join(config.getTempDir(), "%s.tar.gz" % conference)
    dest = config.getConferenceLocation(conference)
    
    logging.info("clear temporary directories")    
    shutil.rmtree(tempdir, ignore_errors = True)
    shutil.rmtree(tempfile, ignore_errors = True)
    os.makedirs(tempdir)
    if not os.path.exists(dest):
        os.makedirs(dest)

    logging.info("download dump for %s" % (conference))
    client.download(tempfile, conference)
    
    logging.info("extract dump for %s" % (conference))
    subprocess.check_call(["tar", "-xf", tempfile, "-C", tempdir])
    
    logging.info("install dump for %s to %s" % (conference, dest))
    subprocess.check_call(["rsync", "-r", "--delete", os.path.join(tempdir, conference, "."), os.path.join(dest, ".")])
    
    purger.purge(conference)

def main():
    config = loadConfig()
    session = makeSession(config)
    client = makeConnection(config, session)
    purger = cachepurge.CachePurger(config)
    updateAllConferences(client, purger, config, session)

main()

