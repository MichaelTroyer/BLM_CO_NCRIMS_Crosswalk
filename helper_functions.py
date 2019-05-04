from collections import Counter
import dateutil
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
    

def tryParseDate(date):
    # Python Cookbook - Ver 2 - Recipe 3.7
    # dateutil.parser expects a string
    inPut = date
    kwargs = {}
    if isinstance(date, (list, tuple)):
        date = ' '.join([str(x) for x in date])
    if isinstance(date, int):
        date = str(date)
    if isinstance(date, dict):
        kwargs = date
        date = kwargs.pop('date')
    try:
        try:
            parsedate = dateutil.parser.parse(date, **kwargs)
            return parsedate.date()
        except ValueError:
            parsedate = dateutil.parser.parse(date, fuzzy=True, **kwargs)
            return parsedate.date()
    except:
        raise FormatDateError(date)


def format_data(input_data, dest_params):
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
    except:
        raise FormatDataError(input_data, dest_params)


def get_most_common_with_ties(values):
    '''
    Find the most common values in a list of values. Will also check for ties.
    Returns a tuple (boolean flag - was there a tie?, most common value(s)).
    '''
    try:
        # Value frequency
        value_counts = Counter(values)
        # Get the frequency of counts
        frequency_counts = value_counts.values()
        # If the most common count frequency is greater than 1, there is a tie for most common value
        most_frequent_count = Counter(frequency_counts).most_common(1)[0][1]
        if most_frequent_count > 1:
            # Tie = True, return the most common values
            return (True, value_counts.most_common(most_frequent_count))
        else:
            # Tie = False, return the most common value
            return (False, value_counts.most_common(1))
    except:
        raise ValueCountError(values)


def replace_all(text, replace_dict):
    for src, tgt in replace_dict.iteritems():
        text = text.replace(src, tgt)
    return text


def extract_parentheticals(text):
    # Exract and clean all parenthetical groups > 1 char in length
    # Get the outermost parentheticals
    parens = text[text.find("(")+1:text.rfind(")")]
    # Split on space and remove all the weird stuff - drop any single characters
    clean_parens = [
        p for p
        in replace_all(parens, {'(': ' ', ')': ' '}).split()
        if len(p) > 1]
    return text, clean_parens


def map_domain_values(raw_value, domain_mapping_dict):
    """Translate raw_value against domain mapping.
    Return None if not found"""
    return domain_mapping_dict.get(raw_value, None)


def parse_assessment_criteria(four_tuple):  # (A, B, C, D) - Yes/No
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


def extract_nepa_ids(string):
    # Matching DOI-BLM-CO-F(digits, maybe oO)-date-seq type
    regex = r'DOI-BLM-CO-F[0-9oO]{1,5}-\d{2,4}-\d{1,4}[- ]\w+'  
    return re.findall(regex, string)


def get_BLM_acres(fc, blm_lyr, id_field, workspace='in_memory'):
    """
    fc: the input feature class to calculate BLM acres
    blm_lyr: a feature layer of BLM lands specifically
    id_field: a unique id field for the source fc
    workspace: output location - defaults to in_memory

    Intersect fc with blm_lyr, dissolve intersect on id_field,
    add and calc acres field and update fc with calculated acreage
    using a search cursor on the dissolved feature class
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
    with arcpy.da.UpdateCursor(fc, [id_field, acre_field]) as cur:
        for row in cur:
            try:
                row[1] = fea_acres[row[0]]
            except KeyError:
                # In case some did not intersect blm_lyr
                row[1] = 0.0
            cur.updateRow(row)