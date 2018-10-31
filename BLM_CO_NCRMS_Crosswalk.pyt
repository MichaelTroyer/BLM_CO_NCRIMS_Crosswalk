# -*- coding: utf-8 -*-


###################################################################################################
##
## FRONT MATTER
##
###################################################################################################
"""
  ____  _     __  __     ____ ___     _   _  ____ ____  __  __ ____  
 | __ )| |   |  \/  |   / ___/ _ \   | \ | |/ ___|  _ \|  \/  / ___| 
 |  _ \| |   | |\/| |  | |  | | | |  |  \| | |   | |_) | |\/| \___ \ 
 | |_) | |___| |  | |  | |__| |_| |  | |\  | |___|  _ <| |  | |___) |
 |____/|_____|_|_ |_|__ \____\___/__ |_| \_|\____|_| \_\_|  |_|____/ 
       / ___|  _ \ / _ \/ ___/ ___\ \      / / \  | |   | |/ /       
      | |   | |_) | | | \___ \___ \\ \ /\ / / _ \ | |   | ' /        
      | |___|  _ <| |_| |___) |__) |\ V  V / ___ \| |___| . \        
       \____|_| \_\\___/|____/____/  \_/\_/_/   \_\_____|_|\_\

Author:             
Michael Troyer    ¯\_(ツ)_/¯

Date:
10/25/2018

Purpose:

Usage:


"""
# TODO: finish up the documen..

###################################################################################################
##
## IMPORTS
##
###################################################################################################

from __future__ import division
from collections import defaultdict
import copy
import csv
import datetime
import getpass
import os
import re
import sys
import traceback

import arcpy

from exceptions import *
from helper_functions import *
from log_handler import pyt_log


###################################################################################################
##
## GLOBALS
##
###################################################################################################

arcpy.env.addOutputsToMap = False
arcpy.env.overwriteOutput = True

user = getpass.getuser()
start_time = datetime.datetime.now()
date_time_stamp = re.sub('[^0-9]', '', str(start_time)[2:16])

log_path = r'T:\CO\GIS\gistools\tools\Cultural\z_logs\NCRMS_Crosswalk_Log.txt'
gdb_template_xml = r'T:\CO\GIS\gistools\tools\Cultural\NCRMS_Crosswalk\src\database_schema.xml'
domain_map_csv = r'T:\CO\GIS\gistools\tools\Cultural\NCRMS_Crosswalk\src\domain_map.csv'

### Exceptions
class ConditionDomainError(BaseException):
    def __init__(self, val):
        self.val = val
class AssessmentDomainError(BaseException):
    def __init__(self, val):
        self.val = val
class AssessmentDateError(BaseException):
    def __init__(self, val):
        self.val = val
class AssessmentAuthorityDomainError(BaseException):
    def __init__(self, val):
        self.val = val
class AssessmentCriteriaDomainError(BaseException):
    def __init__(self, val):
        self.val = val
class TemporalAssessmentDomainError(BaseException):
    def __init__(self, val):
        self.val = val
        

###################################################################################################
##
## EXECUTION
##
###################################################################################################

class Toolbox(object):
    def __init__(self):
        self.label = "BLM_CO_NCRMS_Crosswalk_Toolbox"
        self.alias = "BLM CO NCRMS Crosswalk Toolbox"

        # List of tool classes associated with this toolbox
        self.tools = [Crosswalk_NCRMS_Site_Data]


class Crosswalk_NCRMS_Site_Data(object):
    def __init__(self):
        self.label = "Crosswalk_NCRMS_Site_Data"
        self.description = ""
        self.canRunInBackground = True 

    def getParameterInfo(self):
        """Define parameter definitions"""

        ## PARAMETERS

        # Input SHPO Geodatabase
        src_gdb=arcpy.Parameter(
            displayName="Input SHPO Geodatabase",
            name="Input_fgdb",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
            )
        
        # Output Location
        out_gdb=arcpy.Parameter(
            displayName="Output Workspace",
            name="Out_Workspace",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
            )

        parameters = [src_gdb, out_gdb]
        return parameters


    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True


    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        # Defaults for easier testing - drop for prduction
        if not parameters[0].altered:
            parameters[0].value = r'T:\CO\GIS\gisuser\rgfo\mtroyer\z-Scratch\NCRMS_Testing\blm_full_format_181019.gdb'
            parameters[1].value = r'T:\CO\GIS\gisuser\rgfo\mtroyer\z-Scratch\NCRMS_Testing\test_output'
        return


    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return


