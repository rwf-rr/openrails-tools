#!/usr/bin/env python3
# ORTS-CompareTwoFolders - compare the content of two Open Rails folders
#
# This does a much narrower compare than tools such as Beyond Compare. It currently looks at the size only.
# Real comparison is difficult for compressed and/or binary files.
#
# The main objectives are to find files that exist on one side but not the other.
#
# Copyright (c) 2026 Roger Fischer. MIT License.
#

import argparse
import pathlib
import sys


### walk a directory  --  walk() is available only in 3.12 (2023-10-02) and later
def walk_dir(path_to_dir, root_path) :
    global already_walked_dirs, num_dirs, num_files, num_matching_files
    if path_to_dir in already_walked_dirs :
        if verbose > 0 : print( 'Info: skipping already processed folder "{}".'.format(path_to_dir), file=sys.stderr)
        return
    if verbose > 0 : print('Info: walking folder "{}".'.format(path_to_dir), file=sys.stderr)
    num_dirs += 1
    for child in path_to_dir.iterdir() :
        if child.is_dir() :
            walk_dir(child, root_path)
        else :
            num_files += 1
            if not type_filter or child.suffix.lower() == type_filter.lower() :
                num_matching_files += 1
                file_stats = child.stat()
                rel_path = child.relative_to(root_path)
                file_list[rel_path] = (child.name, file_stats.st_size)
    return


### main
parser = argparse.ArgumentParser(description='Compare the content of two folders. '
                                             'Currently only the file size is used to determine if they are the same.')
parser.add_argument('-v', '--verbose', action='count', default=0, help='Be more verbose. Option may be repeated.')
parser.add_argument('-l', '--left-only', action='store_true', help='List files that are in the first (left) folder only.')
parser.add_argument('-r', '--right-only', action='store_true', help='List files that are in the second (right) folder only.')
parser.add_argument('-b', '--in_both', action='store_true', help='List files that are in both folders, different or same.')
parser.add_argument('-d', '--different', action='store_true', help='List files that different.')
parser.add_argument('-s', '--same', action='store_true', help='List files that are the same.')
parser.add_argument('-t', '--type', help='Only compare files of the specified type (extension).')
parser.add_argument('firstDirPath', type=pathlib.Path, help='First (left) folder path, absolute or relative.')
parser.add_argument('secondDirPath', type=pathlib.Path, help='Second (right) folder path, absolute or relative.')
args = parser.parse_args()
verbose = args.verbose
list_only_in_left = args.left_only
list_only_in_right = args.right_only
list_in_both = args.in_both
list_different = args.different
list_same = args.same
if args.type and not args.type.startswith('.') :
    type_filter = '.' + args.type
else :
    type_filter = args.type
first_dir_path = args.firstDirPath
second_dir_path = args.secondDirPath

if not first_dir_path.is_dir() :
    print( 'Error: first path >{}< is not a directory.'.format(first_dir_path), file=sys.stderr)
    sys.exit(1)

if not second_dir_path.is_dir() :
    print( 'Error: second path >{}< is not a directory.'.format(second_dir_path), file=sys.stderr)
    sys.exit(1)

# traverse the first directory
already_walked_dirs = []
file_list = {} ; num_dirs = num_files = num_matching_files = 0
walk_dir(first_dir_path, first_dir_path)
if verbose > 0 : print( 'Info: left = "{}", dirs = {}, files = {}, matching = {}'.format(first_dir_path, num_dirs, num_files, num_matching_files), file=sys.stderr)
# left_files_dict = dict(sorted(file_list.items()))
left_files_list = list(sorted(file_list.items()))
left_counts = (num_dirs, num_files, num_matching_files)

# traverse the second directory
already_walked_dirs = []
file_list = {} ; num_dirs = num_files = num_matching_files = 0
walk_dir(second_dir_path, second_dir_path)
if verbose > 0 : print( 'Info: right = "{}", dirs = {}, files = {}, matching = {}'.format(second_dir_path, num_dirs, num_files, num_matching_files), file=sys.stderr)
# right_files_dict = dict(sorted(file_list.items()))
right_files_list = list(sorted(file_list.items()))
right_counts = (num_dirs, num_files, num_matching_files)

