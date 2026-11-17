#!/usr/bin/env python3
# ORTS-ListTrackInstalled - list the tracks that is installed in GLOBAL
#
# Parse the tsection.dat file and check which shape files exist in GLOBAL.
#
# Copyright (c) 2026 Roger Fischer. MIT License.
#

# Simulator (TrVectorSection) uses SectionIndex connect tracks. RouteEditor uses Shape File Name to add track.

import argparse
import pathlib
import math
import re
import sys

track_section_authors = []  # (start, end, author-string)
track_shape_authors = []    # (start, end, author-string)
track_sections = {}         # [section-index]{'Type'|'Length [m]'|'Length [ft]'|'Radius [m]'|'Radius [ft]'|'Angle [°]'|'Skew'|'Gauge [m]'|'Gauge [ft]'}
track_shapes = {}           # [shape-index]{'FileName'|'Category'|'Type'|'NumPaths'|'SectionIndices'[]}
shape_files = {}            # [file-name]{'Category'|'Type'|'ShapeIndices'[]|'SectionIndices'[]}
expanded_section_authors = []
expanded_shape_authors = []

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


### expand the author list for easy lookup
def expand_author_list( author_list, max) :
    new_list = ['unknown'] * (max+500)  # add some safety
    for author in author_list :
        for i in range(author[0], author[1]) :
            if i > max : break
            new_list[i] = author[2]
    return new_list


