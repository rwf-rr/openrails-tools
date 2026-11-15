#!/usr/bin/env python3
# ORTS-ListTrackInstalled - list the tracks that is installed in GLOBAL
#
# Parse the tsection.dat file and check which shape files exist in GLOBAL.
#
# Copyright (c) 2026 Roger Fischer. MIT License.
#

import argparse
import pathlib
import math
import re
import sys

track_section_authors = []  # (start, end, author-string)
track_shape_authors = []    # (start, end, author-string)
track_sections = {}         # [section-index]['Gauge [m]'|'Gauge [ft]'|'Type'|'Length [m]'|'Length [ft]'|'Skew']
track_shapes = {}           # [shape-index]['FileName'|'NumPaths'|'SectionIdx'[]]
shape_files = {}            # [file-name]SectionIdx[]


### print warning message
def warn(level, message, addl_text) :
    global verbose
    if verbose > level : print(message + addl_text, file=sys.stderr)
    elif verbose >= level : print(message, file=sys.stderr)
    return


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


### skip to end of block, handling embedded sub-blocks
def skip_to_end_of_block(block_text, start_pos, limit) :
    char_cnt = 1 ; sub_block_cnt = 0
    for i in range(start_pos, start_pos+limit) :
        if block_text[i] == ')' and sub_block_cnt == 0 : break
        elif block_text[i] == ')' : sub_block_cnt -= 1
        elif block_text[i] == '(' : sub_block_cnt += 1
        char_cnt += 1
    return char_cnt + 1


