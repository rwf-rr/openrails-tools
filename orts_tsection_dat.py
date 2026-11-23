# orts_tsection_dat.py - Module to parse Open Rails Train Simulator tsection.dat files.

import pathlib
import math
import re
import sys


# Constants
FT_PER_M = 3.28084  # feet per meter

C_ROAD = 'Road' ; C_TRACK = 'Track' ; C_TUNNEL_SUFFIX = '-Tunnel' ; C_NOT_DEFINED = 'undefined'
T_TRACK = 'track' ; T_ROAD = 'road'
T_CURVED_LEFT = 'curved_left' ; T_CURVED_RIGHT = 'curved_right' ; T_STRAIGHT = 'straight'
T_JUNCTION = 'junction' ; T_JUNCTION_LEFT = 'junction-left' ; T_JUNCTION_RIGHT = 'junction-right' ; T_JUNCTION_SLIP = 'junction-slip'
T_JUNCTION_CURVED_LEFT = 'junction-curved-left' ; T_JUNCTION_CURVED_RIGHT = 'junction-curved-right'
T_CROSSING = 'crossing' ; T_NOT_DEFINED = 'undefined' ; T_INDETERMINATE = 'indeterminate'

CTX_ALL = 'All' ; CTX_SHAPE = 'Shapes' ; CTX_SECTION = 'Sections' ; CTX_AUTHOR = 'Authors' ; CTX_TSECTION = 'TSection'

MAX_INDEX = 40000
"""Largest index seen in tsection.dat version 60."""

########################################################################


class Warn :
    """Static class to output a warning messages."""
    context = 'Main' ; scope = [CTX_ALL] ; level = 0 ; detail = False

    @classmethod
    def set_context(cls, context: str) :
        cls.context = context
    # end function set_context

    @classmethod
    def set_scope_and_level(cls, scope: list[str], level: int, detail: bool = False) :
        cls.scope = scope
        cls.level = level
        cls.detail = detail
    # end of function set_scope_and_level

    @classmethod
    def warn(cls, level: int, message: str, addl_txt: str = ''):
        if level <= cls.level and (CTX_ALL in cls.scope or cls.context in cls.scope) :
            msg = 'Warning - {}: {}'.format(cls.context, message)
            if cls.detail : msg += addl_txt
            print(msg, file=sys.stderr)
        return
    # end function warn
# end class Warn

########################################################################


class Authors :
    """Represents the authors as defined in the comments section of some tsection.dat files."""
    NO_AUTHOR = '__undefined__' ; NOT_FOUND = '__not-found__'

    def __init__(self, size: int) :
        self._authors = [Authors.NO_AUTHOR] * (size + 1)
        """The list of authors. May be a sparse list, as not all indexes are used."""
        self.__num_added = 0
        """The number of indices that have an author set."""
    # end constructor

    def add_author(self, first_idx: int, last_idx: int, author_name: str) :
        """Add an author to the list. Returns the number of indices added."""
        for idx in range(first_idx, last_idx+1) :
            self._authors[idx] = author_name
        self.__num_added += last_idx - first_idx + 1
        return last_idx - first_idx + 1
    # end function add_author

    def get_author(self, index: int) :
        """Get the author for an index."""
        return self._authors[index] if index < len(self._authors) else 'not-found'
    # end function get_authors

    def get_counts(self) -> tuple[int,int] :
        """Get the total number of indices with a defined author and the number of unique authors."""
        defined_indices = sum(1 for author in self._authors if author != Authors.NO_AUTHOR)
        num_unique_authors = len(set(self._authors))
        return defined_indices, num_unique_authors
    # end function get_counts

    def get_counts_per_author(self) -> dict[str,int] :
        counts = {}
        for author in self._authors :
            if author == Authors.NO_AUTHOR : continue
            if author in counts : counts[author] += 1
            else : counts[author] = 1
        return counts
    # end function get_counts_per_author

    def parse_authors(self, keyword: str, text_block: str) -> (int,int,int):
        """Parse a block of text that may include a list of authors with start and end indices.
        Returns the number of characters processed, the number of authors parsed, and the number of warnings."""
        # Shapes 39900-39999 are Okrasa Ghia's Narrow Gauge shapes

        num_chars = num_parsed = num_warn = 0
        regex = f'{keyword}\\s+(\\d+)(.*)$'  # eg. '^Sections\\s+(\\d+)(.*)$'
        matches = re.finditer(regex, text_block, flags=re.IGNORECASE | re.MULTILINE)
        # matches always evaluates to True; there is no easy way to check if it did not find any matches
        for match in matches:
            start_num = int(match.group(1))
            end_num = -1 ; author = Authors.NOT_FOUND
            text = match.group(2).strip()
            if not text.startswith('-'):
                end_num = start_num
                author = match.group(2).strip()
            else:
                m2 = re.search('-\\s*(\\d+)\\s+(.*)', text, flags=re.IGNORECASE)
                if not m2 or m2.lastindex < 2:
                    Warn.warn(2, 'Warning: Unable to find end-number and author in "{}"'.format(text))
                    num_warn += 1
                else:
                    end_num = int(m2.group(1))
                    author = m2.group(2)
            num_chars = match.end()
            self.add_author(start_num, end_num, author)
            num_parsed += 1
        # end for each match
        if num_parsed <= 0 :
            Warn.warn(1, 'Unable to find authors ("<n1>-<n2> <author>")')
            num_warn += 1
        return num_chars, num_parsed, num_warn
    # end of function parse_authors
