#!/usr/bin/env python3
# ORTS-ShowRollingStockFile - output an eng and wag file in UTF-8, resolving includes
#
# Copyright (c) 2024 Roger Fischer. MIT License.
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
    return bytes.decode(encoding = enc, errors = 'replace' )


#### read the eng or wag file and resolve includes
def readTrainsetFile(filePath, refDir) :
    txt = readFile(filePath)
    # resolve includes
    ml = re.finditer( 'include\\s*\\(([^)]+)\\)', txt, flags=re.IGNORECASE)
    for m in ml :
        incPathName = m.group(1).strip().strip('"')
        incPath = pathlib.Path(refDir, incPathName).resolve()
        incTxt = readFile(incPath)
        txt = txt.replace(m.group(0), incTxt, 1)
    return txt


### main
parser = argparse.ArgumentParser()
parser.add_argument('filePath', type=pathlib.Path, help='File (eng or wag) to list.')
args = parser.parse_args()
filePath = args.filePath

if not filePath.is_file() :
    print( "Error: {} is not a file. A single .eng or .wag file is required.".format(filePath), file=sys.stderr)
    sys.exit(1)

if filePath.suffix != '.eng' and filePath.suffix != '.wag' :
    print("Warning: {} is not an engine or wagon file.".format(filePath), file=sys.stderr)
    if input('Do you want to continue? (y/n) ') != 'y': exit(0)

text = readTrainsetFile(filePath, filePath.parent)

numLines = 0
for line in text.splitlines() :
    print( line)
    numLines += 1

print( numLines, 'lines in expanded file ', filePath, file=sys.stderr)

exit(0)
