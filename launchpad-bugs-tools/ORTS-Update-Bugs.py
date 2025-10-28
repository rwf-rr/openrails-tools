#!/usr/bin/env python3
# ORTS-Update-Bugs - update the bugs specified by id in a file or on stdin
#
# Copyright (c) 2025 Roger Fischer. MIT License.
#
# Requires:
# - pip install launchpadlib
# - pip install keyring
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
import re
import os.path
import tempfile
from launchpadlib.launchpad import Launchpad

testing = False
verbose = True

new_status = 'Expired'
new_tags = ['obsolete']
new_importance = None
clear_assignee = False

arg_len = len( sys.argv)
if arg_len > 2 :
    print( 'Invalid arguments, expecting one file or no argument: ', sys.argv)
    exit(1)
elif arg_len == 2 and os.path.isfile( sys.argv[1]) :
    in_file = open( sys.argv[1], 'r')
else :
    in_file = sys.stdin

bug_id_str = in_file.read()
bug_id_list = re.split(r'\W+', bug_id_str)

# above split may not eliminate consecutive separators
print( f'Approx. {len( bug_id_list)} bug ids read', file=sys.stderr)

if in_file != sys.stdin :
    in_file.close()

# bug_list = [1444131, 1409387] # 1335370, 1444131, 1409387

cm = tempfile.TemporaryDirectory( prefix='launchpad-')
cache_dir = cm.name

print( 'Connecting to Launchpad ...', file=sys.stderr)

# this may bring up a web page to log into UbuntuOne and authorize the host machine
launchpad = Launchpad.login_with( 'testing', 'production', cache_dir, version='devel')
project = launchpad.projects['or']

print( 'Processing bug ids  ...', file=sys.stderr)

num_bugs_read = num_bugs_modified = 0
for bug_id in bug_id_list :

    if not bug_id.isdigit() :
        continue


    bug = launchpad.bugs[bug_id]
    if not bug :
        print( f'Error: unable to retrieve bug {bug_id}', file=sys.stderr)
        continue

    task = bug.bug_tasks[0]
    if not task :
        print( f'Error: unable to retrieve task for bug {bug_id}', file=sys.stderr)
        continue

    num_bugs_read += 1

    if not task.bug_target_name == 'or' :
        print(f'Bug {bug_id} "{bug.title}" is not targeted to OpenRails - skipping it.', file=sys.stderr)
        continue

    if new_tags :
        new_tag_list = bug.tags
        new_tag_list.extend( new_tags)
        bug.tags = new_tag_list

    if new_status :
        task.status = new_status

    if new_importance :
        task.importance = new_importance

    if clear_assignee :
        task.assignee_link = None

    if verbose :
        print(f'... updating bug {bug.id}, status {task.status}, tags {bug.tags} ...')

    if not testing :
        try :
            if bug._dirty_attributes :
                bug.lp_save()
            if task._dirty_attributes :
                task.lp_save()
            num_bugs_modified += 1
        except Exception as e :
            print(f'Failed to update bug {bug_id}, error: {e}', file=sys.stderr)

# end for each bug

print( f'{num_bugs_modified} bugs modified (of {num_bugs_read})', file=sys.stderr)

exit(0)
