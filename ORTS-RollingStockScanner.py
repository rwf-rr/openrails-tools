#!/usr/bin/env python3
# ORTS-RollingStockScanner - search for eng and wag files and list key properties in CSV format
#
# Copyright (c) 2024 Roger Fischer. MIT License.
#
# Some of the more challengin tokens:
# - Mass ( "56.163t  #23.186t empty, 90.163t full" )  --  comment inside quotes
# - Name ( "BNSF SD70ACe #8490" )  -- not a comment
# - DerailRailForce ( "2.5m/(s^2)*64t" )  -- non-trivial math
#

import argparse
import pathlib
import re
import sys

# global variables
numEng = numWag = numWarn = 0
heading = None


### get the content (package) directory, the one above TRAINS
def getContentDir( filePath) :
    TRAINS = "TRAINS".casefold()
    absPath = filePath.resolve()
    for i in range(len(absPath.parents)) :
        if absPath.parents[i].name.casefold() == TRAINS and i + 1 < len(absPath.parents) :
            return absPath.parents[i+1].name
    return None


### read a file that is either utf-16 or utf8
def readFile( filePath) :
    enc = "utf-16"
    bytes = filePath.read_bytes()
    if 0 < bytes[0] < 128: enc = 'utf-8'
    return bytes.decode(encoding = enc, errors = 'replace' )


#### read the eng or wag file and resolve includes
def readTrainsetFile(filePath, refDir) :
    txt = readFile(filePath)  # .replace('\n', ' ').replace('\r', '')
    # resolve includes
    ml = re.finditer( 'include\\s*\\(([^)]+)\\)', txt, flags=re.IGNORECASE)
    for m in ml :
        incPathName = m.group(1).strip().strip('"')
        incPath = pathlib.Path(refDir, incPathName).resolve()
        incTxt = readFile(incPath)
        txt = txt.replace(m.group(0), incTxt, 1)
    return txt


### get value for a token; exclude quotes
### is incorrect for nested tokens; stops at the closing parenthesis of a nested token
def getValue( token, txt) :
    value = ''
    start = 0 ; end = 0
    startPat = token + '\\s*\\(\\s*.' ; endPat = '\\s*\\)'
    m = re.search(startPat, txt, flags=re.IGNORECASE)  # find opening parenthesis
    if m :
        start = m.end() - 1
        if txt[start] == '"' :
            start += 1
            endPat = '"\\s*\\)'
        m = re.search(endPat, txt[start:], flags=re.IGNORECASE)  # find closing parenthesis
        if m :
            end = start + m.start()
            value = txt[start:end]
    return value


