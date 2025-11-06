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

print_only_id = False  # use argument --ids-only

# search filters
status_filter = ['New']
importance_filter = ['Undecided']
date_filter = '2022-11-11'  # 1.4 release = 2021-10-19, 1.5 release = 2022-11-11, 1.6 release = 2025-09-09
tags_filter = ['content']
person_filter_part = '~rwf09'  # eg "~rwf09"; will be prefixed with URL
milestone_filter = '1.5'  # wg "1.5"; does not work because it gets converted to float somewhere

# search order: date_last_updated, datecreated, importance, status, id
order_by_fields = ['date_last_updated']

# python filters; search does no support updated_before
py_date_filter = date.fromisoformat( '2025-09-09')  # 1.6 release

if len( sys.argv) > 1 and sys.argv[1] == '--ids-only' :
    print_only_id = True

cm = tempfile.TemporaryDirectory( prefix='launchpad-')
cache_dir = cm.name

print( 'Connecting to Launchpad ...', file=sys.stderr)

launchpad = Launchpad.login_anonymously( 'or-maintenance', 'production', cache_dir, version='devel')
project = launchpad.projects['or']

if person_filter_part :
    person_filter = project.self_link.removesuffix('or') + person_filter_part

print( 'Fetching bugs from Launchpad ...', file=sys.stderr)

# filters: status=list, importance=list, modified_since=str, created_before=str, created_since=str,
#          tags=list,bug_reporter=link, assignee=link, milestone=???
# order: order_by=list
tasks = project.searchTasks(status=status_filter, importance=importance_filter, created_before=date_filter,
                            order_by=order_by_fields)

print( '{} tasks found in launchpad'.format( len(tasks)), file=sys.stderr)

if not print_only_id :
    print( 'Id,Status,Importance,LastUpdated,Created,DaysActive,Tags,Reporter,Title,Link')
    out_fmt = '{},{},{},"{}","{}",{},"{}","{}","{}",{}'

num_bugs = 0
for task in tasks :

    bug = task.bug
    owner = bug.owner
    created = bug.date_created.date()
    updated = bug.date_last_updated.date()
    tags = ','.join(bug.tags)
    user_name = owner.display_name.encode('utf-8', 'replace')
    bug_title = bug.title.encode('utf-8', 'replace')

    # search does not have an updated_before filter
    if updated < py_date_filter :
        if print_only_id :
            print( bug.id)
        else :
            print(out_fmt.format(bug.id, task.status, task.importance, updated, created, (updated - created).days,
                                 tags, user_name, bug_title, task.web_link), flush=True)
        num_bugs += 1

print( '{} bugs exported'.format(num_bugs), file=sys.stderr)

exit(0)