###################################################################################################
##
## MAIN PROGRAM
##
###################################################################################################

    def execute(self, parameters, messages):
        """The source code of the tool."""

        try:
            # Clear memory JIC
            deleteInMemory()
            
            # get the input gdb and output file paths
            input_path = parameters[0].valueAsText
            output_path = parameters[1].valueAsText

            # Create the logger
            report_path = os.path.join(output_path, "BLM_CO_NCRMS_Crosswalk_Report_{}.txt".format(date_time_stamp))
            logger = pyt_log(report_path, log_path)
            
            # Start logging
            logger.log_all("BLM CO NCRMS Data Crosswalk {}".format(datetime.datetime.now()))
            logger.log_report("{}\n".format('-'*120))
            logger.log_all("Running environment: Python - {}\n".format(sys.version))
            logger.log_all("User: {}\n".format(user))

            # Create goedatabase
            gdb_name = 'BLM_CO_NCRMS_Crosswalk_{}'.format(date_time_stamp)
            arcpy.CreateFileGDB_management(output_path, gdb_name, "10.0")
            gdb_name = os.path.join(output_path, gdb_name) + '.gdb'
            # Schema from XML
            arcpy.ImportXMLWorkspaceDocument_management(gdb_name, gdb_template_xml, 'SCHEMA_ONLY')

            # Set workspace to fGDB
            arcpy.env.workspace = gdb_name
            logger.log_all("Output Location:\n")
            logger.log_all('\t{}\n'.format(gdb_name))

            # Remove the old [CRM_Resources] - replace with input data copy - mod in place
            arcpy.Delete_management(os.path.join(gdb_name, 'CRM_Resources'))

            # Get the output feature class paths and duplicate table path
            success = os.path.join(gdb_name, 'CRM_Resources')
            failure = os.path.join(gdb_name, 'CRM_Resources_fails')
            duplicates = os.path.join(gdb_name, 'CRM_Resources_duplicates')
            # Get the site survey M-M table
            site_survey_map_table = os.path.join(gdb_name, 'CRM_RSRCE_INVSTGTN_TBL')

            # Copy input fc to database and get as a feature layer
            # Will be success layer, failures will be copied to <faliure> and removed
            input_fc = os.path.join(input_path, 'BLM_CO_Sites')
            arcpy.CopyFeatures_management(input_fc, success)
            working_lyr = arcpy.MakeFeatureLayer_management(success, r'in_memory\lyr')

            # Check for duplicates
            id_field = 'SITE_'
            arcpy.FindIdentical_management(working_lyr, duplicates, id_field, output_record_option='ONLY_DUPLICATES')
            if int(arcpy.GetCount_management(duplicates).getOutput(0)):
                logger.log_all('WARNING: Duplicate Site IDs found - see duplicate table for details')

            n_rows = int(arcpy.GetCount_management(working_lyr).getOutput(0))
            logger.log_all('{} total rows..'.format(n_rows))

            ### Add the target fields ###
            target_schema = {
                'RSRCE_AGCY_ID'             : {'ALIAS': 'Agency Resource Identifier', 'LENGTH': 50, 'TYPE': 'String', 'DOMAIN': None,  'DEFAULT': None,},
                'RSRCE_SHPO_ID'             : {'ALIAS': 'SHPO Database Resource Identifier', 'LENGTH': 50, 'TYPE': 'String', 'DOMAIN': None, 'DEFAULT': None,},
                'RSRCE_NM'                  : {'ALIAS': 'Resource Name', 'LENGTH': 255, 'TYPE': 'String', 'DOMAIN': None, 'DEFAULT': None,},
                'RSRCE_TMPRL_CLTRL_ASGNMNT' : {'ALIAS': 'Resource Temporal Cultural Assignment', 'LENGTH': 50, 'TYPE': 'String', 'DOMAIN': 'CRM_DOM_RSRCE_TMPRL_CLTRL_ASGNMNT', 'DEFAULT': 'Unknown',},
                'RSRCE_PRMRY_PRPRTY_CL'     : {'ALIAS': 'Resource Primary Property Class', 'LENGTH': 30, 'TYPE': 'String', 'DOMAIN': 'CRM_DOM_RSRCE_PRMRY_PRPRTY_CL', 'DEFAULT': 'Site',},
                'RSRCE_PRMRY_CAT_NM'        : {'ALIAS': 'Resource Primary Category Name', 'LENGTH': 30, 'TYPE': 'String', 'DOMAIN': 'CRM_DOM_RSRCE_PRMRY_CAT', 'DEFAULT': 'Unknown',},
                'RSRCE_CAT'                 : {'ALIAS': 'Resource Category', 'LENGTH': 2000, 'TYPE': 'String', 'DOMAIN': None, 'DEFAULT': None,},
                'RSRCE_NRHP_ELGBLE_STTS'    : {'ALIAS': 'Resource NRHP Eligibility Status', 'LENGTH': 12, 'TYPE': 'String', 'DOMAIN': 'DOM_YES_NO_UNDTRMND', 'DEFAULT': 'Undetermined',},
                'RSRCE_NRHP_ELGBLE_CRTRA'   : {'ALIAS': 'NRHP Eligibility Criteria', 'LENGTH': 35, 'TYPE': 'String', 'DOMAIN': 'CRM_DOM_RSRCE_NRHP_ELGBLE_CRTRA', 'DEFAULT': 'Not Specified',},
                'RSRCE_NRHP_ELGBLE_AUTH_NM' : {'ALIAS': 'Resource NRHP Eligibility Authority Name', 'DOMAIN': 'CRM_DOM_ RSRCE_NRHP_ELGBLE_AUTH_NM', 'DEFAULT': 'NA', 'LENGTH': 35, 'TYPE': 'String',},
                'RSRCE_CNDTN_ASSMNT'        : {'ALIAS': 'Resource Condition Assessment', 'DOMAIN': 'CRM_DOM_RSRCE_CNDTN_ASSMNT', 'DEFAULT': 'Unknown', 'LENGTH': 50, 'TYPE': 'String',},
                'RSRCE_LAST_RCRD_DT'        : {'ALIAS': 'Resource Last Recorded Date', 'DOMAIN': None, 'DEFAULT': None, 'LENGTH': 20, 'TYPE': 'String',},
                'RSRCE_DATE'                : {'ALIAS': 'Resource Last Recorded Date in Date Format', 'DOMAIN': None, 'DEFAULT': None, 'LENGTH': 20, 'TYPE': 'Date',},
                'RSRCE_CLCTN_PRFRM_STTS'    : {'ALIAS': 'Resource Collection Performed Status', 'DOMAIN': 'CRM_DOM_RSRCE_CLCTN_PRFRM_STTS', 'DEFAULT': 'Unknown', 'LENGTH': 20, 'TYPE': 'String',},
                'RSRCE_DATA_SRCE'           : {'ALIAS': 'Resource Data Source', 'DOMAIN': 'CRM_DOM_DATA_SRCE', 'DEFAULT': 'Unknown', 'LENGTH': 25, 'TYPE': 'String',},
                'RSRCE_SPTL_CLCTN_MTHD'     : {'ALIAS': 'Resource Spatial Collection Method', 'DOMAIN': 'CRM_DOM_SPTL_CLCTN_MTHD', 'DEFAULT': 'Unknown', 'LENGTH': 30, 'TYPE': 'String',},
                'RSRCE_CMT'                 : {'ALIAS': 'Resource Comments', 'DOMAIN': None, 'DEFAULT': None, 'LENGTH': 2000, 'TYPE': 'String',},
                'RSRCE_SITE_DOC_ID'         : {'ALIAS': 'Report ID', 'DOMAIN': None, 'DEFAULT': None, 'LENGTH': 255, 'TYPE': 'String',},
                'RSRCE_SITE_DOC_NAME'       : {'ALIAS': 'Report Name', 'DOMAIN': None, 'DEFAULT': None, 'LENGTH': 2000, 'TYPE': 'String',},
                'ADMIN_ST'                  : {'ALIAS': 'Administrative State Code', 'DOMAIN': 'DOM_ADMIN_ST', 'DEFAULT': None, 'LENGTH': 2, 'TYPE': 'String',},
                }

            for field_name, field_params in target_schema.items():
                arcpy.AddField_management(
                    in_table=working_lyr,
                    field_name=field_name,
                    field_type=field_params['TYPE'],
                    field_length=field_params['LENGTH'],
                    field_alias=field_params['ALIAS'],
                    field_domain=field_params['DOMAIN'],
                    )
                logger.log_all('Added field [{}]'.format(field_name))
 
            ### Get the related table data ###
            assessment_table = os.path.join(input_path, 'Assessment')
            condition_table = os.path.join(input_path, 'Condition')
            organization_table = os.path.join(input_path, 'Organization')
            # Probably faster with SQL...
            # Get most recent value and date for each site in [Assessment, Condition, Organization]
            # dict: {table: {site_id: {value: val, date: dt}}}
            tbl_updates = {
                'Assessment'   : {},
                'Condition'    : {},
                'Organization' : {},
                }
            for tbl, updates in tbl_updates.items():
                path = os.path.join(input_path, tbl)
                logger.log_all('Collecting updates from {} table..'.format(tbl))
                with arcpy.da.SearchCursor(path, ['Site_ID', tbl, 'Date']) as cur:
                    for site_id, val, dt in cur:
                        if not dt: continue  # Skip null
                        if not val: continue  # Skip null
                        if not val.strip(): continue  # skip empty strings - needed?
                        if site_id in updates:  # default to keys
                            if dt > updates[site_id]['date']:
                                updates[site_id] = {tbl: val, 'date': dt}
                        else:
                            updates[site_id] = {tbl: val, 'date': dt}
                logger.log_all('{} unique records: {}'.format(tbl, len(tbl_updates[tbl])))

            # Get the collection status from condition table
            collections = {}
            with arcpy.da.SearchCursor(condition_table, ['Site_ID', 'Condition']) as cur:
                for site_id, cond in cur:
                    if not cond: continue
                    if site_id in collections:
                        if collections[site_id]: continue  # Aready True
                    if 'Collected' in cond or 'Excavated' in cond:
                        collections[site_id] = True
                    else:
                         collections[site_id] = False

            # Read in the domain mapping from CSV - necessary to keep up with dosource SHPO 'domain' changes
            domain_mapping = defaultdict(dict)

            logger.log_all('Reading domain table..')
            with open(domain_map_csv, 'r') as f:
                csv_reader = csv.reader(f)
                # Skip the header row
                csv_reader.next()
                for domain, src_val, dmn_val in csv_reader:
                    domain_mapping[domain][src_val] = dmn_val

            NCRMS_fields = sorted(target_schema.keys())
            SHPO_fields = [
                'SITE_', 'site_doc_id', 'site_doc_name', 'name',
                'resource_type', 'culture',  'archaeology', 'site_type',
                'NRC_A', 'NRC_B', 'NRC_C', 'NRC_D',
                'feature', 'artifact',
            ]
            error_rows = []
            logger.log_all('Iterating rows..')
            update_fields = ['OBJECTID'] + SHPO_fields + NCRMS_fields
            logger.logfile('Update fields:', update_fields)
            report_ix = 1

            site_survey_mapping = []