### parse eng or wag file and collect relevant data
def processFile(values, txt, filePath, isEngine) :
    global numWarn

    # separate the wagon and engin parts; assumes that wagon is always first
    wagTxt = txt ; engTxt = ""
    if isEngine :
        m = re.search('Engine\\s*\\(\\s*', txt, flags=re.IGNORECASE)
        if m :
            engOffset = m.start() ; engTxt = txt[engOffset:] ; wagTxt = txt[:engOffset]
        else :
            numWarn += 1
            print("Warning: Unable to find engine section in", filePath, file=sys.stderr)

    # get wagon name, engine name; nested token, cannot use getValue()
    name = 'Name' ; values[name] = '_'
    m = re.search('Wagon\\s*\\(\\s*"?(\\w+)"?', txt, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 : values[name] = m.group(1)
    elif not isEngine :
        numWarn += 1
        print("Warning: Unable to find wagon name in", filePath, file=sys.stderr)
    if isEngine :
        m = re.search('Engine\\s*\\(\\s*"?(\\w+)"?', txt, flags=re.IGNORECASE)
        if m is None or m.lastindex < 1 :
            numWarn += 1
            print("Warning: Unable to find engine name in", filePath, file=sys.stderr)
        elif not values[name] :
            values[name] = m.group(1)
            numWarn += 1
            print("Warning: Unable to find wagon name (using engine name) in", filePath, file=sys.stderr)
        elif values[name] != m.group(1) :
            numWarn += 1
            print("Warning: Wagon name ({}) does not match engine name ({}) in {}".format(values[name], m.group(1), filePath), file=sys.stderr)

    # display name, may contain spaces, may be quoted; either in wagon or engine section
    name = 'DispName' ; values[name] = '_'
    val = getValue('Name', txt)
    if val : values[name] = val.strip()
    else :
        values[name] = values['Name'] + ' (dflt)'  # default to name in Engine or Wagon token
        if verbose > 0 : print("Info: Unable to find wagon or engine display name in", filePath, file=sys.stderr)

    # wagon type (engine, freight, passenger, etc)
    name = 'Type' ; values[name] = '_'
    val = getValue('Type', wagTxt)
    m = re.search('\\s*(\\w+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 : values[name] = m.group(1)
    else :
        numWarn += 1
        print("Warning: Unable to find wagon type in", filePath, file=sys.stderr)

    # engine type (diesel, electric, steam, etc)
    name = 'SubType' ; values[name] = '_'
    if isEngine :
        val = getValue('Type', engTxt)
        m = re.search('\\s*(\\w+)\\s*', val, flags=re.IGNORECASE)
        if m and m.lastindex >= 1 : values[name] = m.group(1)
        else :
            numWarn += 1
            print("Warning: Unable to find engine type in", filePath, file=sys.stderr)

    # engine max velocity
    name = 'MaxSpeed' ; values[name] = '_'
    if isEngine :
        val = getValue('MaxVelocity', engTxt)
        m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
        if m and m.lastindex >= 1 : values[name]  = m.group(1)
        else :
            numWarn += 1
            print("Warning: Unable to find engine max velocity in", filePath, file=sys.stderr)

    # engine max power
    name = 'MaxPower' ; values[name] = '_'
    if isEngine :
        val = getValue('MaximalPower', engTxt)
        m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
        if m and m.lastindex >= 1 : values[name] = "OR " + m.group(1)
        else :
            val = getValue('MaxPower', engTxt)
            m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
            if m and m.lastindex >= 1 : values[name] = m.group(1)
            else :
                numWarn += 1
                print("Warning: Unable to find engine max power in", filePath, file=sys.stderr)

    # engine max force
    name = 'MaxForce' ; values[name] = '_'
    if isEngine :
        val = getValue('MaxForce', engTxt)
        m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
        if m and m.lastindex >= 1 : values[name] = m.group(1)
        else :
            numWarn += 1
            print("Warning: Unable to find engine max force in", filePath, file=sys.stderr)

    # max brake force
    name = 'MaxBrakeForce' ; values[name] = '_'
    val = getValue('MaxBrakeForce', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 : values[name] = m.group(1)
    else :
        numWarn += 1
        print("Warning: Unable to find wagon max brake force in", filePath, file=sys.stderr)

    # weight
    name = 'Weight' ; values[name] = '_'
    val = getValue( 'Mass', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*^()]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 : values[name] = m.group(1)
    else :
        numWarn += 1
        print("Warning: Unable to find wagon weight in", filePath, file=sys.stderr)

    # length, third value
    name = 'Length' ; values[name] = '_'
    val = getValue( 'Size', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 3 : values[name] = m.group(3)
    else :
        numWarn += 1
        print("Warning: Unable to find wagon size in", filePath, file=sys.stderr)

    # number of wheels or axles (OR), wagon and engine; has ORTS variants
    name = 'Wheels/Axles' ; values[name] = '_'
    val = getValue( 'ORTSNumberAxles', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 :
        values[name] = "OR " + m.group(1)
        if isEngine:
            val = getValue('ORTSNumberDriveAxles', engTxt)
            m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
            if m and m.lastindex >= 1 : values[name] += " | " + m.group(1)
            else :
                numWarn += 1
                print("Warning: Unable to find engine ORTS number of wheels in", filePath, file=sys.stderr)
    else :
        val = getValue('NumWheels', wagTxt)
        m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
        if m and m.lastindex >= 1 :
            values[name] = m.group(1)
            if isEngine:
                val = getValue('NumWheels', engTxt)
                m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
                if m and m.lastindex >= 1: values[name] += " | " + m.group(1)
                else :
                    numWarn += 1
                    print("Warning: Unable to find engine number of wheels in", filePath, file=sys.stderr)
        else :
            numWarn += 1
            print("Warning: Unable to find wagon number of wheels in", filePath, file=sys.stderr)

    # coupler strength, may occur twice, use second value of each occurrence
    name = 'CouplerStrength' ; values[name] = '_'
    first = re.search( 'Coupling\\s*\\(', wagTxt, flags=re.IGNORECASE)
    if not first :
        numWarn += 1
        print("Warning: Unable to find wagon coupler section in", filePath, file=sys.stderr)
    else :
        val = getValue('Break', wagTxt[first.start():])
        m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
        if not m or m.lastindex < 2 :
            numWarn += 1
            print("Warning: Unable to find wagon coupler strength in", filePath, file=sys.stderr)
        else :
            values[name] = m.group(2)
            # look for optional second section
            second = re.search( 'Coupling\\s*\\(', wagTxt[first.end():], flags=re.IGNORECASE)
            if not second :
                if verbose > 0 : print("Info: no second coupler section in", filePath, file=sys.stderr)
            else :
                val = getValue('Break', wagTxt[second.start():])  # search for second block
                m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
                if not m or m.lastindex < 2 :
                    numWarn += 1
                    print("Warning: Unable to find wagon second coupler strength in", filePath, file=sys.stderr)
                else :
                    values[name] += " | " + m.group(2)

    # friction, using the first 5 values only; has ORTS variant
    name = 'Friction' ; values[name] = '_'
    val = getValue( 'ORTSDavis_A', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 :
        values[name] = "OR " + m.group(1)
        val = getValue('ORTSDavis_B', wagTxt)
        m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
        if m and m.lastindex >= 1:
            values[name] += " | " + m.group(1)
            val = getValue('ORTSDavis_C', wagTxt)
            m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
            if m and m.lastindex >= 1:
                values[name] += " | " + m.group(1)
    else :
        val = getValue('Friction', wagTxt)
        m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+', val, flags=re.IGNORECASE)
        if m and m.lastindex >= 5 :
            values[name] = m.group(1) + " | " + m.group(2) + " | " + m.group(3) + " | " + m.group(4) + " | " + m.group(5)
        else :
            numWarn += 1
            print("Warning: Unable to find wagon friction values in", filePath, file=sys.stderr)

    # adhesion, 3 values; has ORTS variant; is in wagon section, but only used for engines
    name = 'Adhesion' ; values[name] = '_'
    val = getValue( 'ORTSCurtius_Kniffler', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 4 :
        values[name] = "OR " + m.group(1) + " | " + m.group(2) + " | " + m.group(3) + " | " + m.group(4)
    else :
        val2 = getValue('Adheasion', wagTxt)
        m2 = re.search('\\s*([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+([-+0-9.,a-z/*"]+)\\s+', val2, flags=re.IGNORECASE)
        if m2 and m2.lastindex >= 3 : values[name] = m2.group(1) + " | " + m2.group(2) + " | " + m2.group(3)
        elif isEngine :
            numWarn += 1
            print("Warning: Unable to find wagon adhesion values in", filePath, file=sys.stderr)

    # derail rail force
    name = "DerailRailForce" ; values[name] = '_'
    val = getValue('DerailRailForce', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*^()]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 : values[name] = m.group(1)
    else :
        numWarn += 1
        print("Warning: Unable to find wagon derail rail force in", filePath, file=sys.stderr)

    # derail buffer force
    name = 'DerailBufferForce' ; values[name] = '_'
    val = getValue('DerailBufferForce', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z/*"]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 : values[name] = m.group(1)
    else :
        numWarn += 1
        print("Warning: Unable to find wagon derail buffer force in", filePath, file=sys.stderr)

    # length including couplers ORTS only
    name = 'TotalLength' ; values[name] = '_'
    val = getValue('ORTSLengthCouplerFace', wagTxt)
    m = re.search('\\s*([-+0-9.,a-z /*"]+)\\s*', val, flags=re.IGNORECASE)
    if m and m.lastindex >= 1 : values[name] = m.group(1)

    return


### process a path
def processPath( path, isEngine) :
    global heading, numWarn
    rowValues = {}
    packageName = getContentDir( path)
    if not packageName :
        print("Warning: ignoring {}, could not find package name".format(path), file=sys.stderr)
        numWarn += 1
        return  # do not process files outside the TRAINS directory
    rowValues["Package"] = packageName
    rowValues["Directory"] = path.parent.name
    rowValues["File"] = path.name
    text = readTrainsetFile(path, path.parent)
    processFile(rowValues, text, path, isEngine)
    if heading is None :
        heading = rowValues.keys()
        print(*heading, sep=',')
    print( *rowValues.values(), sep=',')
    return


### main
parser = argparse.ArgumentParser()
parser.add_argument('dirPath', type=pathlib.Path, help='Directory where to search for eng and wag files.')
parser.add_argument('-f', '--filter',
                    help='Optional filter. "eng" limits to engines, "wag" limits to wagons, any other value is matched to the file name')
parser.add_argument('-v', '--verbose', action='count', default=0)
args = parser.parse_args()
dirPath = args.dirPath
filter = args.filter
verbose = args.verbose

if not dirPath.is_dir() :
    print( "Error: {} is not a directory.".format(args.dirPath), file=sys.stderr)
    sys.exit(1)

doEng = doWag = True
pattern = None
if filter == 'wag' : doEng = False
elif filter == 'eng' : doWag = False
elif filter : pattern = re.compile(filter, flags=re.IGNORECASE)

# process engine files
if doEng :
    for path in dirPath.rglob( "*.eng") :
        if pattern and not pattern.search(path.name) : continue
        if verbose > 1 : print( "...processing engine ", path, file=sys.stderr)
        numEng += 1
        processPath( path, True)

# process wagon files
if doWag :
    for path in dirPath.rglob( "*.wag") :
        if pattern and not pattern.search(path.name) : continue
        elif path.name == 'default.wag' : continue
        if verbose > 1 : print( "...processing wagon ", path, file=sys.stderr)
        numWag += 1
        processPath( path, False)

print( "Processed {} Eng and {} Wag files, total {}; generated {} warnings".format( numEng, numWag, numEng + numWag, numWarn), file=sys.stderr)
exit(0)