### Parse the tsection.dat file and build dictionaries of track sections and shapes
def process_tsection_file(ts_file_path) :
    global track_section_authors, track_sections, track_shape_authors, track_shapes, num_warn

    ts_text = read_file(ts_file_path)

    # skip some of the preamble
    offset = 2000  # end of preamble in earliest tsection.dat
    section_authors_text = ts_text[offset:16000]  # well past the author section in version 60

    # first get the author of the track sections from eg.
    # Sections     0-  332  original MS/KUJU sections
    num_warn = 0
    new_pos = 0
    matches = re.finditer('^Sections\\s+(\\d+)(.*)$', section_authors_text, flags=re.IGNORECASE | re.MULTILINE)
    if not matches :
        warn(1, 'Warning: Unable to find "Sections <n1>-<n2> <author>" lines in "{}"'.format(ts_file_path), '')
        num_warn += 1
    else :
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
                    warn(1, 'Warning: Unable to find end-number and author in "{}"'.format(text), '')
                    num_warn += 1
                    end_num = start_num
                    author = '__not-found__'
                else :
                    end_num = int(m2.group(1))
                    author = m2.group(2)
            new_pos = match.end()
            track_section_authors.append((start_num, end_num, author))

    print('Info: {} track section authors found; {} warnings'.format(len(track_section_authors), num_warn), file=sys.stderr)

    # continue from where the sections authors ended
    offset += new_pos
    sections_text = ts_text[offset:]

    # then get the track sections, eg
    # TrackSection ( 39843
    #  SectionSize ( 1.5 0 )
    #  SectionCurve ( 8000.0 5 )
    # )
    num_warn = 0
    num_sections = 0
    new_pos = 0
    matches = re.finditer('^\\s*TrackSection\\s+\\(\\s*(\\d+)\\s*', sections_text, flags=re.IGNORECASE | re.MULTILINE)
    for match in matches :
        section_idx = int(match.group(1))
        author = get_author(track_section_authors, section_idx)
        track_sections[section_idx] = {'Author': author}
        new_pos = match.end()

        gauge_m = size_m = radius_m = -0.1 ; angle_d = skew_d = 0.0
        length_found = curve_found = skew_found = False
        for _ in range(4) :   # hard limit for safety
            # get next token, should be SectionSize or SectionCurve
            next_text = sections_text[new_pos:new_pos+200]
            if next_text.lstrip()[0] == ')' :
                break   # end of TrackSection
            m = re.search('\\s*([^ ()\t\n\r\f\v]+)\\s+\\(', next_text[:30])
            if not m or m.lastindex < 1 :
                warn(1, 'Warning: Unable to find token after TrackSection for index {}'.format(section_idx), ' in string\n' + next_text)
                num_warn += 1
                break
            elif m.group(1).lower() == 'sectionsize' :
                m = re.search('SectionSize\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s+([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 2 :
                    warn(1, 'Warning: Unable to find gauge and length in Track Section with index {}'.format(section_idx), ' in string\n' + next_text)
                    num_warn += 1
                    break
                else :
                    length_found = True
                    gauge_m = float(m.group(1))
                    size_m = float(m.group(2))
                    new_pos += m.end()
            elif m.group(1).lower() == 'sectioncurve' :
                m = re.search('SectionCurve\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s+([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 2 :
                    warn(1, 'Warning: Unable to find radius and angle in Track Section with index {}'.format(section_idx), ' in string\n' + next_text)
                    num_warn += 1
                    break
                else :
                    curve_found = True
                    radius_m = float(m.group(1))
                    angle_d = float(m.group(2))
                    new_pos += m.end()
            elif m.group(1).lower() == 'sectionskew' :
                m = re.search('SectionSkew\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 1 :
                    warn(1, 'Warning: Unable to find skew in Track Section with index {}'.format(section_idx), ' in string\n' + next_text)
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
                warn(1, 'Warning: Unexpected token "{}" in Track Section with index {}'.format(m.group(1), section_idx), ' in string\n' + match.group() + next_text)
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
            warn(1, 'Warning: Neither SectionSize nor SectionCurve found in Track Section with index {}'.format(section_idx), '')
            num_warn += 1
            continue
    # end for each match

    print('Info: {} track sections found, {} track sections parsed; {} warnings'.format(num_sections, len(track_sections), num_warn), file=sys.stderr)
    # for tsection.dat #54, should be 7399, 0-39998
    section_labels = ['Type', '"Gauge [m]"', '"Length [m]"', ]
    if dump :
        for s in track_sections :
            print(s, track_sections[s], file=sys.stderr)

    # continue from where the sections ended
    offset += new_pos
    shape_authors_text = ts_text[offset:]

    # then get the author of the track shapes from eg.
    # Shapes   259-12219  presently not allocated
    num_warn = 0
    new_pos = 0
    matches = re.finditer('^Shapes\\s+(\\d+)(.*)$', shape_authors_text, flags=re.IGNORECASE | re.MULTILINE)
    if not matches :
        warn(1, 'Warning: Unable to find "Shapes <n1>-<n2> <author>" lines in "{}"'.format(ts_file_path), '')
        num_warn += 1
    else :
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
                    warn(1, 'Warning: Unable to find end-number and author in "{}"'.format(text), '')
                    num_warn += 1
                    end_num = start_num
                    author = '__not-found__'
                else :
                    end_num = int(m2.group(1))
                    author = m2.group(2)
            new_pos = match.end()
            track_shape_authors.append((start_num, end_num, author))

    print('Info: {} shape authors found; {} warnings'.format(len(track_shape_authors), num_warn), file=sys.stderr)

    # continue from where the shape authors ended
    offset += new_pos
    shapes_text = ts_text[offset:]

    # lastly get the track shapes, eg
    # TrackShape ( 0
    #  FileName ( A1t10mStrt.s )
    #  NumPaths ( 1 )
    #  SectionIdx ( 1 0 0 0 0 0 )
    #  ...
    # )
    num_warn = 0
    num_shapes = 0
    new_pos = 0
    matches = re.finditer('^\\s*TrackShape\\s+\\(\\s*(\\d+)\\s*', shapes_text, flags=re.IGNORECASE | re.MULTILINE)
    for match in matches :
        shape_idx = int(match.group(1))
        author = get_author(track_shape_authors, shape_idx)
        track_shapes[shape_idx] = {'Author': author}
        new_pos = match.end()
        filename = '' ; num_paths = 0 ; section_indices = []
        filename_found = num_paths_found = False
        for _ in range(16) :   # hard limit for safety
            # get next token, should be SectionSize or SectionCurve
            next_text = shapes_text[new_pos:new_pos+200]  # all tokens should be shorter than 200 chars
            if next_text.lstrip()[0] == ')' :
                break   # end of TrackShape
            m = re.search('\\s*([^ ()\t\n\r\f\v]+)\\s+\\(', next_text[:30])
            if not m or m.lastindex < 1 :
                warn(1, 'Warning: Unable to find token after Track Shape for index {}'.format(shape_idx), ' in string\n' + next_text)
                num_warn += 1
                break
            elif m.group(1).lower() == 'filename' :
                m = re.search('FileName\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 1 :
                    warn(1, 'Warning: Unable to find filename in Track Shape with index {}'.format(shape_idx), ' in string\n' + next_text)
                    num_warn += 1
                    break
                else :
                    filename_found = True
                    filename = m.group(1)
                    new_pos += m.end()
            elif m.group(1).lower() == 'numpaths' :
                m = re.search('NumPaths\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 1 :
                    warn(1, 'Warning: Unable to find number of paths in Track Shape with index {}'.format(shape_idx), ' in string\n' + next_text)
                    num_warn += 1
                    break
                else :
                    num_paths_found = True
                    num_paths = int(m.group(1))
                    new_pos += m.end()
            elif m.group(1).lower() == 'sectionidx' :
                # SectionIdx ( num-sections X Y Z A section-idx ... )
                m = re.search('SectionIdx\\s+\\(\\s*(\\d+)\\s+[^ )]+\\s+[^ )]+\\s+[^ )]+\\s+[^ )]+\\s+([^()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                if not m or m.lastindex < 2 :
                    warn(1, 'Warning: Unable to find section indices in Track Shape with index {}'.format(shape_idx), ' in string\n' + next_text)
                    num_warn += 1
                    break
                else :
                    num_indices = int(m.group(1))
                    # the trailing string is a list of section indices
                    str_indices = m.group(2).split()
                    if num_indices != len(str_indices) :
                        warn(1, 'Warning: Number of indexes ({} vs {}) do not match in Track Shape with index {}'.format(num_indices, len(str_indices), shape_idx), ' in string\n' + next_text)
                        num_warn += 1
                    else :
                        for idx in str_indices :
                            section_indices.append(int(idx))
                    new_pos += m.end()
            elif m.group(1).lower() == 'mainroute' :
                # ignore
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'clearancedist' :
                # ignore
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'tunnelshape' :
                # ignore
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'roadshape' :
                # ignore
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'manualjunctionshape':
                # ignore
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'crossovershape':
                # ignore
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'xoverpts':
                # ignore
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 200)
            else :
                warn(1, 'Warning: Unexpected token "{}" in Track Shape with index {}'.format(m.group(1), shape_idx), ' in string\n' + match.group() + next_text)
                num_warn += 1
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
                break

        if filename_found :
            track_shapes[shape_idx]['FileName'] = filename
            num_shapes += 1
            if num_paths_found:
                track_shapes[shape_idx]['NumPaths'] = num_paths
            track_shapes[shape_idx]['SectionIdx'] = []
            for idx in section_indices :
                track_shapes[shape_idx]['SectionIdx'].append(idx)
            shape_files[filename] = section_indices
        else :
            warn(1, 'Warning: Filename not found in Track Shape with index {}'.format(shape_idx), '')
            num_warn += 1
            continue
    # end for each match

    print('Info: {} shapes found, {} shapes parsed; {} warnings'.format(num_shapes, len(track_shapes), num_warn), file=sys.stderr)
    print('Info: {} shape files found'.format(len(shape_files)), file=sys.stderr)

    return
# end process_tsection_file()



### main

parser = argparse.ArgumentParser(description='''List the track sections installed in GLOBAL.
Scans the specified tsection.dat and checks if the referenced shape file exists.
Outputs a line for each track section that has a shape.
Does _not_ consider track in the route specific tsection.dat.''')
parser.add_argument('tsection_file_path', type=pathlib.Path, help='The path to the tsection.dat file.')
parser.add_argument('global_dir_path', nargs='?', type=pathlib.Path, help='Optional. The path to the GLOBAL folder.')
parser.add_argument('shapes_dir_path', nargs='?', type=pathlib.Path, help='Optional. The path to the SHAPES folder.')
parser.add_argument('-v', '--verbose', action='count', default=0, help='Be more verbose. Option may be repeated.')
parser.add_argument('-d', '--dump', action='store_true', help='Dump intermediate results, like the list of track shapes, etc.')
args = parser.parse_args()
tsection_file_path = args.tsection_file_path
global_dir_path = args.global_dir_path
shapes_dir_path = args.shapes_dir_path
verbose = args.verbose
dump = args.dump

if not tsection_file_path.is_file() :
    print( 'Error: Track Sections file "{}" does not exist.'.format(tsection_file_path), file=sys.stderr)
    sys.exit(1)

if not global_dir_path :
    global_dir_path = tsection_file_path.resolve().parent
if not global_dir_path.is_dir() :
    print( 'Error: Global folder "{}" does not exist.'.format(global_dir_path), file=sys.stderr)
    sys.exit(1)

if not shapes_dir_path :
    shapes_dir_path = pathlib.Path(global_dir_path / 'SHAPES')
if not shapes_dir_path.is_dir() :
    print( 'Error: Shapes folder "{}" does not exist.'.format(shapes_dir_path), file=sys.stderr)
    sys.exit(1)

process_tsection_file(tsection_file_path)




exit(0)