import dateutil
import re

import arcpy


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


def compare_schema(src, dst):
    src_schema = set([(f.name.upper(), f.type, f.length) for f in arcpy.ListFields(src)])
    dst_schema = set([(f.name.upper(), f.type, f.length) for f in arcpy.ListFields(dst)])
    for dst_scheme in dst_schema:
        if not dst_scheme in src_schema and not dst_scheme[0] in \
            ['SHAPE.AREA', 'SHAPE.LEN', 'SHAPE.LENGTH']:
            # bool, the unmatched dst field
            return False, dst_scheme 
    return True,


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


def get_acres(fc):
    """Check for an acres field in fc - create if doesn't exist or flag for calculation.
       Recalculate acres and return name of acre field"""
    # Add ACRES field to analysis area - check if exists
    field_list = [field.name for field in arcpy.ListFields(fc) if field.name.upper() == "ACRES"]
    # If ACRES/Acres/acres exists in table, flag for calculation instead
    if field_list:
        acre_field = field_list[0] # select the 'acres' variant
    else:
        arcpy.AddField_management(fc, "ACRES", "DOUBLE", 15, 2)
        acre_field = "ACRES"
    arcpy.CalculateField_management(fc, acre_field, "!shape.area@ACRES!", "PYTHON_9.3")
    return acre_field


def clean_string(string):
    string = string.strip() if string else None
    return string
    

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
        return None


def format_data(input_data, dest_params):
    '''accepts an input dictionary of field format parameters and matches input data to it
       note: the state standard only includes text, double, and date formats'''
    # string, date, double
    if dest_params['TYPE'] == 'String':
        # make sure is not too long
        max_length = dest_params['LENGTH']
        if len(input_data) > max_length:
            clean_data = input_data[:max_length]
        else: clean_data = input_data
    if dest_params['TYPE'] == 'Double':
        # make sure is type 'float'
        clean_data = float(input_data)
    if dest_params['TYPE'] == 'Date':
        # parse date - try to..
        clean_data = tryParseDate(input_data)
    return clean_data


def extract_parentheticals(string):
    parentheticals = re.findall(r'\(\w*\)', string)
    if parentheticals:
        string = re.sub(r'\(\w*\)', '', string)
    return string, parentheticals


def map_domain_values(raw_value, domain_mapping_dict):
    return domain_mapping_dict.get(raw_value, None)


def split_and_map_domain_values(raw_value, domain_mapping_dict, delimiter='>'):
    vals = raw_value.split(delimiter)
    vals = [clean_string(v) for v in vals if v]  # No None, no weird stuff
    vals = [domain_mapping_dict.get(v, None) for v in vals]
    # Can implment polling here..
    return vals


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


#TODO: Please god test this!
def extract_nepa_ids(string):
    regex = r'DOI-BLM-CO-F[0-9oO]{1,5}-\d{2,4}-\d{1,4}[- ]\w+'  # Matching DOI-BLM-CO-F(digits, maybe oO)-date-seq type
    return re.findall(regex, string)