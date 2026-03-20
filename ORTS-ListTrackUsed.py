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

track_section_authors = []
track_shape_authors = []
track_sections = {}
track_shapes = {}



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


### Parse the tsection.dat file and build a dictionary of track sections and shapes
def process_tsection_file(ts_file_path) :
    global track_section_authors, track_sections, track_shape_authors, track_shapes, num_warn
    new_pos = 6750   # approx end of explanatory section in early versions of tsection.day

    ts_text = read_file(ts_file_path)

    # first get the author of the track sections from eg.
    # Sections     0-  332  original MS/KUJU sections
    num_warn = 0
    section_authors_text = ts_text
    matches = re.finditer('^Sections\\s+(\\d+)(.*)$', section_authors_text, flags=re.IGNORECASE | re.MULTILINE)
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

    if verbose > 0 : print('Info: {} track section authors found; {} warnings'.format(len(track_section_authors), num_warn), file=sys.stderr)

    # then get the track sections, eg
    # TrackSection ( 39843
    #  SectionSize ( 1.5 0 )
    #  SectionCurve ( 8000.0 5 )
    # )
    num_warn = 0
    num_sections = 0
    sections_text = section_authors_text[new_pos:]   # continue from where the section authors ended
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
            elif m.group(1).lower() == 'sectionsize' :
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
            elif m.group(1).lower() == 'sectioncurve' :
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
            elif m.group(1).lower() == 'sectionskew' :
                m = re.search('SectionSkew\\s+\\(\\s+(\\S+)\\s+\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 1 :
                    if verbose > 1 : print('Warning: Unable to find skew in Track Section with index {} and string "{}"'.format(section_idx, next_text), file=sys.stderr)
                    num_warn += 1
                    break
                else :
                    skew_found = True
                    skew_d = float(m.group(1))
                    new_pos += m.end()
            elif m.group(1).lower() == 'waterscoop':
                # ignore
                new_pos += m.end()
            else :
                if verbose > 1: print('Warning: Unexpected token "{}" in Track Section with index {} and string\n"{}"'.format(m.group(1), section_idx, match.group() + next_text), file=sys.stderr)
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
            num_sections += 1
        else :
            if verbose > 1: print('Warning: Neither SectionSize nor SectionCurve found in Track Section with index {}'.format(section_idx), file=sys.stderr)
            num_warn += 1
            continue

        if verbose > 2 : print('Info: Added Track Section', track_sections[section_idx])

    if verbose > 0 : print('Info: {} track sections found, {} track sections added; {} warnings'.format(num_sections, len(track_sections), num_warn), file=sys.stderr)
    # for tsection.dat #54, should be 7399, 0-39998
    section_labels = ['Type', '"Gauge [m]"', '"Length [m]"', ]
    if dump :
        for s in track_sections :
            print(s, track_sections[s], file=sys.stderr)

    # then get the author of the track shapes from eg.
    # Shapes   259-12219  presently not allocated
    num_warn = 0
    shape_authors_text = sections_text[new_pos:]   # continue from where the sections ended
    matches = re.finditer('^Shapes\\s+(\\d+)(.*)$', shape_authors_text, flags=re.IGNORECASE | re.MULTILINE)
    if not matches :
        print('Error: Unable to find "Shapes <n1>-<n2> <author>" lines in "{}"'.format(ts_file_path), file=sys.stderr)
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
        track_shape_authors.append((start_num, end_num, author))

    if verbose > 0 : print('Info: {} shape authors found; {} warnings'.format(len(track_shape_authors), num_warn), file=sys.stderr)

    # lastly get the track shapes, eg
    # TrackShape ( 0
    #  FileName ( A1t10mStrt.s )
    #  NumPaths ( 1 )
    #  SectionIdx ( 1 0 0 0 0 0 )
    #  ...
    # )
    num_warn = 0
    num_shapes = 0
    shapes_text = shape_authors_text[new_pos:]   # continue from where the shape authors ended
    matches = re.finditer('^TrackShape\\s+\\(\\s+(\\d+)\\s*', shapes_text, flags=re.IGNORECASE | re.MULTILINE)
    for match in matches :
        shape_idx = int(match.group(1))
        author = get_author(track_shape_authors, shape_idx)
        track_shapes[shape_idx] = {'Author': author}
        new_pos = match.end()
        filename = '' ; numpaths = 0 ; section_indices = []
        filename_found = numpaths_found = False
        for _ in range(3) :   # at most SectionSize, SectionCurve and SectionSkew, although curve and skew seem exclusive
            # get next token, should be SectionSize or SectionCurve
            next_text = shapes_text[new_pos:new_pos+200]
            if next_text.lstrip()[0] == ')' :
                break   # end of TrackShape
            m = re.search('\\s*(\\S+)\\s+\\(', next_text[:30])
            if not m or m.lastindex < 1 :
                if verbose > 1 : print('Warning: Unable to find token after Track Shape for index {} in string "{}"'.format(shape_idx, next_text), file=sys.stderr)
                num_warn += 1
                break
            elif m.group(1).lower() == 'filename' :
                m = re.search('FileName\\s+\\(\\s+(\\S+)\\s+\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 1 :
                    if verbose > 1 : print('Warning: Unable to find filename in Track Shape with index {} and string "{}"'.format(shape_idx, next_text), file=sys.stderr)
                    num_warn += 1
                    break
                else :
                    filename_found = True
                    filename = m.group(1)
                    new_pos += m.end()
            elif m.group(1).lower() == 'numpaths' :
                m = re.search('NumPaths\\s+\\(\\s+(\\S+)\\s+\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 1 :
                    if verbose > 1 : print('Warning: Unable to find number of paths in Track Shape with index {} and string "{}"'.format(shape_idx, next_text), file=sys.stderr)
                    num_warn += 1
                    break
                else :
                    numpaths_found = True
                    numpaths = int(m.group(1))
                    new_pos += m.end()
            elif m.group(1).lower() == 'sectionidx' :
                m = re.search('SectionIdx\\s+\\(\\s+(\\S+)\\s+\\S+\\s+\\S+\\s+\\S+\\s+\\S+\\s+([^)]+)\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 2 :
                    if verbose > 1 : print('Warning: Unable to find section indices in Track Shape with index {} and string "{}"'.format(shape_idx, next_text), file=sys.stderr)
                    num_warn += 1
                    break
                else :
                    num_indices = int(m.group(1))
                    # the trailing string is a list of section indices
                    str_indices = m.group(2).split()
                    if num_indices != len(str_indices) :
                        if verbose > 1: print('Warning: Number of indexes ({} vs {}) do not match in Track Shape with index {} and string "{}"'.format(num_indices, len(str_indices), shape_idx, next_text), file=sys.stderr)
                        num_warn += 1
                    else :
                        for idx in str_indices :
                            section_indices.append(int(idx))
                    new_pos += m.end()
            elif m.group(1).lower() == 'mainroute' :
                # ignore
                new_pos += m.end()
            elif m.group(1).lower() == 'clearancedist' :
                # ignore
                new_pos += m.end()
            elif m.group(1).lower() == 'tunnelshape' :
                # ignore
                new_pos += m.end()
            elif m.group(1).lower() == 'roadshape' :
                # ignore
                new_pos += m.end()
            else :
                if verbose > 1: print('Warning: Unexpected token "{}" in Track Shape with index {} and string\n"{}"'.format(m.group(1), shape_idx, match.group() + next_text), file=sys.stderr)
                num_warn += 1
                break

        if filename_found :
            track_shapes[shape_idx]['FileName'] = filename
            num_shapes += 1
            if numpaths_found:
                track_shapes[shape_idx]['NumPaths'] = numpaths
            track_shapes[shape_idx]['SectionIdx'] = []
            for idx in section_indices :
                track_shapes[shape_idx]['SectionIdx'].append(idx)
        else :
            if verbose > 1: print('Warning: Filename not found in Track Shape with index {}'.format(shape_idx), file=sys.stderr)
            num_warn += 1
            continue

        if verbose > 2 : print('Info: Added Track Shape', track_shapes[shape_idx])

    if verbose > 0 : print('Info: {} shapes found, {} shapes added; {} warnings'.format(num_shapes, len(track_shapes), num_warn), file=sys.stderr)
    # for tsection.dat #54, should be 14631, 0-39998

    return
# end process_tsection_file()



### main
parser = argparse.ArgumentParser(description='List the track sections used by a route.')
parser.add_argument('-ts', '--tsection-path', type=pathlib.Path, help='Use the specified tsection.dat file, instead of the route\'s global one.')
parser.add_argument('tdb_path', type=pathlib.Path, help='The path to the route\'s track database (.tdb file).')
parser.add_argument('-v', '--verbose', action='count', default=0, help='Be more verbose. Option may be repeated.')
parser.add_argument('-d', '--dump', action='store_true', help='Dump intermediate results, like the list of track shapes, etc.')
args = parser.parse_args()
tsection_path = args.tsection_path
tdb_path = args.tdb_path
verbose = args.verbose
dump = args.dump

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