### Parse the tsection.dat file and build dictionaries of track sections and shapes
def process_tsection_file(ts_file_path) :
    global track_section_authors, track_sections, track_shape_authors, track_shapes, expanded_section_authors, expanded_shape_authors

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
    expanded_section_authors = expand_author_list(track_section_authors, 40000)

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
        track_sections[section_idx] = {'Author': author, 'Type': 'unknown', 'Length [m]': '', 'Length [ft]': '', 'Radius [m]': '', 'Radius [ft]': '', 'Angle [°]': '', 'Skew [°]': '', 'Gauge [m]': '', 'Gauge [ft]': ''}
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
                    s1 = m.group(1) ; s2 = m.group(2)
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
                new_pos += m.end()
                new_pos += skip_to_end_of_block(sections_text, new_pos, 50)
        # end for each token in TrackSection

        track_sections[section_idx]['Type'] = 'invalid'
        track_sections[section_idx]['FromShapes'] = []
        if not length_found and not curve_found :
            warn(1, 'Warning: Neither SectionSize nor SectionCurve found in Track Section with index {}'.format(section_idx), '')
            num_warn += 1
        else :
            if length_found :
                track_sections[section_idx]['Gauge [m]'] = '{:.2f}'.format(gauge_m)
                track_sections[section_idx]['Gauge [ft]'] = '{:.2f}'.format(gauge_m * 3.28084)
            if curve_found :
                if angle_d < 0.0 : track_sections[section_idx]['Type'] = 'curved-left'
                else : track_sections[section_idx]['Type'] = 'curved-right'
                calc_track_length = math.fabs(radius_m * math.radians(angle_d))
                track_sections[section_idx]['Length [m]'] = '{:.2f}'.format(calc_track_length)
                track_sections[section_idx]['Length [ft]'] = '{:.2f}'.format(calc_track_length * 3.28084)
                track_sections[section_idx]['Radius [m]'] = '{:.2f}'.format(radius_m)
                track_sections[section_idx]['Radius [ft]'] = '{:.2f}'.format(radius_m * 3.28084)
                track_sections[section_idx]['Angle [°]'] = '{:.2f}'.format(angle_d)
            else :
                track_sections[section_idx]['Type'] = 'straight'
                track_sections[section_idx]['Length [m]'] = '{:.2f}'.format(size_m)
                track_sections[section_idx]['Length [ft]'] = '{:.2f}'.format(size_m * 3.28084)
            if skew_found :
                track_sections[section_idx]['Skew [°]'] = '{:.2f}'.format(skew_d)
            num_sections += 1
    # end for each match

    num_left = num_right = num_straight = num_other = 0
    for sidx in track_sections :
        if track_sections[sidx]['Type'] == 'curved-left' : num_left += 1
        elif track_sections[sidx]['Type'] == 'curved-right'  : num_right += 1
        elif track_sections[sidx]['Type'] == 'straight' : num_straight += 1
        else : num_other += 1

    print('Info: {} track sections found, {} track sections parsed; {} warnings'.format(num_sections, len(track_sections), num_warn), file=sys.stderr)
    print(' curved-left curved-right     straight        other', file=sys.stderr)
    print('{: >12} {: >12} {: >12} {: >12}'.format(num_left, num_right, num_straight, num_other), file=sys.stderr)

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
    expanded_shape_authors = expand_author_list(track_shape_authors, 40000)

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
    num_warn = 0 ; num_file_warn = 0
    num_shapes = 0
    new_pos = 0
    matches = re.finditer('^\\s*TrackShape\\s+\\(\\s*(\\d+)\\s*', shapes_text, flags=re.IGNORECASE | re.MULTILINE)
    for match in matches :
        shape_idx = int(match.group(1))
        author = get_author(track_shape_authors, shape_idx)
        track_shapes[shape_idx] = {'Author': author}
        new_pos = match.end()
        filename = '' ; category = 'Track' ; num_paths = 0 ; section_refs = []
        has_main_route = has_clearance_dist = has_manual_junction = has_crossover = has_tunnel_shape = False
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
                            i_idx = int(idx)
                            section_refs.append(i_idx)
                            if i_idx in track_sections :
                                track_sections[i_idx]['FromShapes'].append(shape_idx)
                            else :
                                warn(1, 'Warning: Track Section {} referenced in Track Shape {} does not exist'.format(i_idx, shape_idx), '')
                    new_pos += m.end()
            elif m.group(1).lower() == 'mainroute' :
                has_main_route = True
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'clearancedist' :
                has_clearance_dist = True
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'tunnelshape' :
                has_tunnel_shape = True
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'roadshape' :
                category = 'Road'
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'manualjunctionshape':
                has_manual_junction = True
                new_pos += m.end()
                new_pos += skip_to_end_of_block(shapes_text, new_pos, 20)
            elif m.group(1).lower() == 'crossovershape':
                has_crossover = True
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
        # end loop over tokens in TrackShape block

        if filename_found :
            num_shapes += 1

            track_type = 'unknown'
            if has_tunnel_shape : category += '-Tunnel'
            if has_crossover : track_type = 'Crossing'
            elif (has_main_route and has_clearance_dist) or has_manual_junction : track_type = 'Junction'
            elif has_main_route or has_clearance_dist :
                track_type = 'Junction'
                warn(1, 'Warning: Junction from TrackShape {} may have missing options; mr = {}, hcd = {}'.format(shape_idx, has_main_route, has_clearance_dist), '')
            else :
                if len(section_refs) <= 0 :
                    warn(1, 'Warning: Track Shape {} does not reference any Track Sections'.format(shape_idx), '')
                elif section_refs[0] not in track_sections :
                    warn(1, 'Warning: Track Shape {} does not reference any Track Sections'.format(shape_idx), '')
                else :
                    track_type = track_sections[section_refs[0]]['Type']
            if track_type == 'Junction' :
                num_left = num_right = num_straight = 0
                for idx in section_refs :
                    if idx not in track_sections : continue
                    if track_sections[idx]['Type'] == 'straight' : num_straight += 1  # junctions must have at least one curve
                    elif track_sections[idx]['Type'] == 'curved-left' : num_left += 1
                    elif track_sections[idx]['Type'] == 'curved-right' : num_right += 1
                if num_left <= 0 and num_right <= 0 : track_type = 'straight'
                if num_straight <= 0 : track_type += '-curved'
                elif num_left > num_right : track_type += '-left'
                elif num_right > num_left : track_type += '-right'

            track_shapes[shape_idx]['FileName'] = filename
            track_shapes[shape_idx]['Category'] = category
            track_shapes[shape_idx]['Type'] = track_type
            if num_paths_found:
                track_shapes[shape_idx]['NumPaths'] = num_paths
            track_shapes[shape_idx]['SectionIndices'] = []
            for idx in section_refs :
                track_shapes[shape_idx]['SectionIndices'].append(idx)

            if filename not in shape_files :
                shape_files[filename] = {}
                shape_files[filename]['Category'] = category
                shape_files[filename]['Type'] = track_type
                shape_files[filename]['NumTracks'] = num_paths
                shape_files[filename]['ShapeIndices'] = [shape_idx]
                shape_files[filename]['SectionIndices'] = section_refs
            else :
                warn(2, 'Warning: filename {} from TrackShape {} already in list'.format(filename, shape_idx), '')
                num_file_warn += 1
                shape_files[filename]['ShapeIndices'].append(shape_idx)
                shape_files[filename]['SectionIndices'].extend(section_refs)
        else :
            warn(1, 'Warning: Filename not found in Track Shape with index {}'.format(shape_idx), '')
            num_warn += 1
            continue
    # end for each match

    print('Info: {} shapes found, {} shapes parsed; {} warnings'.format(num_shapes, len(track_shapes), num_warn), file=sys.stderr)
    print('Info: {} shape files found, {} reused'.format(len(shape_files), num_file_warn), file=sys.stderr)

    for section_idx in track_sections :
        if len(track_sections[section_idx]['FromShapes']) <= 0 :
            warn(1, 'Warning: Track Section {} ({}) is not referenced by any Track Shape'.format(section_idx, track_sections[section_idx]['Type']), '')
    return
