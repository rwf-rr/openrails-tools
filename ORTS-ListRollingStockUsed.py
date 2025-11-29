#!/usr/bin/env python3
# ORTS-ListRollingStockUsed - list the rolling stock that a route uses
#
# Copyright (c) 2025 Roger Fischer. MIT License.
#

import argparse
import pathlib
import re
import sys


### read a file that is either utf-16 or utf8
def readFile( filePath) :
    enc = "utf-16"
    bytes = filePath.read_bytes()
    if 0 < bytes[0] < 128: enc = 'utf-8'
    return bytes.decode(encoding=enc, errors='replace')


### get the root path (where ROUTES and TRAINS resides)
def getRootPath(filePath) :
    absPath = filePath.resolve()
    if (absPath / 'ROUTES').is_dir() :
        return absPath
    elif absPath.name.casefold() == 'ROUTES'.casefold() :
        return absPath.parent
    else :
        for i in range(len(absPath.parents)) :
            if absPath.parents[i].name.casefold() == 'ROUTES'.casefold() :
                return absPath.parents[i+1]
    return None


### get the root path, content dir, and route dir
def getContextDirs(filePath) :
    absPath = filePath.resolve()
    for i in range(len(absPath.parents)) :
        if absPath.parents[i].name.casefold() == 'ROUTES'.casefold() and i + 1 < len(absPath.parents) :
            return absPath.parents[i+1], absPath.parents[i+1].name, absPath.parents[i-1].name
    return None


### get file name and dir name from EngineData or WagonData value
def getFileAndDirNames(engOrWagData) :
    filename = dirname = None ; valremain = ''
    val = engOrWagData.strip()
    vallist = val.split(maxsplit=5)  # we want to know if there are more than 3 words (not counting the closing parenthesis)
    if len(vallist) == 2 :
        return vallist[0].strip('"'), vallist[1].strip('"')
    if val.startswith('"') :
        m1 = re.search('"([^"]+)"', val)
        if m1 and m1.lastindex == 1 :
            filename = m1.group(1)
        valremain = val[m1.end() + 1:]
    else :
        filename, valremain = val.split(maxsplit=1)
    if valremain.startswith('"') :
        m2 = re.search('"([^"]+)"', valremain)
        if m2 and m2.lastindex == 1 :
            dirname = m2.group(1)
    else :
        dirname, valremain = valremain.split(maxsplit=1)
    return filename, dirname


### main
parser = argparse.ArgumentParser(description='Scan Services files and list the Engines and Wagons used.')
parser.add_argument('dirPath', type=pathlib.Path, help='Folder where to search for services. Should be a specific route or the ROUTES folder.')
parser.add_argument('-f', '--filter', help='Optional filter. "eng" limits to engines, "wag" limits to wagons.')
parser.add_argument('-a', '--all', action='store_true', help='Also include Engines and Wagons not used by activites (services).')
parser.add_argument('-v', '--verbose', action='count', default=0)
args = parser.parse_args()
dirPath = args.dirPath
filter = args.filter
includeNotUsed = args.all
verbose = args.verbose

if not dirPath.is_dir() :
    print( "Error: {} is not a directory.".format(args.dirPath), file=sys.stderr)
    sys.exit(1)

numSrv = numCon = numEng = numWag = numUnusedCon = numUnusedEng = numUnusedWag = numWarn = 0
processedConsistList = processedEngineList = processedWagonList = []  # list of already processed objects

doEng = doWag = True
if not includeNotUsed and filter == 'wag' : doEng = False
elif not includeNotUsed and filter == 'eng' : doWag = False

# header row
print('Type,ContentDir,DirName,FileName, Path', flush=True)

