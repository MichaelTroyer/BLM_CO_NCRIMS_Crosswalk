from collections import Counter
from dateutil.parser import parse
import datetime
import os
import re

import arcpy

from custom_exceptions import FormatDataError
from custom_exceptions import FormatDateError
from custom_exceptions import ValueCountError


def deleteInMemory():
    """Delete in memory tables and feature classes
       reset to original worksapce when done"""
    # get the original workspace location
    orig_workspace = arcpy.env.workspace
    # Set the workspace to in_memory
    arcpy.env.workspace = "in_memory"
    # Delete all in memory feature classes
    fcs = arcpy.ListFeatureClasses()
    if len(fcs) > 0:
        for fc in fcs:
            arcpy.Delete_management(fc)
    # Delete all in memory tables
    tbls = arcpy.ListTables()
    if len(tbls) > 0:
        for tbl in tbls:
            arcpy.Delete_management(tbl)
    # Reset the workspace
    arcpy.env.workspace = orig_workspace


def buildWhereClauseFromList(table, field, valueList):
    """Takes a list of values and constructs a SQL WHERE
       clause to select those values within a given field and table."""
    # Add DBMS-specific field delimiters
    fieldDelimited = arcpy.AddFieldDelimiters(arcpy.Describe(table).path, field)
    # Determine field type
    fieldType = arcpy.ListFields(table, field)[0].type
    # Add single-quotes for string field values
    if str(fieldType) == 'String':
        valueList = ["'%s'" % value for value in valueList]
    # Format WHERE clause in the form of an IN statement
    whereClause = "%s IN(%s)" % (fieldDelimited, ', '.join(map(str, valueList)))
    return whereClause
    

# def tryParseDate(date_string):
#     try:
#         return datetime.datetime.strptime(date_string, '%m/%d/%Y').date()
#     except Exception as e:
#         raise FormatDateError('could not parse date:', repr(date_string), e)
def tryParseDate(date_string):
    try:
        try:
            parsedate = parse(date_string)
            return parsedate.date()
        except ValueError:
            parsedate = parse(date_string, fuzzy=True)
            return parsedate.date()
    except Exception as e:
        raise FormatDateError('could not parse date:', repr(date_string), e)


def formatData(input_data, dest_params):
    '''accepts an input dictionary of field format parameters and matches input data to it
       note: the state standard only includes text, double, and date formats
       Will truncate text!'''
    try:
        # string, date, double
        if dest_params['TYPE'] == 'String':
            # make sure is not too long
            max_length = dest_params['LENGTH']
            clean_data = input_data[:max_length]
        if dest_params['TYPE'] == 'Double':
            # make sure is type 'float'
            clean_data = float(input_data)
        if dest_params['TYPE'] == 'Date':
            # parse date - try to..
            clean_data = tryParseDate(input_data)
        return clean_data
    except Exception as e:
        raise FormatDataError('Could not format data:', repr(input_data), repr(dest_params), e)


def getMostCommonWithTies(values):
    '''
    Find the most common values in a list of values. Will also check for ties.
    Returns a tuple (boolean flag - was there a tie?, most common value(s) and their counts).

    i.e. 
    ['a', 'b', 'c', 'd', 'a'] --> (False, [('a', 2)])
    ['a', 'b', 'a', 'b'] --> (True, [('a', 2), ('b', 2)])
    '''
    try:
        value_counts = Counter(values)
        # Get the frequency of value counts
        # This gets really meta..
        value_frequencies = value_counts.values()
        frequency_counts = Counter(value_frequencies)
        max_frequency = max(frequency_counts)
        most_frequent_count = frequency_counts[max_frequency]
        # If the most frequent count is greater than 1, there is a tie for most common value
        if most_frequent_count > 1:
            # Tie = True, return the most common values
            return (True, sorted(value_counts.most_common(most_frequent_count)))
        else:
            # Tie = False, return the most common value
            return (False, value_counts.most_common(1))
    except Exception as e:
        raise ValueCountError('Error counting values:', repr(values), e)