# end class Authors

########################################################################


class TrackSection :
    """
    Represents a section of track or road. Is either a straight or curved section.
    Added fields are section type, imperial measures, and calculated track length for curves.
    Values are strings, as they are intended to be exported to a spreadsheet.
    """

    def __init__(self, index: int = -1, gauge_m: str = '', length_m: str = '', radius_m: str = '' , angle_d: str = '', skew_d: str = '') :
        """Create a TrackSection object, either undefined or with the specified values."""
        self.index = index
        self.gauge_m = gauge_m
        self.length_m = length_m
        self.radius_m = radius_m
        self.angle_d = angle_d
        self.skew_d = skew_d
        self.type = T_NOT_DEFINED

        if index >= 0 :
            try :
                self.gauge_ft = '{:.2f}'.format(float(gauge_m) * FT_PER_M) if gauge_m else ''
                self.length_ft = '{:.2f}'.format(float(length_m) * FT_PER_M) if length_m else ''
                self.radius_ft = '{:.2f}'.format(float(radius_m) * FT_PER_M) if radius_m else ''
                self.curve_degree = ('{:.2f}'.format(114.592 * math.asin(15.24/float(radius_m))) if float(radius_m) > 15.24 else '>90') if radius_m else ''
                if self.angle_d and self.radius_m :
                    self.length_m = '{:.2f}'.format(math.fabs(float(radius_m) * math.radians(float(angle_d))))
                    self.length_ft = '{:.2f}'.format(float(self.length_m) * FT_PER_M)
                    if float(self.angle_d) < 0.0 : self.type = T_CURVED_LEFT
                    elif float(self.angle_d) > 0.0 : self.type = T_CURVED_RIGHT
                elif self.length_m :
                    self.type = T_STRAIGHT
                else : self.type = 'indeterminate'
            except Exception as ex :  # only expect ValueError
                Warn.warn(3, f'Failed to create Track Section with index {index}, exception {type(ex).__name__}, args: {ex.args}')
    # end function __init__

    def is_curve(self):
        return self.type in [T_CURVED_LEFT, T_CURVED_RIGHT]

    def is_straight(self):
        return self.type in [T_STRAIGHT]

    def format_row(self) :
        if self.index == -1 : return '-1,unused'
        return f'{self.index},{self.type},{self.length_m},{self.radius_m},{self.angle_d},{self.length_ft},{self.radius_ft},{self.curve_degree},{self.skew_d},{self.gauge_m},{self.gauge_ft}'
    # end function format_row

    @classmethod
    def format_header(cls) :
        return 'SectionIdx,Type,"Length [m]","Radius [m]","Angle [°]","Length [ft]","Radius [ft]",CurveDegree,"Skew [°]","Gauge [m]","Gauge [ft]"'
    # end function format_header

