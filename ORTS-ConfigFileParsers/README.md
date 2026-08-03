# MSTS / ORTS Config File Parsers

This is an attempt at a generic (context-unaware) parser for MSTS / Open Rails config file.
The main focus is **eng and wag files**, but if practical other file types should also be supported.
The end-goal is to support **comparison** of config files (this is hard as config files don't have any specific order).

## ORTS-ParseConfigFile.py (in Python)

Python version of the parser.
Parses the config file into tokens, builds a tree, and outputs in one of the following formats:
* msts: essentially the same format as the input (should be able to use this in place of the original)
* dot: connecting the keywords with dots (similar to INI files), so that the list can be sorted and compared

#### Status

* First version, with significant limitations. See the header for details.
* Does not handle includes, compression, binary files, ORTS sub-folders.
* Reasonable at parsing standard eng/wag files and tsection.dat. Fails for shape (.s) files.
* Dot notation does not handle repeated keywords (eg. lights). Need to add identifier for each instance.

  This is not trivial. Some repetitions have identifiers (eg. TrackShape), others do not (eg. Lights). 
  For those that don't, using the order in which they are in the file may not create reasonable matches when trying to compare.

## ParseConfigFile (in Lark)

An attempt to parse using [Lark](https://github.com/lark-parser/lark) and the [extended Backus-Naur Form](https://en.wikipedia.org/wiki/Extended_Backus%E2%80%93Naur_form) (EBNF).

This has been abandoned, as the parsed try is not in a format that I was looking for (keywords and values).
Also, the error handling seems not great, it was hard to find where EBNF definition errors.

It was a good learning experience, though.

Last updated: Aug 2026
