#!/usr/bin/env python3
# ORTS-ListTrackUsed - list the tracks that a route uses
#
# Parse the <route>.tdb file for track and reference the tsection.dat file
#
# Copyright (c) 2026 Roger Fischer. MIT License.
#

import argparse
import pathlib
import math
import re
import sys

APPROX_SECTION_LEN = 200   # bigger than the longest section block
APPROX_SHAPE_LEN = 500   # bigger than the longest shape block

track_section_authors = []
track_sections = {}

num_warn = 0


### read a file that is either utf-16 or utf8
def read_file(file_path) :
    enc = "utf-16"
    bytes = file_path.read_bytes()
    if 0 < bytes[0] < 128: enc = 'utf-8'
    return bytes.decode(encoding=enc, errors='replace')


### get author of a track section
def get_author( author_list, section_idx) :
    # this needs to be optimized
    for item in author_list :
        if section_idx >= item[0] and section_idx <= item[1] :
            return item[2]
    return '__not-found__'


### Parse the tsection.dat file and build a dictionary of track sections
def process_tsection_file(ts_file_path) :
    global track_section_authors, track_sections, num_warn
    new_pos = 6750   # approx end of explanatory section in early versions of tsection.day

    ts_text = read_file(ts_file_path)

    # first get the author of the track sections from eg.
    # Sections     0-  332  original MS/KUJU sections
    matches = re.finditer('^Sections\\s+(\\d+)(.*)$', ts_text, flags=re.IGNORECASE | re.MULTILINE)
    if not matches :
        print('Error: Unable to find "Sections <n1>-<n2> <author>" lines in "{}"'.format(ts_file_path), file=sys.stderr)
        return
    for match in matches :
        start_num = int(match.group(1))
        end_num = -1
        author = '__none__'
        text = match.group(2).strip()
        if not text.startswith('-') :
            end_num = int(match.group(1))
            author = match.group(2).strip()
        else :
            m2 = re.search('-\\s*(\\d+)\\s+(.*)', text, flags=re.IGNORECASE)
            if not m2 or m2.lastindex < 2 :
                if verbose > 1 : print('Warning: Unable to find end-number and author in "{}"'.format(text), file=sys.stderr)
                num_warn += 1
                end_num = start_num
                author = '__not-found__'
            else :
                end_num = int(m2.group(1))
                author = m2.group(2)
        new_pos = match.end()
        track_section_authors.append((start_num, end_num, author))
    if verbose > 0 : print('Info: {} track section authors found'.format(len(track_section_authors)), file=sys.stderr)

    # then get the track sections, eg
    # TrackSection ( 39843
    #  SectionSize ( 1.5 0 )
    #  SectionCurve ( 8000.0 5 )
    # )
    num_ts = 0
    sections_text = ts_text[new_pos:]
    matches = re.finditer('^TrackSection\\s+\\(\\s+(\\d+)\\s*', sections_text, flags=re.IGNORECASE | re.MULTILINE)
    for match in matches :
        section_idx = int(match.group(1))
        author = get_author(track_section_authors, section_idx)
        track_sections[section_idx] = {'Author': author}
        new_pos = match.end()

        gauge_m = size_m = radius_m = -0.1 ; angle_d = skew_d = 0.0
        length_found = curve_found = skew_found = False
        for _ in range(3) :   # at most SectionSize, SectionCurve and SectionSkew, although curve and skew seem exclusive
            # get next token, should be SectionSize or SectionCurve
            next_text = sections_text[new_pos:new_pos+200]
            if next_text.lstrip()[0] == ')' :
                break   # end of TrackSection
            m = re.search('\\s*(\\S+)\\s+\\(', next_text[:30])
            if not m or m.lastindex < 1 :
                if verbose > 1 : print('Warning: Unable to find token after TrackSection for index {} in string "{}"'.format(section_idx, next_text), file=sys.stderr)
                num_warn += 1
                break
            elif m.group(1) == 'SectionSize' :
                m = re.search('SectionSize\\s+\\(\\s+(\\S+)\\s+(\\S+)\\s+\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 2 :
                    if verbose > 1 : print('Warning: Unable to find gauge and length in Track Section with index {} and string "{}"'.format(section_idx, next_text), file=sys.stderr)
                    num_warn += 1
                    break
                else :
                    length_found = True
                    gauge_m = float(m.group(1))
                    size_m = float(m.group(2))
                    new_pos += m.end()
            elif m.group(1) == 'SectionCurve' :
                m = re.search('SectionCurve\\s+\\(\\s+(\\S+)\\s+(\\S+)\\s+\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 2 :
                    if verbose > 1 : print('Warning: Unable to find radius and angle in Track Section with index {} and string "{}"'.format(section_idx, next_text), file=sys.stderr)
                    num_warn += 1
                    break
                else :
                    curve_found = True
                    radius_m = float(m.group(1))
                    angle_d = float(m.group(2))
                    new_pos += m.end()
            elif m.group(1) == 'SectionSkew' :
                m = re.search('SectionSkew\\s+\\(\\s+(\\S+)\\s+\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 1 :
                    if verbose > 1 : print('Warning: Unable to find skew in Track Section with index {} and string "{}"'.format(section_idx, next_text), file=sys.stderr)
                    num_warn += 1
                    break
                else :
                    skew_found = True
                    skew_d = float(m.group(1))
                    new_pos += m.end()
            else :
                if verbose > 1: print('Warning: Unexpected token "{}" in Track Section with index {} and string "{}"'.format(m.group(1), section_idx, next_text), file=sys.stderr)
                num_warn += 1
                break

        if length_found :
            track_sections[section_idx]['Gauge [m]'] = '{:.2f}'.format(gauge_m)
            track_sections[section_idx]['Gauge [ft]'] = '{:.2f}'.format(gauge_m * 3.28084)
            if curve_found :
                if angle_d < 0 : track_sections[section_idx]['Type'] = 'curved-left'
                else : track_sections[section_idx]['Type'] = 'curved-left'
                track_length = math.fabs(radius_m * math.radians(angle_d))
                track_sections[section_idx]['Length [m]'] = '{:.2f}'.format(track_length)
                track_sections[section_idx]['Length [ft]'] = '{:.2f}'.format(track_length * 3.28084)
            else :
                track_sections[section_idx]['Type'] = 'straight'
                track_sections[section_idx]['Length [m]'] = '{:.2f}'.format(size_m)
                track_sections[section_idx]['Length [ft]'] = '{:.2f}'.format(size_m * 3.28084)
            if skew_found :
                track_sections[section_idx]['Skew'] = '{:.2f}'.format(skew_d)
            num_ts += 1
        else :
            if verbose > 1: print('Warning: Neither SectionSize nor SectionCurve found Track Section with index {} and string "{}"'.format(m.group(1), section_idx, next_text), file=sys.stderr)
            num_warn += 1
            continue

        if verbose > 2 : print('Info: Added Track Section', track_sections[section_idx])

    if verbose > 0 : print('Info: {} track sections found, {} track sections added'.format(num_ts, len(track_sections)), file=sys.stderr)


    # lastly get the track shapes

    print( num_ts, 'Track Sections;', len(track_sections), ' TS in dictionary;', num_warn, 'warnings', file=sys.stderr)

    return




### main
parser = argparse.ArgumentParser(description='List the track sections used by a route.')
parser.add_argument('-v', '--verbose', action='count', default=0, help='Be more verbose. Option may be repeated.')
parser.add_argument('-ts', '--tsection-path', type=pathlib.Path, help='Use the specified tsection.dat file, instead of the route\'s.')
parser.add_argument('tdb_path', type=pathlib.Path, help='The path to the route\'s track database (.tdb file).')
args = parser.parse_args()
verbose = args.verbose
tsection_path = args.tsection_path
tdb_path = args.tdb_path

if not tdb_path.is_file() :
    print( 'Error: track database file "{}" does not exist.'.format(tdb_path), file=sys.stderr)
    sys.exit(1)

if not tsection_path :
    tsection_path = pathlib.Path(tdb_path.resolve().parent / '../../global/tsection.dat').resolve()
if verbose > 0 : print('Info: using track section file "{}"'.format(tsection_path), file=sys.stderr)
if not tsection_path.is_file() :
    print( 'Error: track sections file "{}" does not exist.'.format(tsection_path), file=sys.stderr)
    sys.exit(1)

process_tsection_file(tsection_path)




exit(0)