# end process_tsection_file()



### main

parser = argparse.ArgumentParser(description='''List the track sections installed in GLOBAL.
Scans the specified tsection.dat and checks if the referenced shape file exists.
Outputs a line for each track section, keyed by the shape file name.
Does _not_ consider track in the route specific tsection.dat.''')
parser.add_argument('tsection_file_path', type=pathlib.Path, help='The path to the tsection.dat file.')
parser.add_argument('global_dir_path', nargs='?', type=pathlib.Path, help='Optional. The path to the GLOBAL folder.')
parser.add_argument('shapes_dir_path', nargs='?', type=pathlib.Path, help='Optional. The path to the SHAPES folder.')
parser.add_argument('-i', '--installed', action='store_true', help='List only tracks that are installed in GLOBAL/SHAPES.')
parser.add_argument('-v', '--verbose', action='count', default=0, help='Be more verbose. Option may be repeated.')
parser.add_argument('-d', '--dump', action='store_true', help='Dump intermediate results, like the list of track shapes, etc.')
args = parser.parse_args()
tsection_file_path = args.tsection_file_path
global_dir_path = args.global_dir_path
shapes_dir_path = args.shapes_dir_path
list_all = not args.installed
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

num_installed = 0
print('FileName,Category,Type,NumTracks,ShapeIndices,SectionIndices,Author,SectionIdx,Type,Length [m],Length [ft],Radius [m],Radius [ft],Angle [°],Skew [°],Gauge [m],Gauge [ft], SectionIdx2,...')
for filename in shape_files :
    filepath = pathlib.Path(shapes_dir_path / filename)
    category = shape_files[filename]['Category']
    if list_all or filepath.is_file() :
        num_installed += 1
        first_shape_idx = shape_files[filename]['ShapeIndices'][0]
        first_section_index = shape_files[filename]['ShapeIndices'][0]
        shape_indices = sorted((dict.fromkeys(shape_files[filename]['ShapeIndices'])).keys())  # unique and sorted
        section_indices = sorted((dict.fromkeys(shape_files[filename]['SectionIndices'])).keys())  # unique and sorted
        author = expanded_shape_authors[first_shape_idx]
        out_line = '"{}","{}","{}","{}","{}","{}","{}",'.format(filename, category, shape_files[filename]['Type'], shape_files[filename]['NumTracks'], ';'.join(map(str, shape_indices)), ';'.join(map(str, section_indices)), author)
        for idx in section_indices :
            if idx not in track_sections : continue
            section = track_sections[idx]
            out_line += '"{}","{}","{}","{}","{}","{}","{}","{}","{}","{}",'.format(idx, section['Type'], section['Length [m]'], section['Length [ft]'], section['Radius [m]'], section['Radius [ft]'], section['Angle [°]'], section['Skew [°]'], section['Gauge [m]'], section['Gauge [ft]'])
        print( out_line)

print('Info: {} files installed.'.format(num_installed), file=sys.stderr)

exit(0)