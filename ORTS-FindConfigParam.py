#!/usr/bin/env python3
# ORTS-FindConfigParam - search folder tree for config file with specified parameter
#
# Copyright (c) 2025 Roger Fischer. MIT License.
#

import argparse
import pathlib
import re
import sys

numFiles = numMatches = 0


### read a file that is either utf-16 or utf8
def readFile( filePath) :
    enc = "utf-16"
    bytes = filePath.read_bytes()
    if 0 < bytes[0] < 128: enc = 'utf-8'
    return bytes.decode( encoding = enc, errors = 'replace' )


### main
parser = argparse.ArgumentParser( description='Find config files that have the specified parameter within the specified context.')
parser.add_argument( '-v', '--verbose', action='count', default=0)
parser.add_argument( 'dirPath', type=pathlib.Path, help='Directory where to search for config files.')
parser.add_argument( 'filePat', help='Pattern for the config file name, eg: "*.cvf".')
parser.add_argument( 'paramName', help='Name of parameter to search for. Must be a literal')
parser.add_argument( 'context', help='A string that needs to be near the parameter to qualify it. May be a regex.')
parser.add_argument( '-r', '--range', type=int, default=200, help='Optional. The max distance to look for context. '
                     'Negative if the context is to be found after the parameter. Default is 200 characters.')

args = parser.parse_args()
dirPath = args.dirPath
filePat = args.filePat
paramName = args.paramName
context = args.context
range = args.range
verbose = args.verbose

paramRe = re.compile( '\\s(' + paramName + ')\\s*\\(\\s*([^)(]+)[)(]', flags=re.IGNORECASE)

contextRe = re.compile( context, flags=re.IGNORECASE)
if not contextRe :
    print( 'Error: "{}" is not a proper regex.'.format(context), file=sys.stderr)
    sys.exit(1)

if not dirPath.is_dir() :
    print( 'Error: "{}" is not a directory.'.format(args.dirPath), file=sys.stderr)
    sys.exit(1)

for path in dirPath.rglob( filePat) :
    if verbose > 0 : print( "...processing config file ", path, file=sys.stderr)
    numFiles += 1
    txt = readFile( path)

    for paramMatch in paramRe.finditer( txt) :
        val = paramMatch.group()
        if len(val) > 80 : val = val[0:80] + '...'

        if range >=0 :
            start = paramMatch.start() - range
            end = paramMatch.start()
        else :
            start = paramMatch.start()
            end = paramMatch.start() - range

        ctxMatch = contextRe.search( txt, pos=start, endpos=end)
        if ctxMatch :
            numMatches += 1
            print( path, val, sep=': ')

print( 'Processed {} config files, found {} matches.'.format(numFiles, numMatches), file=sys.stderr)
exit(0)
