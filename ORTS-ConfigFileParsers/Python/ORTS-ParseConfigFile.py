#!/usr/bin/env python3
# ORTS-ParseConfigFile - parse an MSTS-style config file and output it as a tree of keyword value pairs
#
# Copyright (c) 2026 Roger Fischer. MIT License.
#
# Limitations:
# - Does not handle ORTS include directive.
# - Does not handle ORTS subfolders (ORTS paraemters).
# - Does not handle compressed files.
# - Does not handle binary files - need token dictionary from C# for this.
# - Does not handle escaped characters (eg. \" withing a quoted string).
# - Does not handle shapes. Shapes use identifier between keyword and opening parenthesis.
# - Does not handle repeated keywords in dot notation. To be sortable, need to have an identifier (grouping).
# - Does not concatenate stings (quoted-string + quoted-string), as used in Description keyword.
#
# Assumptions:
#
# Examples:
#   ORTS-ParseConfigFile.py "C:\Games\OpenRails\Open Rails Content\BNSF Starter Route\TRAINS\trainset\SLI.BNSF\BNSF_C44_9W_4870.eng"
#   ORTS-ParseConfigFile.py "C:\Games\OpenRails\Open Rails Content\BNSF Starter Route\GLOBAL\tsection.dat"
#   ORTS-ParseConfigFile.py "C:\Games\OpenRails\Open Rails Content\BNSF Starter Route\GLOBAL-orig\SHAPES\SR_Turntable_w_37m.s.uncompressed"
#
#
# Patterns:
# - # any-text-up-to-end-of-line-or-closing-parenthesis
# - keyword ( value )
# - keyword ( value1 ... )
# - keyword ( "value-with-whitespace" )
# - keyword ( optional-values ( keyword-value-block ... ) )
# - keyword ( optional-count ( repeated-keyword ( optional-identifier keyword-value-block ... ) ... ) )
# - keyword identifier ( keyword-value-block ... ) )
# - COMMENT ( any-text-incl-whitespace-quotes-and-matching-sets-of-parenthesis )
# - SKIP ( any-text-incl-whitespace-quotes-and-matching-sets-of-parenthesis )      -- also _SKIP
# - INFO ( any-text-incl-whitespace-quotes-and-matching-sets-of-parenthesis )      -- also _INFO
#

import argparse
import pathlib
import re
import sys

# global variables
token_list = []  # list of tokens as extracted from the file; token may be keyword, value or parenthesis
num_kw = 0 ; num_val = 0
num_warn = 0 ; num_err = 0


######################################################################################
# class to hold the config tree


class TreeNode:
    """Holds a tree of nested keyword-value pairs. The root represents the config file."""

    def __init__(self, name):
        """Constructs a TreeNode, and sets its name."""
        self.name = name  # the keyword
        self.values = []  # list of values
        self.children = []  # list of child keywords (nodes)

    @property
    def has_children(self):
        """Returns True if the node has child nodes."""
        return len(self.children) > 0

    def add_value(self, value):
        """Adds a value to the tree node."""
        self.values.append(value)

    def add_value_list(self, value_list):
        """Adds a list of values to the tree node."""
        self.values.extend(value_list)

    def add_child(self, child_node):
        """Adds a child node to this node."""
        self.children.append(child_node)

    def display_dot_format(self, parents='', out_file=sys.stdout):
        """Display the tree structure using dot notation (parents prefixed with a dot separator."""
        if len(self.values) > 0 :
            print('{}{} : {}'.format(parents, self.name, ' '.join(self.values)), file=out_file, flush=True)
        for child in self.children:
            child.display_dot_format(parents + self.name + '.', out_file)

    def display_msts_format(self, level=0, out_file=sys.stdout):
        """Helper method to visualize the tree structure in the MSTS format."""
        indent = "  " * level
        end = '' if self.has_children else ' )'
        print('{}{} ( {}{}'.format(indent, self.name, ' '.join(self.values), end), file=out_file, flush=True)
        for child in self.children:
            child.display_msts_format(level + 1, out_file)
        if self.has_children :
            print('{})'.format(indent), file=out_file, flush=True)


##############################################################################
# utility functions

### read a file that is either utf-16 or utf8
def read_file(file_path):
    enc = "utf-16"
    bytes = file_path.read_bytes()
    if 0 < bytes[0] < 128: enc = 'utf-8'
    return bytes.decode(encoding=enc, errors='replace')