# end class TrackSection

########################################################################


class TrackSectionList :
    """
    Represents the TrackSections list in the tsection.dat file.
    The list is augmented with additional data (eg. author) to make processing easier.
    """

    def __init__(self, size: int) :
        self._size = size
        self.list = [TrackSection()] * (self._size + 1)
        """List of track sections, indexed by the section index."""
        self.bad_indices: set[int] = set()  #
        """List of track section indices that have parsing issues."""

    def parse_sections(self, sections_text: str) -> [int, int, int, int]:
        """Parse the track sections block and create the list of track sections."""
        # then get the track sections, eg
        # TrackSection ( 39843
        #  SectionSize ( 1.5 0 )
        #  SectionCurve ( 8000.0 5 )
        # )

        offset = num_matches = num_warn = 0
        matches = re.finditer('^\\s*TrackSection\\s+\\(\\s*(\\d+)\\s*', sections_text, flags=re.IGNORECASE | re.MULTILINE)
        for match in matches :
            num_matches += 1
            section_idx = int(match.group(1))
            offset = match.end()
            gauge_m = length_m = radius_m = angle_d = skew_d = ''
            size_found = curve_found = False
            for _ in range(6) :   # hard limit for safety
                next_text = sections_text[offset:offset+200]  # enough for largest TrackSection block in v60
                if next_text.lstrip()[0] == ')' :
                    break   # end of TrackSection
                m = re.search('\\s*([^ ()\t\n\r\f\v]+)\\s+\\(', next_text[:30])  # enough for largest token
                if not m or m.lastindex < 1 :
                    Warn.warn(3, f'Unable to find token after TrackSection for index {section_idx}', ' in string\n' + next_text)
                    num_warn += 1 ; self.bad_indices.add(section_idx)
                    break  # go to next TrackSection block
                elif m.group(1).lower() == 'sectionsize' :
                    m = re.search('SectionSize\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s+([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 2 :
                        Warn.warn(3, f'Unable to find gauge and length in Track Section with index {section_idx}', ' in string\n' + next_text)
                        num_warn += 1 ; self.bad_indices.add(section_idx)
                        offset += skip_to_end_of_block(sections_text, offset, 50)
                    else :
                        size_found = True
                        gauge_m = m.group(1)
                        length_m = m.group(2)
                        offset += m.end()
                elif m.group(1).lower() == 'sectioncurve' :
                    m = re.search('SectionCurve\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s+([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 2 :
                        Warn.warn(3, f'Unable to find radius and angle in Track Section with index {section_idx}', ' in string\n' + next_text)
                        num_warn += 1 ; self.bad_indices.add(section_idx)
                        offset += skip_to_end_of_block(sections_text, offset, 50)
                    else :
                        curve_found = True
                        radius_m = m.group(1)
                        angle_d = m.group(2)
                        offset += m.end()
                elif m.group(1).lower() == 'sectionskew' :
                    m = re.search('SectionSkew\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 1 :
                        Warn.warn(3, f'Unable to find skew in Track Section with index {section_idx}', ' in string\n' + next_text)
                        num_warn += 1 ; self.bad_indices.add(section_idx)
                        offset += skip_to_end_of_block(sections_text, offset, 50)
                    else :
                        skew_d = float(m.group(1))
                        offset += m.end()
                elif m.group(1).lower() == 'waterscoop':
                    # ignore
                    offset += m.end(); offset += skip_to_end_of_block(sections_text, offset, 50)
                else :
                    Warn.warn(3, f'Unexpected token "{m.group(1)}" in Track Section with index {section_idx}', ' in string\n' + match.group() + next_text)
                    num_warn += 1 ; self.bad_indices.add(section_idx)
                    offset += m.end() ; offset += skip_to_end_of_block(sections_text, offset, 50)
            # end for each token in TrackSection

            if not size_found and not curve_found :
                Warn.warn(2, f'Neither SectionSize nor SectionCurve found in Track Section with index {section_idx}')
                num_warn += 1 ; self.bad_indices.add(section_idx)
                continue  # ignore this TrackSection block

            track_section = TrackSection(section_idx, gauge_m, length_m, radius_m, angle_d, skew_d)
            self.list[section_idx] = track_section
        # end for each match

        if num_matches <= 0 : Warn.warn( 1, '*** No Track Sections found ***')

        return offset, num_matches, num_warn, len(self.bad_indices)
    # end function parse_sections

    def get_counts(self) -> tuple[int, int, int, int] :
        """Count the track sections by type: all, straight, left, right."""
        num_straight = num_curved_left = num_curved_right = num_indeterminate = num_undefined = 0
        for ts in self.list :
            if ts is None or ts.index < 0 :  num_undefined += 1
            elif ts.type == T_STRAIGHT : num_straight += 1
            elif ts.type == T_CURVED_LEFT : num_curved_left += 1
            elif ts.type == T_CURVED_RIGHT : num_curved_right += 1
            elif ts.type == T_INDETERMINATE : num_indeterminate += 1
            else : num_undefined += 1
        num_all = num_straight + num_curved_left + num_curved_right
        return num_all, num_straight, num_curved_left, num_curved_right
    # end function get_counts

# end class TrackSectionList

########################################################################


class TrackShape :
    """
    Represents a placeable piece of track or road, as represented by a shape file. May consist of multiple track sections.
    """

    def __init__(self, index=-1, filename='', num_paths='', sections_list=None, main_route_idx='', clearance_dist_m='', is_tunnel='', is_road='', is_manual_junction='', is_crossover='', num_crossing_points='') :
        self.index = index
        self.filename = filename
        self.num_paths = num_paths
        self.sections_list = sections_list
        self.main_route_idx = main_route_idx
        self.clearance_dist_m = clearance_dist_m
        self.is_tunnel = is_tunnel
        self.is_road = is_road
        self.is_manual_junction = is_manual_junction
        self.is_crossover = is_crossover
        self.num_crossing_points = num_crossing_points
        self.type = T_NOT_DEFINED
        self.category = C_NOT_DEFINED

        if index >= 0 :
            self.category = C_ROAD if is_road else C_TRACK
            if self.is_tunnel : self.category += C_TUNNEL_SUFFIX
            self.clearance_dist_ft = '{:.2f}'.format(float(self.clearance_dist_m) * FT_PER_M) if self.clearance_dist_m else ''
            if 'Slip' in self.filename : self.type = T_JUNCTION_SLIP
            elif self.is_crossover or self.num_crossing_points : self.type = T_CROSSING
            elif (num_paths and int(num_paths) > 1) and (is_manual_junction or main_route_idx or clearance_dist_m) : self.type = T_JUNCTION
            else :
                self.type = T_ROAD if self.category == C_ROAD else T_TRACK
                if num_paths and int(num_paths) > 1 : self.type += f'-{num_paths}x'
    # end function __init__

    def format_row(self) :
        if self.index == -1 : return '-1,unused'
        section_str = ' ; '.join(self.sections_list)
        return f'{self.index},{self.category},{self.type},"{self.filename}",{self.num_paths},{self.main_route_idx},{self.clearance_dist_m},{self.clearance_dist_ft},' \
               f'{self.is_tunnel},{self.is_road},{self.is_manual_junction},{self.is_crossover},{self.num_crossing_points},"{section_str}"'
    # end function format_row

    @classmethod
    def format_header(cls) :
        return 'SectionIdx,Category,Type,FileName,NumPaths,MainRoute,"Clearance [m]","Clearance [ft]",Tunnel,Road,ManualJunction,Crossover,CrossingPoints,SectionRefs'
    # end function format_header

# end class TrackShape

########################################################################


class TrackShapeList :
    """
    Represents the TrackShapes list in the tsection.dat file.
    The list is augmented with additional data (eg. author) to make processing easier.
    """

    def __init__(self, size: int) :
        self._size = size
        self.list = [TrackShape()] * (self._size + 1)
        """List of track shapes, indexed by the shape index."""
        self.bad_indices: set[int] = set()
        """List of track shape indices that have parsing problems."""
    # end of constructor

    def parse_shapes(self, shapes_text: str) -> [int, int, int, int] :
        """Parse the track shapes block and create the list of track shapes."""
        # TrackShape ( 0
        #  FileName ( A1t10mStrt.s )
        #  NumPaths ( 1 )
        #  SectionIdx ( 1 0 0 0 0 0 )
        #  ...
        # )

        offset = num_matches = num_warn = 0
        matches = re.finditer('^\\s*TrackShape\\s+\\(\\s*(\\d+)\\s*', shapes_text, flags=re.IGNORECASE | re.MULTILINE)
        for match in matches:
            num_matches += 1
            shape_idx = int(match.group(1))
            offset = match.end()
            sections_list = []
            filename = num_paths = main_route_ref = clearance_dist_m = is_tunnel = is_road = is_manual_junction = is_crossover = num_crossing_points = ''
            for _ in range(50):  # hard limit for safety, seen turntables with up to 40 paths
                next_text = shapes_text[offset:offset+200]  # all tokens should be shorter than 200 chars
                if next_text.lstrip()[0] == ')':
                    break  # end of TrackShape
                m = re.search('\\s*([^ ()\t\n\r\f\v]+)\\s+\\(', next_text[:30])
                if not m or m.lastindex < 1:
                    Warn.warn(3, f'Unable to find token after Track Shape for index {shape_idx}', ' in string\n' + next_text)
                    num_warn += 1
                    break  # go to next TrackShape block
                elif m.group(1).lower() == 'filename':
                    m = re.search('FileName\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 1:
                        Warn.warn(3, f'Unable to find filename in Track Shape with index {shape_idx}', ' in string\n' + next_text)
                        num_warn += 1
                        offset += skip_to_end_of_block(shapes_text, offset, 50)
                    else:
                        filename = m.group(1)
                        offset += m.end()
                elif m.group(1).lower() == 'numpaths':
                    m = re.search('NumPaths\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 1:
                        Warn.warn(3, f'Unable to find number of paths in Track Shape with index {shape_idx}', ' in string\n' + next_text)
                        num_warn += 1
                        offset += skip_to_end_of_block(shapes_text, offset, 50)
                    else:
                        num_paths = m.group(1)
                        offset += m.end()
                elif m.group(1).lower() == 'sectionidx':  # this may occur multiple times, generally num_paths times
                    # SectionIdx ( num-sections X Y Z A section-idx ... )
                    m = re.search('SectionIdx\\s+\\(\\s*(\\d+)\\s+[^ )]+\\s+[^ )]+\\s+[^ )]+\\s+[^ )]+\\s+([^()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 2:
                        Warn.warn(3, f'Unable to find section indices in Track Shape with index {shape_idx}', ' in string\n' + next_text)
                        num_warn += 1
                        offset += skip_to_end_of_block(shapes_text, offset, 100)
                    else:
                        num_indices = int(m.group(1))
                        indices = m.group(2).strip() ; num_values = len(indices.split())
                        if num_indices != num_values:
                            Warn.warn(3, f'Number of indexes ({num_indices} vs {num_values}) do not match in Track Shape with index {shape_idx}', ' in string\n' + next_text)
                            num_warn += 1
                        sections_list.append(indices)
                        offset += m.end()
                elif m.group(1).lower() == 'mainroute':
                    m = re.search('MainRoute\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 1:
                        Warn.warn(3, f'Unable to find main route number in Track Shape with index {shape_idx}', ' in string\n' + next_text)
                        num_warn += 1
                        offset += skip_to_end_of_block(shapes_text, offset, 50)
                    else:
                        main_route_ref = m.group(1)
                        offset += m.end()
                elif m.group(1).lower() == 'clearancedist':
                    m = re.search('ClearanceDist\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s*\\)', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 1:
                        Warn.warn(3, f'Unable to find clearance distance in Track Shape with index {shape_idx}', ' in string\n' + next_text)
                        num_warn += 1
                        offset += skip_to_end_of_block(shapes_text, offset, 50)
                    else:
                        clearance_dist_m = m.group(1)
                        offset += m.end()
                elif m.group(1).lower() == 'tunnelshape':
                    is_tunnel = 'y'
                    offset += m.end() ; offset += skip_to_end_of_block(shapes_text, offset, 20)
                elif m.group(1).lower() == 'roadshape':
                    is_road = 'y'
                    offset += m.end() ; offset += skip_to_end_of_block(shapes_text, offset, 20)
                elif m.group(1).lower() == 'manualjunctionshape':
                    is_manual_junction = 'y'
                    offset += m.end() ; offset += skip_to_end_of_block(shapes_text, offset, 20)
                elif m.group(1).lower() == 'crossovershape':
                    is_crossover = 'y'
                    offset += m.end() ; offset += skip_to_end_of_block(shapes_text, offset, 20)
                elif m.group(1).lower() == 'xoverpts':
                    m = re.search('XoverPts\\s+\\(\\s*([^ ()\t\n\r\f\v]+)\\s+', next_text, flags=re.IGNORECASE)
                    if not m or m.lastindex < 1:
                        Warn.warn(3, f'Unable to find number of crossing points in Track Shape with index {shape_idx}', ' in string\n' + next_text)
                        num_warn += 1
                        offset += skip_to_end_of_block(shapes_text, offset, 20)
                    else:
                        num_crossings = int(m.group(1))
                        num_crossing_points = 'x' * num_crossings
                        offset += m.end()
                        offset += skip_to_end_of_block(shapes_text, offset, 100)  # skips over enclosed XoverPt blocks
                else:
                    Warn.warn(3, 'Unexpected token "{m.group(1)}" in Track Shape with index {shape_idx}', ' in string\n' + match.group() + next_text)
                    num_warn += 1
                    offset += skip_to_end_of_block(shapes_text, offset, 100)
            # end for each token in block

            if not filename:
                Warn.warn(2, f'FileName not found in Track Shape with index {shape_idx}')
                num_warn += 1 ; self.bad_indices.add(shape_idx)
                continue  # ignore this TrackShape block
            if not num_paths:
                Warn.warn(2, f'NumPaths not found in Track Shape with index {shape_idx}')
                num_warn += 1 ; self.bad_indices.add(shape_idx)
                # but continue to use block
            elif int(num_paths) != len(sections_list) :
                Warn.warn(2, f'NumPaths "{num_paths}" does not match the number of section indices "{len(sections_list)}" in Track Shape with index {shape_idx}')
                num_warn += 1 ; self.bad_indices.add(shape_idx)

            track_shape = TrackShape(shape_idx, filename, num_paths, sections_list, main_route_ref, clearance_dist_m, is_tunnel, is_road, is_manual_junction, is_crossover, num_crossing_points)
            self.list[shape_idx] = track_shape
        # end for each TrackShape block

        if num_matches <= 0 :
            Warn.warn( 1, '*** No Track Shapes found ***')
            num_warn += 1

        return offset, num_matches, num_warn, len(self.bad_indices)
    # end of function parse_shapes


    def get_counts(self) -> tuple[int, int, int, int, int] :
        """Count the track shapes by type: all, roads, track, junction, crossing."""
        num_roads = num_tracks = num_junctions = num_crossings = num_indeterminate = num_undefined = 0
        for ts in self.list :
            if ts is None or ts.index < 0 : num_undefined += 1
            elif ts.category.startswith(C_ROAD) : num_roads += 1
            elif ts.type.startswith(T_CROSSING) : num_crossings += 1
            elif ts.type.startswith(T_JUNCTION) : num_junctions += 1
            elif ts.type.startswith(T_TRACK) : num_tracks += 1
            else : num_indeterminate += 1
        num_all = num_roads + num_tracks + num_junctions + num_crossings
        return num_all, num_roads, num_tracks, num_junctions, num_crossings
    # end of function get_counts

# end class TrackShapesList

########################################################################


class TSectionDatFile :
    """
    Represents the tsection.dat file. Besides the TrackSections and TrackShapes lists, also includes TrackSection authors and TrackShape authors.
    """

    def __init__(self, file_path: pathlib.Path):
        self.file_path = file_path
        """The path of the tsection.dat file."""
        self.section_authors = Authors(MAX_INDEX)
        """List of section authors, indexed by section index."""
        self.track_sections = TrackSectionList(MAX_INDEX)
        """list of track sections, indexed by section index."""
        self.shape_authors = Authors(MAX_INDEX)
        """List of shape authors, indexed by shape index."""
        self.track_shapes = TrackShapeList(MAX_INDEX)
        """list of track shapes, indexed by shape index."""

        # read the file, which is either utf-16 or utf8
        file_bytes = self.file_path.read_bytes()
        enc = 'utf-8' if 0 < file_bytes[0] < 128 else "utf-16"
        self._file_text = file_bytes.decode(encoding=enc, errors='replace')
    # end function __init__

    def parse_file(self) :

        # skip some of the preamble
        full_text = self._file_text
        offset = 2000  # end of preamble in earliest tsection.dat

        # parse the section authors, eg "Sections     0-  332  original MS/KUJU sections"
        Warn.set_context(CTX_SECTION)
        section_authors_text = full_text[offset:offset+16000]  # well past the author section in version 60
        self.section_authors = Authors(MAX_INDEX+500)  # add some spare capacity
        (num_chars, num_parsed, num_warn) = self.section_authors.parse_authors('Sections', section_authors_text)
        offset += num_chars
        print(f'Info: {num_parsed} section author definitions found, {num_warn} warnings.', file=sys.stderr)

        (num_indices, num_authors) = self.section_authors.get_counts()
        print(f'Info: {num_indices} section indices have authors; {num_authors} unique section authors.', file=sys.stderr)

        # parse the track sections
        Warn.set_context(CTX_SECTION)
        (num_chars, num_parsed, num_warn, num_bad) = self.track_sections.parse_sections(full_text[offset:])
        offset += num_chars
        print(f'Info: {num_parsed} Track Section definitions found, {num_warn} warnings, {num_bad} bad blocks.', file=sys.stderr)

        (num_track_sections, num_straight, num_curved_left, num_curved_right) = self.track_sections.get_counts()
        print(f'Info: {"Total": >12} {T_STRAIGHT: >12} {T_CURVED_LEFT: >12} {T_CURVED_RIGHT: >12}', file=sys.stderr)
        print(f'Info: {num_track_sections: >12} {num_straight: >12} {num_curved_left: >12} {num_curved_right: >12}', file=sys.stderr)

        # parse the shape authors, eg "Shapes     0-  332  original MS/KUJU sections"
        Warn.set_context(CTX_SHAPE)
        shape_authors_text = full_text[offset:offset+16000]  # well past the author section in version 60
        self.shape_authors = Authors(MAX_INDEX+500)  # add some spare capacity
        (num_chars, num_parsed, num_warn) = self.shape_authors.parse_authors('Shapes', shape_authors_text)
        offset += num_chars
        print(f'Info: {num_parsed} shape author definitions found, {num_warn} warnings.', file=sys.stderr)

        (num_indices, num_authors) = self.shape_authors.get_counts()
        print(f'Info: {num_indices} shape indices have authors; {num_authors} unique shape authors.', file=sys.stderr)

        # parse the track shapes
        Warn.set_context(CTX_SHAPE)
        (num_chars, num_parsed, num_warn, num_bad) = self.track_shapes.parse_shapes(full_text[offset:])
        offset += num_chars
        print(f'Info: {num_parsed} Track Shape definitions found, {num_warn} warnings, {num_bad} bad blocks.', file=sys.stderr)

        (num_track_shapes, num_roads, num_tracks, num_junctions, num_crossings) = self.track_shapes.get_counts()
        print(f'Info: {"Total": >12} {C_ROAD: >12} {T_TRACK: >12} {T_JUNCTION: >12} {T_CROSSING: >12}', file=sys.stderr)
        print(f'Info: {num_track_shapes: >12} {num_roads: >12} {num_tracks: >12} {num_junctions: >12} {num_crossings: >12}', file=sys.stderr)


    # end function parse_file

# end class TSectionDatFile

########################################################################


def skip_to_end_of_block(block_text, start_pos, limit) :
    """Skip to the end of the block. Handles nested sub-blocks.
    start_pos is where to start searching for the end of the block.
    limit is the maximum number of characters to search across."""
    char_cnt = 1 ; sub_block_cnt = 0
    for i in range(start_pos, start_pos+limit) :
        if block_text[i] == ')' and sub_block_cnt == 0 : break
        elif block_text[i] == ')' : sub_block_cnt -= 1
        elif block_text[i] == '(' : sub_block_cnt += 1
        char_cnt += 1
    return char_cnt + 1
# end of function skip_to_end_of_block


if __name__ == "__main__" :
    import argparse

    warn_scope = [] ; warn_level = 0

    parser = argparse.ArgumentParser(description='''Parse the specified tsection.dat file.''')
    parser.add_argument('tsection_file_path', type=pathlib.Path, help='The path to the tsection.dat file.')
    parser.add_argument('-da', '--dump_all', action='store_true', help='Dump everything.')
    parser.add_argument('-d1a', '--dump_section_authors', action='store_true', help='Dump the list of section authors.')
    parser.add_argument('-d1', '--dump_sections', action='store_true', help='Dump the list of track section.')
    parser.add_argument('-d2a', '--dump_shape_authors', action='store_true', help='Dump the list of shape authors.')
    parser.add_argument('-d2', '--dump_shapes', action='store_true', help='Dump the list of track shapes.')
    parser.add_argument('-wa', '--warn_all', action='store_true', help='Output all types of warnings.')
    parser.add_argument('-w1', '--warn_sections', action='store_true', help='Output warnings on sections.')
    parser.add_argument('-w2', '--warn_shapes', action='store_true', help='Output warnings on shapes.')
    parser.add_argument('-wl', '--warn_level',type=int, default=0, help='Suppress warnings above this level.')
    parser.add_argument('-wd', '--warn_detail', action='store_true', help='Include additional details in warnings.')

    args = parser.parse_args()
    tsection_file_path = args.tsection_file_path
    dump_all = args.dump_all
    dump_section_authors = args.dump_section_authors ; dump_sections = args.dump_sections
    dump_shape_authors = args.dump_shape_authors ; dump_shapes = args.dump_shapes
    if args.warn_sections : warn_scope.append(CTX_SECTION)
    if args.warn_shapes : warn_scope.append(CTX_SHAPE)
    if args.warn_all : warn_scope = [CTX_ALL]
    warn_level = args.warn_level ; warn_detail = args.warn_detail

    Warn.set_scope_and_level(warn_scope, warn_level, warn_detail)

    if not tsection_file_path.is_file() :
        print( 'Error: Track Sections file "{}" does not exist.'.format(tsection_file_path), file=sys.stderr)
        sys.exit(1)

    tsection_dat = TSectionDatFile(tsection_file_path)
    tsection_dat.parse_file()

    # dump section authors
    if dump_all or dump_section_authors :
        print('\nSection Authors (by number of sections descending)')
        authors = tsection_dat.section_authors.get_counts_per_author()
        counts = sorted(((v, k) for k, v in authors.items()), reverse=True)
        for (cnt , name) in counts :
            print(f'{cnt: >5d}\t{name}')
        sys.stdout.flush()

    # dump track sections
    if dump_all or dump_sections :
        print(f'\nTrack Sections\n{TrackSection.format_header()}')
        for ts in tsection_dat.track_sections.list :
            if ts is not None and ts.index >= 0 : print(ts.format_row())
        sys.stdout.flush()

    # dump shape authors
    if dump_all or dump_shape_authors :
        print('\nShape Authors (by number of shapes descending)')
        authors = tsection_dat.shape_authors.get_counts_per_author()
        counts = sorted(((v, k) for k, v in authors.items()), reverse=True)
        for (cnt , name) in counts :
            print(f'{cnt: >5d}\t{name}')
        sys.stdout.flush()

    # dump track shapes
    if dump_all or dump_shapes :
        print(f'\nTrack Shapes\n{TrackShape.format_header()}')
        for ts in tsection_dat.track_shapes.list :
            if ts is not None and ts.index >= 0 : print(ts.format_row())
        sys.stdout.flush()

    exit(0)
# end of file orts_tsection_dat.py
