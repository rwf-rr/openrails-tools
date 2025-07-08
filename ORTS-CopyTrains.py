#!/usr/bin/env python3
# ORTS-CopyTrains - copy all the consists and rolling stock needed by a route
#
# Copyright (c) 2025 Roger Fischer. MIT License.
#

# TODO: consists with parenthesis in name - these must be quoted in srv file

import argparse
import pathlib
import shutil
import re
import sys

numConsists = numTrainset = 0
consistPattern = re.compile('Train_Config\\s*\\(([^)]+)\\)', flags=re.IGNORECASE)
trainsetSubPattern = '\\(\\s*(\\S+)\\s*(\\S+)\\s\\)'
#trainsetPattern = re.compile( 'EngineData\\s*' + trainsetSubPattern + '|' + 'WagonData\\s*' + trainsetSubPattern, flags=re.IGNORECASE)
trainsetPattern = re.compile( '(EngineData|WagonData)\\s*\\(\\s*(\\S+)\\s*(\\S+)\\s\\)', flags=re.IGNORECASE)

### read a file that is either utf-16 or utf8
def readFile( filePath) :
    enc = "utf-16"
    bytes = filePath.read_bytes()
    if 0 < bytes[0] < 128: enc = 'utf-8'
    return bytes.decode(encoding = enc, errors = 'replace' )

### main
parser = argparse.ArgumentParser( description='Copy all the consists and rolling stock (trainset) needed by a route from another content folder.')
parser.add_argument( '-v', '--verbose', action='count', default=0)
parser.add_argument( 'routePath', type=pathlib.Path, help='Route folder, to copy the trains to. The folder that contains the Services sub-folder.')
parser.add_argument( 'contentPath', type=pathlib.Path, help='Content folder, to copy the trains from. The folder that contains the Trains sub-folder')

args = parser.parse_args()
routePath = args.routePath
contentPath = args.contentPath
verbose = args.verbose

# check that the route exists and has services folder (to scan) and consists and trainset folders to copy to
if not routePath.is_dir() :
    print( 'Error: "{}" is not a folder.'.format(routePath), file=sys.stderr)
    sys.exit(1)
servicesDirPath = routePath / 'Services'
if not servicesDirPath.is_dir() :
    print( 'Error: "{}" does not contain a Services folder.'.format(routePath), file=sys.stderr)
    sys.exit(1)
targetPath = routePath.parent.parent / 'Trains'
toConsistsDirPath = targetPath / 'Consists'
if not toConsistsDirPath.is_dir() :
    print( 'Error: Content folder of route "{}" does not contain a Consists sub-folder ({}).'.format(routePath.name, toConsistsDirPath), file=sys.stderr)
    sys.exit(1)
toTrainsetDirPath = targetPath / 'Trainset'
if not toTrainsetDirPath.is_dir() :
    print( 'Error: Content folder of route "{}" does not contain a Trainset sub-folder ({}).'.format(routePath.name, toTrainsetDirPath), file=sys.stderr)
    sys.exit(1)

# check that the content folder exists and has consists and trainset folders (to copy from)
if not contentPath.is_dir() :
    print( 'Error: "{}" is not a folder.'.format(contentPath), file=sys.stderr)
    sys.exit(1)
sourcePath = contentPath / 'Trains'
fromConsistsDirPath = sourcePath / 'Consists'
if not fromConsistsDirPath.is_dir() :
    print( 'Error: Content folder "{}" to copy from does not contain a Consists sub-folder ({}).'.format(contentPath.name, fromConsistsDirPath), file=sys.stderr)
    sys.exit(1)
fromTrainsetDirPath = sourcePath / 'Trainset'
if not fromTrainsetDirPath.is_dir() :
    print( 'Error: Content folder "{}" to copy from does not contain a Trainset sub-folder ({}).'.format(contentPath.name, fromTrainsetDirPath), file=sys.stderr)
    sys.exit(1)

print( 'Info: copying trains (consists, trainset folders) for route "{}" from content folder "{}".'.format( routePath, contentPath), file=sys.stderr)

# for each service in the services folder
for serviceFilePath in servicesDirPath.glob('*.srv') :
    if (verbose > 1) : print( 'Info: processing Service "{}", file "{}".'.format( serviceFilePath.name, serviceFilePath), file=sys.stderr)
    srvText = readFile(serviceFilePath)
    match = consistPattern.search(srvText)
    if not match or match.lastindex < 1 :
        print('Warning: No train config found in Service "{}".'.format( serviceFilePath), file=sys.stderr)
        continue
    consistFileName = match.group(1).strip().strip('\"') + '.con'
    consistFromPath = fromConsistsDirPath / consistFileName
    if not consistFromPath.exists() :
        print( 'Error: Consist "{}" from service "{}" does not exist ({}).'.format(consistFromPath.name, serviceFilePath, consistFromPath), file=sys.stderr)
        continue
    consistToPath = toConsistsDirPath / consistFileName
    if consistToPath.exists() :
        if verbose > 1 : print( 'Info: Consist "{}" from Service "{}" already exists - skipping it.'.format(consistToPath.name, serviceFilePath), file=sys.stderr)
        continue
    if verbose > 0 : print( 'Info: copying Consist "{}" from "{}" to "{}".'.format(consistFileName, consistFromPath, consistToPath), file=sys.stderr)
    shutil.copy2(consistFromPath, consistToPath)
    numConsists += 1

    # for each wagon or engine in the consist file
    conText = readFile(consistFromPath)
    matchList = trainsetPattern.finditer( conText)
    if matchList is None :
        print('Warn: No Engines or Wagons found in Consist "{}".'.format(consistFromPath), file=sys.stderr)
        continue
    for match in matchList :
        if match.lastindex < 3 :
            print('Warning: Unable to parse line "{}" in Consist "{}".'.format(match.group(0), consistFromPath), file=sys.stderr)
            continue
        dirName = match.group(3).strip().strip('\"')
        trainsetFromPath = fromTrainsetDirPath / dirName
        if not trainsetFromPath.exists():
            print('Error: Trainset folder "{}" from consist "{}" does not exist ({}).'.format(trainsetFromPath.name, consistFileName, trainsetFromPath), file=sys.stderr)
            continue
        trainsetToPath = toTrainsetDirPath / dirName
        if trainsetToPath.exists():
            if verbose > 1 : print( 'Info: Trainset "{}" from Consist "{}" already exists - skipping it.'.format(trainsetToPath.name, consistFileName), file=sys.stderr)
            continue
        if verbose > 0: print('Info: copying Trainset "{}" from "{}" to "{}".'.format(dirName, consistFromPath, consistToPath), file=sys.stderr)
        shutil.copytree(trainsetFromPath, trainsetToPath)
        numTrainset += 1

print( 'Sum: copied {} Consists and {} Trainsets folders.'.format( numConsists, numTrainset), file=sys.stderr)
exit(0)