leftcnt = len(left_files_list)
rightcnt = len(right_files_list)

# compare the two lists
num_only_in_left = num_only_in_right = num_in_both = num_different = num_same = 0
only_in_left = [] ; only_in_right = [] ; in_both = [] ; in_both_different = [] ; in_both_same = []
if leftcnt == 0 and rightcnt == 0 :
    print( 'Warning: No files found.')
elif leftcnt == 0 :
    print( 'Warning: no files in first (left) folder, {} in second (right) folder'.format(rightcnt))
elif rightcnt == 0:
    print('Warning: no files in second (right) folder, {} in first (left) folder'.format(leftcnt))
else :
    file_cnt = 0
    leftidx = rightidx = 0
    left_name = str(left_files_list[leftidx][0]).lower()
    right_name = str(right_files_list[rightidx][0]).lower()
    done = False
    while not done :
        file_cnt += 1
        if verbose > 0 and file_cnt % 1000 == 0 :
            print('Info: file {}; leftidx={}, rightidx={}, left-only={}, right-only={}, both={}'.format(file_cnt, leftidx, rightidx, num_only_in_left, num_only_in_right, num_in_both), file=sys.stderr)
        if rightidx >= rightcnt or left_name < right_name :
            if list_only_in_left :
                only_in_left.append('{}\t{}'.format(left_files_list[leftidx][0], left_files_list[leftidx][1][1]))
            num_only_in_left += 1
            leftidx += 1
        elif leftidx >= leftcnt or left_name > right_name :
            if list_only_in_right :
                only_in_right.append('{}\t{}'.format(right_files_list[rightidx][0], right_files_list[rightidx][1][1]))
            num_only_in_right += 1
            rightidx += 1
        else :
            if list_in_both :
                in_both.append('{}\t{}\t{}'.format(left_files_list[leftidx][0], left_files_list[leftidx][1][1], right_files_list[rightidx][1][1]))
            num_in_both += 1
            if left_files_list[leftidx][1][1] == right_files_list[rightidx][1][1] :
                if list_same :
                    in_both_same.append('{}\t{}'.format(left_files_list[leftidx][0], left_files_list[leftidx][1][1]))
                num_same += 1
            else :
                if list_different :
                    in_both_different.append('{}\t{}\t{}'.format(left_files_list[leftidx][0], left_files_list[leftidx][1][1], right_files_list[rightidx][1][1]))
                num_different += 1
            leftidx += 1
            rightidx += 1

        if rightidx >= rightcnt and leftidx >= leftcnt :
            done = True
        elif file_cnt > leftcnt + rightcnt :
            print('Error: apparent infinite loop; file_cnt={}, leftidx={}, rightidx={}, leftcnt={}, rightcnt={}'.format(file_cnt, leftidx, rightidx, leftcnt, rightcnt))
            done = True
        if leftidx < leftcnt : left_name = str(left_files_list[leftidx][0]).lower()
        else : left_name = '~~~'   # lexically greater than any valid filename
        if rightidx < rightcnt : right_name = str(right_files_list[rightidx][0]).lower()
        else : right_name = '~~~'   # lexically greater than any valid filename

# output lists
if list_only_in_left :
    for line in only_in_left : print('<-', line)
if list_only_in_right :
    for line in only_in_right : print('->', line)
if list_in_both :
    for line in in_both : print('<>', line)
if list_same :
    for line in in_both_same : print('==', line)
if list_different :
    for line in in_both_different : print('~~', line)
sys.stdout.flush()

# output summary
print('\nComparing "{}" and "{}"'.format(first_dir_path, second_dir_path), file=sys.stderr)
print('Only in left folder:', num_only_in_left, file=sys.stderr)
print('Only in right folder:', num_only_in_right, file=sys.stderr)
print('In both folders: {}\tdifferent {}\tsame {}'.format(num_in_both,num_different, num_same), file=sys.stderr)
print('Total files:', num_only_in_left + num_only_in_right + num_in_both, file=sys.stderr)

exit(0)
