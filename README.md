fahrplandump
============

This repository contains a script to dump a Fahrplan out of a frab
installation.

The script can be called from a cronjob running every five minutes or so. It
will automatically login to the frab and check, if a new version of the
Fahrplan has been exported. If a new version is available on the server, it
will automatically download the file and extract the Fahrplan to the given
location.

Note: As for now, the user for the export script needs full access on the
converence to be eported, as only this permission allows downloading the
exported schedule.

Setup
-----

In order to run the script, you will need python2 and the following
extensions:
- lxml (used for parsing the html content)
- pycurl (used for accessing webfrontends and downloading files)

After installing the necessary extensions, please copy the
`config.py.example` file to `config.py` and modify it according your system
needs.

Cloning the Fahrplan
--------------------

To download the Fahrplan, a current export of the Fahrplan must have been
created manually by some user. The script will always check and download the
latest version, if the version string differs from the information in the
`version` file created by the script itself.

After configuring the script, please call `export.py` to start downloading
the Fahrplan.


