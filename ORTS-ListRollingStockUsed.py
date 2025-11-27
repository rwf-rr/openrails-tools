#!/usr/bin/env python3
# ORTS-ListRollingStockUsed - list the rolling stock that a route uses
#
# Copyright (c) 2025 Roger Fischer. MIT License.
#

import argparse
import pathlib
import re
import sys


### get the root path, content dir, and route dir
def getContextDirs(filePath) :
    absPath = filePath.resolve()
    for i in range(len(absPath.parents)) :
        if absPath.parents[i].name.casefold() == 'ROUTES'.casefold() and i + 1 < len(absPath.parents) :
            return absPath.parents[i+1], absPath.parents[i+1].name, absPath.parents[i-1].name
    return None


### read a file that is either utf-16 or utf8
def readFile( filePath) :
    enc = "utf-16"
    bytes = filePath.read_bytes()
    if 0 < bytes[0] < 128: enc = 'utf-8'
    return bytes.decode(encoding = enc, errors = 'replace' )


### main
parser = argparse.ArgumentParser(description='Scan Services files and list the Engines and Wagons used.')
parser.add_argument('dirPath', type=pathlib.Path, help='Folder where to search for services. Should be a specific route or the ROUTES folder.')
parser.add_argument('-f', '--filter', help='Optional filter. "eng" limits to engines, "wag" limits to wagons.')
parser.add_argument('-v', '--verbose', action='count', default=0)
args = parser.parse_args()
dirPath = args.dirPath
filter = args.filter
verbose = args.verbose

if not dirPath.is_dir() :
    print( "Error: {} is not a directory.".format(args.dirPath), file=sys.stderr)
    sys.exit(1)

numSrv = numCon = numEng = numWag = numWarn = 0
processedConsistList = processedEngineList = processedWagonList = []  # list of already processed objects

doEng = doWag = True
if filter == 'wag' : doEng = False
elif filter == 'eng' : doWag = False

# for each service file
for servicePath in dirPath.rglob("*.srv") :
    if verbose > 0 : print('Info: service', str(servicePath), file=sys.stderr)

    # find reference to consist file
    serviceText = readFile(servicePath)
    m = re.search('Train_Config\\s*\\(\\s*"([^"]+)"\\s*\\)', serviceText, flags=re.IGNORECASE)
    if not m or m.lastindex < 1 :
        m = re.search('Train_Config\\s*\\(\\s*([^)#(]+)\\s*\\)', serviceText, flags=re.IGNORECASE)
    if not m or m.lastindex < 1 :
        print("Warning: Unable to find consist name in", servicePath, file=sys.stderr)
        numWarn += 1
        continue
    consistFileName = m.group(1).strip().strip('"')
    numSrv += 1

    rootPath, contentDir, routeDir = getContextDirs(servicePath)
    consistPath = pathlib.Path(f'{rootPath}\\TRAINS\\CONSISTS\\{consistFileName}.con')

    # skip already processed consist
    if str(consistPath) in processedConsistList :
        continue
    if verbose > 0 : print('Info: unique consist', str(consistPath), file=sys.stderr)

    consistText = readFile(consistPath)
    processedConsistList.append(str(consistPath))
    numCon += 1

    # does not work, parsing is more complex
    engMatchList = re.findall('EngineData\\s*\\(\\s*([^)#(]+)\\s+([^)#(]+)\\s*\\)', consistText, flags=re.IGNORECASE)
    wagMatchList = re.findall('WagonData\\s*\\(\\s*([^)#(]+)\\s+([^)#(]+)\\s*\\)', consistText, flags=re.IGNORECASE)
    if (not engMatchList or len(engMatchList) < 1) and (not wagMatchList or len(wagMatchList) < 1) :
        print("Warning: No engines or wagons found in consist", consistPath, file=sys.stderr)
        numWarn += 1
        continue

    if doEng :
        for fileName, dirName in engMatchList :
            fileName = fileName.strip().strip('"') ; dirName = dirName.strip().strip('"')
            engPath = pathlib.Path(f'{rootPath}\\TRAINS\\TRAINSET\\{dirName}\\{fileName}.eng')
            if not engPath.is_file() :
                print('Warning: Engine file does not exist: ', engPath, file=sys.stderr)
                numWarn += 1
            elif str(engPath) in processedEngineList :
                # engine already processed
                continue
            else :
                print(f'Engine,"{contentDir}","{dirName}","{fileName}.eng","{engPath}"', flush=True)
                processedEngineList.append(str(engPath))
                numEng += 1

    if doWag :
        for fileName, dirName in wagMatchList :
            fileName = fileName.strip().strip('"') ; dirName = dirName.strip().strip('"')
            wagPath = pathlib.Path(f'{rootPath}\\TRAINS\\TRAINSET\\{dirName}\\{fileName}.wag')
            if not wagPath.is_file() :
                print('Warning: Wagon file does not exist: ', wagPath, file=sys.stderr)
                numWarn += 1
            elif str(wagPath) in processedWagonList:
                # wagon already processed
                continue
            else :
                print(f'Wagon,"{contentDir}","{dirName}","{fileName}.eng","{wagPath}"', flush=True)
                processedWagonList.append(str(wagPath))
                numWag += 1

print( "Processed {} Eng and {} Wag files, total {}; generated {} warnings; from {} consists, {} services.".format(
       numEng, numWag, numEng + numWag, numWarn, numCon, numSrv), file=sys.stderr)
exit(0)