### tokenize the config file string
#   text: string version of the complete config file
#   current_index: the index of the character in the text string currently being processed
#   returns: the index of the next character to be processed
def tokenize_text(text, current_index) -> int:
    global token_list, num_warn, num_err
    idx = current_index
    current_token = ''

    # traverse each character in the text string
    while idx < len(text):
        char = text[idx]

        # inline comment: ignore to end-of-line or closing parenthesis
        if char == '#':
            # complete current token if any
            if current_token != '':
                token_list.append(current_token.strip())
                current_token = ''
            #  skip to the end of the line or block
            i = idx + 1
            while i < len(text) and text[i] not in (')', '\r', '\n'):
                i += 1
            idx = i
            continue

        # quoted string: collect as a single token
        if char == '"':
            # complete current token if any
            if current_token != '':
                token_list.append(current_token.strip())
                current_token = ''
            # collect everything up to the next quote as a single token
            i = idx + 1
            while i < len(text):
                if text[i] != '"' :
                    i += 1
                else :
                    # end of quoted string; save token and resume normal parsing
                    if i > idx :
                        txt = text[idx:i+1]
                        token_list.append(txt.strip())
                    i += 1
                    break
            # end while not end of quoted string
            idx = i
            continue

        # opening parentheses: add token (and some special token handling)
        if char == '(' :
            # complete current token if any
            if current_token != '':
                token_list.append(current_token.strip())
                current_token = ''
            # add open parenthesis token
            token_list.append(char)
            idx += 1
            # special tokens: collect until matching closing parenthesis
            if token_list[-2].lower() in ('comment', 'skip', 'info', '_skip', '_info') :
                i = idx ; level = 1
                while i < len(text) and level > 0 :
                    if text[i] == '(' :
                        level += 1
                    elif text[i] == ')' :
                        level -= 1
                    i += 1
                # add collected characters
                current_token = text[idx:i-1]
                token_list.append(current_token.strip())
                current_token = ''
                # add token for closing parenthesis
                if i < len(text) and text[i-1] == ')' :
                    token_list.append(text[i-1])
                idx = i + 1
            continue

        # closing parenthesis: add token
        if char == ')' :
            # complete current token if any
            if current_token != '':
                token_list.append(current_token.strip())
                current_token = ''
            # create token
            token_list.append(char)
            idx += 1
            continue

        # whitespace: ignore
        if char in (' ', '\t', '\r', '\n'):
            # complete current token if any
            if current_token != '':
                token_list.append(current_token.strip())
                current_token = ''
            # ignore
            idx += 1
            continue

        # text: add token
        current_token += char
        idx += 1
    # end while more characters in text

    if current_token:
        print('Warning: incomplete token {} at end of text to be tokenized.'.format(current_token), file=sys.stderr, flush=True)
        num_warn += 1

    return idx


# end tokenize_text()


######################################################################################
# functions to process the token list


def find_next_keyword_index(idx) -> int:
    """Finds the index of the next keyword."""
    global token_list, num_warn, num_err
    while idx < len(token_list) - 1:
        if len(token_list[idx]) > 1 and token_list[idx + 1] == '(':
            return idx
    return -1


# end find_next_keyword()


def find_next_parenthesis_index(idx) -> int:
    """Finds the index of the next opening or closing parenthesis."""
    global token_list, num_warn, num_err
    while idx < len(token_list) and token_list[idx] not in ('(', ')'):
        idx += 1
    if idx == len(token_list):
        print('Warning: missing closing parenthesis at end of file, last token is {}.'.format(token_list[idx - 1]),
              file=sys.stderr, flush=True)
        num_warn += 1
        token_list.append(')')
        idx += 1
    return idx


# end find_next_parenthesis_index()




