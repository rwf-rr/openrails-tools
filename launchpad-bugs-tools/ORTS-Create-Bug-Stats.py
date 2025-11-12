#!/usr/bin/env python3
# ORTS-Create-Bug-Stats - create statistics about bugs in launchpad
#
# Copyright (c) 2025 Roger Fischer. MIT License.
#
# Requires:
# - pip install launchpadlib
# - pip install tabulate
#
# References:
# - https://documentation.ubuntu.com/launchpad/user/explanation/launchpad-api/launchpadlib/
# - https://documentation.ubuntu.com/launchpad/user/how-to/launchpadlib/using-launchpadlib/
# - https://api.launchpad.net/devel.html
#

import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from launchpadlib.launchpad import Launchpad

verbose = 0

open_states = ['New', 'Incomplete', 'Triaged', 'Deferred', 'Confirmed', 'In Progress', 'Fix Committed']
closed_states = ['Fix Released', 'Invalid', "Won't Fix", 'Does Not Exist', 'Expired', 'Opinion']
all_states = open_states + closed_states

importance_list = ['Critical', 'High', 'Medium', 'Low', 'Wishlist', 'Undecided']

age_range = ['0..7 days', '8..30 days', '31..90 days', '91..180 days', '181..365 days', '1..2 years', '> 2 years']
age_range_days = [7, 30, 90, 180 , 365, 730, None]


### All Bugs by Status

def all_bugs_by_status() :
    print('All bugs by status:')
    total_cnt = 0
    for importance in open_states:
        tasks = project.searchTasks(status=importance)
        total_cnt += len(tasks)
        print(f'{len(tasks):5d}  {importance}')
    print(f'{total_cnt:5d}  \x1B[3mopen\x1B[0m')
    print('       -----')
    total_cnt = 0
    for importance in closed_states:
        tasks = project.searchTasks(status=importance)
        total_cnt += len(tasks)
        print(f'{len(tasks):5d}  {importance}')
    print(f'{total_cnt:5d}  \x1B[3mclosed\x1B[0m')
    print('------------------------')
# end all_bugs_by_status()


### Open Bugs by Importance

def open_bugs_by_importance() :
    print('Open bugs by importance:')
    for importance in importance_list:
        tasks = project.searchTasks(importance=importance)
        print(f'{len(tasks):5d}  {importance}')
    print('------------------------')
# end open_bugs_by_importance()


### Count Open and Closed Bugs based on Date Completed (to verify above counts)

def count_based_on_date_closed() :
    # takes a very long time
    print('Open/Closed based on date closed:')
    tasks = project.searchTasks(status=all_states)  # search without filter returns only open bug tasks
    open_cnt = 0 ; closed_cnt = 0
    for task in tasks :
        if task.date_closed : closed_cnt += 1
        else : open_cnt += 1
    print(f'{open_cnt:5d}  Open')
    print(f'{closed_cnt:5d}  Closed')
    print(f'{len(tasks):5d}  Total')
    print('------------------------')
# end count_based_on_date_closed()


### Open Bugs by Age and Status/Importance

def open_bugs_by_age_and_status_and_importance() :
    print('Open bugs by age and status:')
    bug_status = [[0 for x in range(len(open_states))] for y in range(len(age_range))]
    bug_importance = [[0 for x in range(len(open_states))] for y in range(len(age_range))]
    tasks = project.searchTasks()  # search without filter returns only open bug tasks
    for task in tasks:
        if task.date_created > (datetime.now(tz=lptz) - timedelta(age_range_days[0])):
            bug_status[0][open_states.index(task.status)] += 1
            bug_importance[0][importance_list.index(task.importance)] += 1
        elif task.date_created > datetime.now(tz=lptz) - timedelta(age_range_days[1]):
            bug_status[1][open_states.index(task.status)] += 1
            bug_importance[1][importance_list.index(task.importance)] += 1
        elif task.date_created > datetime.now(tz=lptz) - timedelta(age_range_days[2]):
            bug_status[2][open_states.index(task.status)] += 1
            bug_importance[2][importance_list.index(task.importance)] += 1
        elif task.date_created > datetime.now(tz=lptz) - timedelta(age_range_days[3]):
            bug_status[3][open_states.index(task.status)] += 1
            bug_importance[3][importance_list.index(task.importance)] += 1
        elif task.date_created > datetime.now(tz=lptz) - timedelta(age_range_days[4]):
            bug_status[4][open_states.index(task.status)] += 1
            bug_importance[4][importance_list.index(task.importance)] += 1
        elif task.date_created > datetime.now(tz=lptz) - timedelta(age_range_days[5]):
            bug_status[5][open_states.index(task.status)] += 1
            bug_importance[5][importance_list.index(task.importance)] += 1
        else:
            bug_status[6][open_states.index(task.status)] += 1
            bug_importance[6][importance_list.index(task.importance)] += 1
    print( 'Age'.rjust(15), open_states[0].rjust(14), open_states[1].rjust(14), open_states[2].rjust(14),
           open_states[3].rjust(14), open_states[4].rjust(14), open_states[5].rjust(14), open_states[6].rjust(14))
    for ai in range(len(age_range)) :
        print( age_range[ai].rjust(15), end='')
        for ii in range(len(open_states)) :
            print( f'{bug_status[ai][ii]:15d}', end='')
        print(flush=True)
    print('------------------------')
    print('Open bugs by age and importance:')
    print( 'Age'.rjust(15), importance_list[0].rjust(14), importance_list[1].rjust(14), importance_list[2].rjust(14),
           importance_list[3].rjust(14), importance_list[4].rjust(14), importance_list[5].rjust(14))
    for ai in range(len(age_range)) :
        print( age_range[ai].rjust(15), end='')
        for ii in range(len(importance_list)) :
            print( f'{bug_importance[ai][ii]:15d}', end='')
        print(flush=True)
    print('------------------------')
# end open_bugs_by_age_and_status_and_importance()


### main

cm = tempfile.TemporaryDirectory( prefix='launchpad-')
cache_dir = cm.name

print( 'Connecting to Launchpad ...', file=sys.stderr)

launchpad = Launchpad.login_anonymously( 'explore', 'production', cache_dir, version='devel')
project = launchpad.projects['or']
lptz = project.date_created.tzinfo

# working on ...

all_bugs_by_status()

open_bugs_by_importance()

# may take a long time - intended to verify the open and closed states
if verbose > 1 : count_based_on_date_closed()

open_bugs_by_age_and_status_and_importance()

exit(0)
