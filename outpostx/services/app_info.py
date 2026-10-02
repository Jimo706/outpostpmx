# outpostx: services/app_info.py  (or app/app_info.py)

"""
Usage:  from services.app_info import AppInfo
then:   version = AppInfo.VERSION
"""
class AppInfo:
    ORG_NAME = "Outpostpmx"       # impacts the data directory root

    APP_NAME = "OutpostX"
    TITLE = "OutpostX"

    APP_VERSION = "26.09.5"         # CalVer + release-in-month
    APP_MARKER = "261001.2139"      # optional: can be injected during packaging

    APP_WEBSITE = "https://outpostpm.org"