def handle_keywords(kw_idx, parent_node, level=0) -> int:
    """Handle all keywords at this level. Create keyword node, add it as a child, and collect values.
    Loop for keywords at the same level. Recurse when a nested keyword is encountered.
    Returns index of next token."""
    global token_list, num_warn, num_err
    next_kw_idx = kw_idx

    # while more keywords
    while next_kw_idx < len(token_list) - 1:
        keyword = token_list[next_kw_idx]

        if verbose > 1: print('Info: new level {} keyword {} at token idx {}'.format(level, keyword, next_kw_idx),
                              file=sys.stderr, flush=True)

        if keyword in ('(', ')') :
            print('Warning: expected a keyword, got {} at index {} in {}'.format(keyword, next_kw_idx, token_list[next_kw_idx-1:next_kw_idx+2]),
                  file=sys.stderr, flush=True)
            num_warn += 1
            next_kw_idx = find_next_keyword_index(next_kw_idx)

        new_node = TreeNode(keyword)
        parent_node.add_child(new_node)
        first_val_idx = next_kw_idx + 2
        end_idx = find_next_parenthesis_index(first_val_idx)
        last_val_idx = end_idx - 1 if token_list[end_idx] != '(' else end_idx - 2
        if last_val_idx >= first_val_idx:
            new_node.add_value_list(token_list[first_val_idx:last_val_idx + 1])

        # if next is a nested token, recurse
        if token_list[end_idx] == '(':
            next_kw_idx = handle_keywords(end_idx - 1, new_node, level+1) + 1
            if next_kw_idx < len(token_list) - 1 and token_list[next_kw_idx] == ')' :
                return next_kw_idx

        # else if end of keyword, end loop
        elif token_list[end_idx + 1] == ')':
            return end_idx + 1

        # else, continue with next keyword
        else:
            next_kw_idx = end_idx + 1
    # end while more keywords

    return next_kw_idx


# end handle_keywords()


#######################################################################
# main


# handle arguments
parser = argparse.ArgumentParser(description='Parse an MSTS-style config file and output it as a token tree.')
parser.add_argument('file_path', type=pathlib.Path, help='Relative or absolute path to the config file to be parsed.')
parser.add_argument('-f', '--format', help='The output format: msts, dot, or none (default).', default='none')
parser.add_argument('-v', '--verbose', action='count', default=0)
args = parser.parse_args()
file_path = args.file_path
out_format = args.format
verbose = args.verbose

if not file_path.is_file():
    print('Error: {} is not a file.'.format(args.file_path), file=sys.stderr, flush=True)
    num_err += 1
    sys.exit(1)

# read the file
file_text = read_file(file_path)

# handle compressed file
if file_text.startswith('SIMISA@F'):
    print('Compressed file, not yet implemented.', file=sys.stderr, flush=True)
    exit(0)

# skip preamble
preamble_txt = ''
starting_index = 0
if file_text.startswith('SIMISA'):
    offset = min(file_text.find('\r', 0, 32), file_text.find('\n', 0, 32))
    if offset > 0:
        starting_index = offset
        preamble_txt = file_text[0:offset] + '\n'

# split the text into tokens
ending_index = tokenize_text(file_text, starting_index)

if ending_index != len(file_text):
    print('Warning: tokenizer stopped before end of file, leaving {}.'.format(file_text[ending_index:]),
          file=sys.stderr, flush=True)
    num_warn += 1

if verbose > 0: print(token_list, file=sys.stderr, flush=True)

# create the root node
root_node = TreeNode(file_path.name)
root_node.add_value(str(file_path.parent))
current_node = root_node

# first token should be a keyword
first_kw_idx = find_next_keyword_index(0)
if first_kw_idx < 0:
    print('Error: No keyword found in file {}'.format(file_path), file=sys.stderr, flush=True)
    num_err += 1
    exit(1)
elif first_kw_idx != 0:
    print('Warning: File {} does not start with a keyword. {}'.format(file_path, file_text[0:50]), file=sys.stderr, flush=True)
    num_warn += 1

# process the first token, recursively handling nested keywords
last_idx = handle_keywords(first_kw_idx, root_node)
if last_idx != len(token_list):
    print('Warning: File {} does not end with a closing parenthesis. {}'.format(file_path,
                                                                                file_text[len(file_text) - 50:]),
          file=sys.stderr, flush=True)
    num_warn += 1

# output the result
if out_format == 'msts' :
    print(preamble_txt)
    for node in root_node.children :
        node.display_msts_format()
elif out_format == 'dot' :
    print(root_node.values, root_node.name)
    for node in root_node.children :
        node.display_dot_format()

print( '{} errors, {} warnings'.format(num_err, num_warn), file=sys.stderr, flush=True)
exit(0)
