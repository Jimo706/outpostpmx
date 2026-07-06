# optermx: services/app_info.py

"""
Usage:  from services.app_info import AppInfo
then:   version = AppInfo.APP_VERSION
"""
class AppInfo:
    ORG_NAME = "Outpostpmx"       # impacts the data directory root

    APP_NAME = "Optermx"
    TITLE = "Optermx"

    APP_VERSION = "26.07.3"     # CalVer + release-in-month
    APP_MARKER = "260705.1102"  # optional: can be injected during packaging

    APP_WEBSITE = "https://outpostpm.org"