###################################################################################################
##
## MAIN PROCESSING LOOP
##
###################################################################################################

            with arcpy.da.UpdateCursor(working_lyr, update_fields) as cur:
                for row in cur:
                    if report_ix % 5000 == 0:
                        logger.console('Processed {} of {} rows..'.format(report_ix, n_rows))

                    try:
                        OBJECTID       = row[0]  # Used
                        SITE_          = row[1]  # Used              
                        site_doc_id    = row[2]  # Used
                        site_doc_name  = row[3]  # Used
                        name           = row[4]  # Used
                        resource_type  = row[5]  # Used
                        culture        = row[6]
                        archaeology    = row[7]  # Used
                        site_type      = row[8]  # Used
                        NRC_A          = row[9]  # Used
                        NRC_B          = row[10]  # Used
                        NRC_C          = row[11]  # Used
                        NRC_D          = row[12]  # Used
                        feature        = row[13]  # Used
                        artifact       = row[14]  # Used

                        # Clean the strings - no weird surprises!
                        SITE_          = clean_string(SITE_)              
                        site_doc_id    = clean_string(site_doc_id)
                        site_doc_name  = clean_string(site_doc_name)
                        name           = clean_string(name) 
                        resource_type  = clean_string(resource_type) 
                        culture        = clean_string(culture)
                        archaeology    = clean_string(archaeology)
                        site_type      = clean_string(site_type)
                        NRC_A          = clean_string(NRC_A)
                        NRC_B          = clean_string(NRC_B)
                        NRC_C          = clean_string(NRC_C)
                        NRC_D          = clean_string(NRC_D)
                        feature        = clean_string(feature)
                        artifact       = clean_string(artifact)                       

                        # 15 ADMIN_ST
                        # 16 RSRCE_AGCY_ID
                        # 17 RSRCE_CAT
                        # 18 RSRCE_CLCTN_PRFRM_STTS
                        # 19 RSRCE_CMT
                        # 20 RSRCE_CNDTN_ASSMNT
                        # 21 RSRCE_DATA_SRCE
                        # 22 RSRCE_DATE
                        # 23 RSRCE_LAST_RCRD_DT
                        # 24 RSRCE_NM
                        # 25 RSRCE_NRHP_ELGBLE_AUTH_NM
                        # 26 RSRCE_NRHP_ELGBLE_CRTRA
                        # 27 RSRCE_NRHP_ELGBLE_STTS
                        # 28 RSRCE_PRMRY_CAT_NM
                        # 29 RSRCE_PRMRY_PRPRTY_CL
                        # 30 RSRCE_SHPO_ID
                        # 31 RSRCE_SITE_DOC_ID
                        # 32 RSRCE_SITE_DOC_NAME
                        # 33 RSRCE_SPTL_CLCTN_MTHD
                        # 34 RSRCE_TMPRL_CLTRL_ASGNMNT


                        # Track comments throughout and add to COMMENTS field
                        comments = ''

                        # ADMIN_ST = row[15]
                        row[15] = 'CO'

                        # RSRCE_AGCY_ID = row[16]
                        row[16] = SITE_



                        # RSRCE_CAT = row[17]
                        if archaeology:
                            archaeology = archaeology.replace('HISTORIC>', '')
                            arch_items = [ai for ai in archaeology.split('>') if ai.strip()]
                            site_types = [st for st in site_type.split('>') if st.strip()]
                            rsrce_cats = set(arch_items + site_types)
                            rsrce_cat = ', '.join(sorted(rsrce_cats))
                            row[17] = format_data(rsrce_cat, target_schema['RSRCE_CAT'])
                        else:
                            row[17] = None
                        # RSRCE_PRMRY_CAT_NM = row[28]
                        #TODO:



                        # RSRCE_CLCTN_PRFRM_STTS = row[18]
                        collection_status = collections.get(SITE_)
                        row[18] = 'Yes' if collection_status else 'Unknown'

                        # RSRCE_CNDTN_ASSMNT = row[20]
                        cnd = tbl_updates['Condition'].get(SITE_)
                        if cnd:
                            cnd_val = cnd['Condition']
                            cnd_date = cnd['date']
                            try:
                                dom_cnd = map_domain_values(cnd_val, domain_mapping['CRM_DOM_RSRCE_CNDTN_ASSMNT'])
                                row[20] = format_data(dom_cnd, target_schema['RSRCE_CNDTN_ASSMNT'])
                            except Exception:
                                raise ConditionDomainError(cnd)
                        else:
                            row[20] = 'Unknown'

                        # RSRCE_DATA_SRCE = row[21]
                        row[21] = 'CO SHPO'
                       
                        # RSRCE_NM = row[24]
                        if name:
                            row[24] = format_data(name, target_schema['RSRCE_NM'])
                        else:
                            row[24] = None

                        # Get most recent eligibility, authority, and date
                        # RSRCE_NRHP_ELGBLE_STTS = row[27]
                        # RSRCE_NRHP_ELGBLE_AUTH_NM = row[25]
                        # RSRCE_DATE = row[22] - full date value as date
                        # RSRCE_LAST_RCRD_DT = row[23] - year only as string
                        # RSRCE_NRHP_ELGBLE_CRTRA = row[26]
                        assessment = tbl_updates['Assessment'].get(SITE_)
                        if assessment:
                            assess_val = assessment['Assessment']
                            assess_date = assessment['date']

                            try:
                                row[27] = map_domain_values(assess_val, domain_mapping['DOM_YES_NO_UNDTRMND'])
                            except Exception:
                                raise AssessmentDomainError(assess_val)

                            try:
                                row[22] = assess_date
                                try:
                                    row[23] =  assess_date.year
                                except:
                                    row[23] = None
                            except Exception:
                                raise AssessmentDateError(assess_date)

                            try:
                                row[25] = map_domain_values(assess_val, domain_mapping['CRM_DOM_RSRCE_NRHP_ELGBLE_AUTH_NM'])
                            except Exception:
                                raise AssessmentAuthorityDomainError(assess_val)

                            try:
                                row[26] = parse_assessment_criteria((NRC_A, NRC_B, NRC_C, NRC_D))
                            except Exception:
                                raise AssessmentCriteriaDomainError((NRC_A, NRC_B, NRC_C, NRC_D))
                        else:
                            row[22], row[23], row[25], row[26], row[27] = None, None, 'NA', None, 'Unknown'

                        # RSRCE_PRMRY_PRPRTY_CL = row[29]
                        row[29] = 'Site'

                        # RSRCE_SHPO_ID = row[30]
                        row[30] = SITE_

                        # RSRCE_SITE_DOC_ID = row[31]
                        if site_doc_id:
                            doc_ids = set([sid for sid in site_doc_id.split('>') if sid.strip()])
                            for doc_id in doc_ids:
                                site_survey_mapping.append((SITE_, doc_id))
                            id_string = ', '.join(sorted(doc_ids))
                            row[31] = format_data(id_string, target_schema['RSRCE_SITE_DOC_ID'])
                        else:
                            row[31] = None

                        # RSRCE_SITE_DOC_NAME = row[32]
                        if site_doc_name:
                            site_doc_name = ', '.join(['{}'.format(s) for s in site_doc_name.split('>')])
                            row[32] = format_data(site_doc_name, target_schema['RSRCE_SITE_DOC_NAME'])
                        else:
                            row[32] = None

                        # RSRCE_SPTL_CLCTN_MTHD = row[33]
                        row[33] = 'Unknown'

                        # RSRCE_TMPRL_CLTRL_ASGNMNT = row[34]
                        if resource_type:
                            try:
                                res_type = map_domain_values(resource_type, domain_mapping['CRM_DOM_RSRCE_TMPRL_CLTRL_ASGNMNT'])
                                row[34] = format_data(res_type, target_schema['RSRCE_TMPRL_CLTRL_ASGNMNT'])
                            except Exception:
                                raise TemporalAssessmentDomainError(resource_type)
                        else:
                            row[34] = 'Unknown'
                        
                        # RSRCE_CMT = row[19]
                        comments += '[FEATURES: {}] '.format(feature.replace('>', ', ')) if feature else ''
                        comments += '[ARTIFACTS: {}] '.format(artifact.replace('>', ', ')) if artifact else ''
                        row[19] = format_data(comments, target_schema['RSRCE_CMT'])
                        
                        ### Update row ###
                        cur.updateRow(row)
                                       
                    except TemporalAssessmentDomainError as e:
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] TemporalAssessmentDomainError: [OID: {}][SITE: {}][{}]\n{}'.format(OBJECTID, SITE_, e.val, traceback.format_exc()))
                    except ConditionDomainError as e:
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] ConditionDomainError: [OID: {}][SITE: {}][{}]\n{}'.format(OBJECTID, SITE_, e.val, traceback.format_exc()))
                    except AssessmentDomainError as e:
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] AssessmentDomainError: [OID: {}][SITE: {}][{}]\n{}'.format(OBJECTID, SITE_, e.val, traceback.format_exc()))
                    except AssessmentDateError as e:
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] AssessmentDateError: [OID: {}][SITE: {}][{}]\n{}'.format(OBJECTID, SITE_, e.val, traceback.format_exc()))
                    except AssessmentAuthorityDomainError as e:
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] AssessmentAuthorityDomainError: [OID: {}][SITE: {}][{}]\n{}'.format(OBJECTID, SITE_, e.val, traceback.format_exc()))

                    except Exception:  # Off the rails
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] Error: [OID: {}][SITE: {}]\n{}'.format(OBJECTID, SITE_, traceback.format_exc()))

                    finally:
                        report_ix += 1

            n_errors = len(error_rows)
            logger.log_all('Errors: {}'.format(n_errors))
            success_rate = (1-(float(n_errors)/n_rows))*100
            logger.log_all('Success rate: {:.3}%'.format(success_rate))
 
            # Clean up final feature class
            # Move and remove error_rows
            if error_rows:
                logger.log_all('Quarantining error rows..')
                where = buildWhereClauseFromList(working_lyr, 'OBJECTID', error_rows)
                logger.logfile(where)
                arcpy.SelectLayerByAttribute_management(working_lyr, where_clause=where)
                arcpy.CopyFeatures_management(working_lyr, failure)
                arcpy.DeleteRows_management(working_lyr)

                # Delete the derived fields from failure (so can be input again)
                # Delete unnecesarry fields
                for field in arcpy.ListFields(failure):
                    if field.name.startswith('TARGET_'):
                        try:
                            arcpy.DeleteField_management(failure, field.name)
                        except:
                            # Should minimally fail on required fields
                            logger.logfile("Delete field from [Failure FC] failed: {}".format(field.name)) 

            # Delete unnecesarry fields from final output
            logger.log_all('Cleaning up fields..')
            for field in arcpy.ListFields(working_lyr):
                if field.name not in NCRMS_fields:
                    try:
                        arcpy.DeleteField_management(working_lyr, field.name)
                    except:
                        try:
                            # try again..
                            arcpy.DeleteField_management(working_lyr, field.name)
                        except:
                            # Should minimally fail on required fields
                            logger.logfile("Delete field from [Success FC] failed: {}".format(field.name)) 

            # Update the site-survey many-to-many relationship table
            logger.log_all('Updating M-M table..')
            with arcpy.da.InsertCursor(site_survey_map_table, ['CRM_RSRCE_ID', 'CRM_INVSTGTN_ID']) as cur:
                for site_id, doc_id in site_survey_mapping:
                    cur.insertRow((site_id, doc_id))
            

###################################################################################################
##
## EXCEPTIONS
##
###################################################################################################

        except Exception as ex:
            logger.logfile(arcpy.GetMessages(2))
            arcpy.AddError(traceback.format_exc())
            


###################################################################################################
##
## CLEAN-UP
##
###################################################################################################

        finally:
            # Clear memory JIC
            deleteInMemory()


###################################################################################################
