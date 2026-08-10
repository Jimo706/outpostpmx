# outpostx: services/app_info.py  (or app/app_info.py)

"""
Usage:  from services.app_info import AppInfo
then:   version = AppInfo.VERSION
"""
class AppInfo:
    ORG_NAME = "Outpostpmx"       # impacts the data directory root

    APP_NAME = "OutpostX"
    TITLE = "OutpostX"

    APP_VERSION = "26.08.2"     # CalVer + release-in-month
    APP_MARKER = "260809.1342"  # optional: can be injected during packaging


    APP_WEBSITE = "https://outpostpm.org"