# def replaceAll(text, replace_dict):
#     for src, tgt in replace_dict.iteritems():
#         text = text.replace(src, tgt)
#     return text


def extractParentheticals(text):
    """
    Match single, double, and nested parentheticals.
    Return original text and a a list of parenthetical groups.
    Nested parentheticals are returned as a single entry.
    """
    parentheticals = re.findall('\(.*?\)+', text)
    return text, parentheticals
# def extractParentheticals(text):
#     """
#     Exract and clean all parenthetical groups > 1 char in length
#     Returns origianl text and a list of parentheticals contents.
#     """
#     # Get the outermost parentheticals
#     parens = text[text.find("(")+1:text.rfind(")")]
#     # Split on space and remove all the weird stuff - drop any single characters
#     clean_parens = [
#         p for p
#         in replaceAll(parens, {'(': ' ', ')': ' '}).split()
#         if len(p) > 1]
#     return text, clean_parens


def mapDomainValues(raw_value, domain_mapping_dict):
    """
    Translate raw_value against domain mapping.
    Return None if not found
    Convert raw value to upper since in memory domain mapping is all upper
    Eliminates need match case from source domain data.
    """
    return domain_mapping_dict.get(raw_value.upper(), None)
    # return domain_mapping_dict.get(raw_value, None)


def parseAssessmentCriteria(four_tuple):  # (A, B, C, D) - Yes/No
    criteria = [True if c=='Yes' else False for c in four_tuple]
    criteria_cnt = sum(criteria)
    if criteria_cnt == 4:
        return 'Eligible ((A, B and/or C) and D)'
    elif criteria_cnt in (2, 3):
        if criteria[3]:  # D
            return 'Eligible ((A, B and/or C) and D)'
        else: 
            return 'Eligible (A, B, and/or C)'
    elif criteria_cnt == 1:
        if criteria[0]: return 'Eligible A Only'
        if criteria[1]: return 'Eligible B Only'
        if criteria[2]: return 'Eligible C Only'
        if criteria[3]: return 'Eligible D Only'
    else:
        return 'Not Specified'


def extractNepaIds(string):
    # Matching DOI-BLM-CO-F(digits, maybe oO)-date-seq type
    regex = r'DOI-BLM-CO-F[0-9oO]{1,5}-\d{2,4}-\d{1,4}[- ]\w+'  
    return re.findall(regex, string)


def getBLMAcres(fc, blm_lyr, id_field, workspace='in_memory'):
    """
    fc: the input feature class to calculate BLM acres
    blm_lyr: a feature layer of BLM lands specifically
    id_field: a unique id field for the source fc
    workspace: output location - defaults to in_memory

    Intersect fc with blm_lyr, dissolve intersect on id_field,
    add and calc acres field and update fc with calculated acreage
    using a search cursor on the dissolved feature class to create a dict {id: acres}
    and subsequent update cursor on the source feature class.

    Make sure there are no duplicates first!
    """
    intersect = arcpy.Intersect_analysis(
        in_features=[fc, blm_lyr],
        out_feature_class=os.path.join(workspace, 'intersect'),
        join_attributes="ALL",
        )
    dissolve = arcpy.Dissolve_management(
        in_features=intersect,
        out_feature_class=os.path.join(workspace, 'dissolve'),
        dissolve_field=id_field,
        )
    acre_field = id_field + '_acres'
    arcpy.AddField_management(dissolve, acre_field, "DOUBLE", 15, 2)
    arcpy.CalculateField_management(dissolve, acre_field, "!shape.area@ACRES!", "PYTHON_9.3")
    fc_acres = {}
    with arcpy.da.SearchCursor(dissolve, [id_field, acre_field]) as cur:
        for row in cur:
            fc_acres[row[0]] = row[1]
    with arcpy.da.UpdateCursor(fc, [id_field, 'BLM_ACRES']) as cur:
        for row in cur:
            try:
                row[1] = fc_acres[row[0]]
            except KeyError:
                # In case some did not intersect blm_lyr
                row[1] = 0.0
            cur.updateRow(row)