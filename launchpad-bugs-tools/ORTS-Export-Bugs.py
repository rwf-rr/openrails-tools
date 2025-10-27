#!/usr/bin/env python3
# ORTS-Export-Bugs - export filtered launchpad bugs to stdout in CSV format
#
# Copyright (c) 2025 Roger Fischer. MIT License.
#
# Requires:
# - pip install launchpadlib
#
# Notes:
# - This script is meant to be edited to achieve the desired objective. That is easier than trying to anticipate
#   all future needs.
#
# References:
# - https://documentation.ubuntu.com/launchpad/user/explanation/launchpad-api/launchpadlib/
# - https://documentation.ubuntu.com/launchpad/user/how-to/launchpadlib/using-launchpadlib/
# - https://api.launchpad.net/devel.html
#

import sys
import tempfile
from datetime import date, datetime, timezone
from launchpadlib.launchpad import Launchpad

printOnlyId = False

# search filters
statusFilter = ['New']
importanceFilter = ['Undecided']
dateFilter = '2021-10-19'  # 1.4 release
tagsFilter = ['content']
personFilterPart = '~rwf09'  # eg "~rwf09"; will be prefixed with URL
milestoneFilter = '1.5'  # wg "1.5"; does not work because it gets converted to float somewhere

# search order: date_last_updated, datecreated, importance, status, id
orderByFields = ['date_last_updated']

# python filters; search does no support updated_before
pyDateFilter = date(2022, 11, 11)  # 1.5 release

cm = tempfile.TemporaryDirectory( prefix='launchpad-')
cachedir = cm.name

print( 'Connecting to Launchpad ...', file=sys.stderr)

launchpad = Launchpad.login_anonymously( 'testing', 'production', cachedir, version='devel')
project = launchpad.projects['or']

if personFilterPart :
    personFilter = project.self_link.removesuffix( 'or') + personFilterPart

print( 'Fetching bugs from Launchpad ...', file=sys.stderr)

# filters: status=list, importance=list, modified_since=str, created_before=str, created_since=str,
#          tags=list,bug_reporter=link, assignee=link, milestone=???
# order: order_by=list
tasks = project.searchTasks( status=statusFilter, importance=importanceFilter, created_before=dateFilter,
                             order_by=orderByFields)

print( '{} tasks fetched from launchpad'.format( len(tasks)), file=sys.stderr)

if not printOnlyId :
    print( 'Id,Status,Importance,LastUpdated,Created,DaysActive,Tags,Reporter,Title,Link')
    outFmt = '{},{},{},"{}","{}",{},"{}","{}","{}",{}'

numBugs = 0
for task in tasks :

    bug = task.bug
    owner = bug.owner
    created = bug.date_created.date()
    updated = bug.date_last_updated.date()
    tags = ','.join(bug.tags)

    # search does not have an updated_before filter
    if updated < pyDateFilter :
        if printOnlyId :
            print( bug.id)
        else :
            print( outFmt.format( bug.id, task.status, task.importance, updated, created, (updated - created).days,
                                  tags, owner.display_name, bug.title, task.web_link))
        numBugs += 1

print( '{} bugs exported'.format(numBugs), file=sys.stderr)

exit(0)