# for each service file
for servicePath in dirPath.rglob("*.srv") :
    if verbose > 0 : print('Info: service', servicePath, file=sys.stderr)

    # find reference to consist file
    serviceText = readFile(servicePath)
    m = re.search('Train_Config\\s*\\(\\s*"([^"]+)"\\s*\\)', serviceText, flags=re.IGNORECASE)
    if m and m.lastindex > 0 :
        consistFileName = m.group(1)
    else :
        m = re.search('Train_Config\\s*\\(\\s*([^)(]+)\\s*\\)', serviceText, flags=re.IGNORECASE)
        if m and m.lastindex > 0 :
            consistFileName = m.group(1).strip()
        else :
            print("Warning: Unable to find consist name in", servicePath, file=sys.stderr)
            numWarn += 1
            continue
    numSrv += 1

    rootPath, contentDir, routeDir = getContextDirs(servicePath)
    consistPath = pathlib.Path(f'{rootPath}\\TRAINS\\CONSISTS\\{consistFileName}.con')

    # skip already processed consist
    if str(consistPath) in processedConsistList :
        continue
    if verbose > 0 : print('Info: unique consist', consistPath, file=sys.stderr)

    if not consistPath.is_file() :
        print(f'Warning: Consist file does not exist: service {servicePath}; consist {consistPath}', file=sys.stderr)
        numWarn += 1
        continue

    print(f'Consist,"{contentDir}","","{consistFileName}.con","{consistPath}"', flush=True)
    consistText = readFile(consistPath)
    processedConsistList.append(str(consistPath))
    numCon += 1

    # simplification: assuming that the closing parenthesis is at the end of the line
    # ie. the two fields are not split over two lines, and there is no other keyword on the same line
    engMatchList = re.findall('EngineData\\s*\\(\\s*(.+)\\s*\\)\\s*$', consistText, flags=re.IGNORECASE|re.MULTILINE)
    wagMatchList = re.findall('WagonData\\s*\\(\\s*(.+)\\s*\\)\\s*$', consistText, flags=re.IGNORECASE|re.MULTILINE)
    if (not engMatchList or len(engMatchList) < 1) and (not wagMatchList or len(wagMatchList) < 1) :
        print("Warning: No engines or wagons found in consist", consistPath, file=sys.stderr)
        numWarn += 1
        continue

    if doEng and engMatchList :
        for match in engMatchList :
            fileName, dirName = getFileAndDirNames(match)
            if not fileName or not dirName :
                print(f'Warning: Failed to parse EngineData value for consist {consistPath}: value = >{match}<', file=sys.stderr)
                numWarn += 1
                continue
            engPath = pathlib.Path(f'{rootPath}\\TRAINS\\TRAINSET\\{dirName}\\{fileName}.eng')
            if str(engPath) in processedEngineList :
                # engine already processed
                continue
            if verbose > 0 : print('Info: unique engine', engPath, file=sys.stderr)
            if not engPath.is_file() :
                print(f'Warning: Engine file does not exist: consist {consistPath}; engine {engPath}', file=sys.stderr)
                numWarn += 1
            else :
                print(f'Engine,"{contentDir}","{dirName}","{fileName}.eng","{engPath}"', flush=True)
                processedEngineList.append(str(engPath))
                numEng += 1

    if doWag and wagMatchList :
        for match in wagMatchList :
            fileName, dirName = getFileAndDirNames(match)
            if not fileName or not dirName :
                print(f'Warning: Failed to parse WagonData value for consist {consistPath}: value = >{match}<', file=sys.stderr)
                numWarn += 1
                continue
            wagPath = pathlib.Path(f'{rootPath}\\TRAINS\\TRAINSET\\{dirName}\\{fileName}.wag')
            if str(wagPath) in processedWagonList:
                # wagon already processed
                continue
            if verbose > 0 : print('Info: unique wagon', wagPath, file=sys.stderr)
            if not wagPath.is_file() :
                print(f'Warning: Wagon file does not exist: consist {consistPath}; wagon {wagPath}', file=sys.stderr)
                numWarn += 1
            else :
                print(f'Wagon,"{contentDir}","{dirName}","{fileName}.wag","{wagPath}"', flush=True)
                processedWagonList.append(str(wagPath))
                numWag += 1
# end for each service

if includeNotUsed :
    rootPath = getRootPath(dirPath)
    if not rootPath :
        print('Warning: Unable to find root path in', dirPath, file=sys.stderr)
    else :

        # unused consists
        consistPath = rootPath / 'TRAINS' / 'CONSISTS'
        if not consistPath.is_dir() :
            print('Warning: Consist folder does not exist:', consistPath, file=sys.stderr)
        else :
            for conPath in consistPath.rglob("*.con") :
                if not str(conPath) in processedConsistList :
                    print(f'unused-Consist,"{rootPath.name}","","{conPath.name}","{conPath}"', flush=True)
                    numUnusedCon += 1

        # unused engines and wagons
        engWagPath = rootPath / 'TRAINS' / 'TRAINSET'
        if not engWagPath.is_dir() :
            print('Warning: Engine/Waggon folder does not exist:', engWagPath, file=sys.stderr)
        else :
            for engPath in engWagPath.rglob("*.eng") :
                if not str(engPath) in processedEngineList :
                    print(f'unused-Engine,"{rootPath.name}","{engPath.parent.name}","{engPath.name}","{engPath}"', flush=True)
                    numUnusedEng += 1
            for wagPath in engWagPath.rglob("*.wag") :
                if not str(wagPath) in processedWagonList :
                    print(f'unused-Wagon,"{rootPath.name}","{wagPath.parent.name}","{wagPath.name}","{wagPath}"', flush=True)
                    numUnusedWag += 1



print( "Processed {} Eng and {} Wag files, total {}; generated {} warnings; from {} consists, {} services.".format(
       numEng, numWag, numEng + numWag, numWarn, numCon, numSrv), file=sys.stderr)
if numUnusedCon > 0 or numUnusedEng > 0 or numUnusedWag > 0:
    print( f'Unused: {numUnusedCon} Consists, {numUnusedEng} Engines, {numUnusedWag} Wagons', file=sys.stderr)

exit(0)
