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

Purpose: Crosswalk state SHPO data to BLM NCRMS format.


"""
# TODO: calculate BLM acres for sitesa and surveys
# TODO: Custom exceptions
# TODO: Test helper functions!
# TODO: finish up the documen..


###################################################################################################
##
## IMPORTS
##
###################################################################################################

from __future__ import division
from collections import Counter
from collections import defaultdict
from collections import OrderedDict
import csv
import datetime
import getpass
import os
import re
import sys
import traceback

import arcpy

sys.path.append(r'T:\CO\GIS\gistools\tools\Cultural')

from helpers.helper_functions import *
from helpers.log_handler import pyt_log


###################################################################################################
##
## GLOBALS
##
###################################################################################################

arcpy.env.addOutputsToMap = False
arcpy.env.overwriteOutput = True

user = getpass.getuser()
start_time = datetime.datetime.now()
start_date = datetime.date(1900,1,1)  # SHPO dates are int days since 1/1/1900
date_time_stamp = re.sub('[^0-9]', '', str(start_time)[2:16])

# TODO: switch to relative paths
gdb_template_xml = r'T:\CO\GIS\gistools\tools\Cultural\NCRMS_Crosswalk\data\database_schema.xml'
domain_map_csv = r'T:\CO\GIS\gistools\tools\Cultural\NCRMS_Crosswalk\data\domain_map.csv'


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
        self.tools = [Crosswalk_NCRMS_Data]


class Crosswalk_NCRMS_Data(object):
    def __init__(self):
        self.label = "Crosswalk_NCRMS_Data"
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

        ## May need a param path to land ownership to calculate BLM acres..

        return [src_gdb, out_gdb]


    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True


    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        # Defaults for easier testing - drop for prduction
        if not parameters[0].altered:
            parameters[0].value = r'T:\CO\GIS\gisuser\rgfo\mtroyer\z-Tests\NCRMS_Testing\blm_full_format_181019.gdb'
            parameters[1].value = r'T:\CO\GIS\gisuser\rgfo\mtroyer\z-Tests\NCRMS_Testing\test_output'
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
            log_path = os.path.join(output_path, "BLM_CO_NCRMS_Crosswalk_{}.log".format(date_time_stamp))
            logger = pyt_log(log_path)
            
            # Start logging
            logger.log_all("BLM CO NCRMS Data Crosswalk {}".format(datetime.datetime.now()))
            logger.logfile("{}\n".format('-'*120))
            logger.log_all("Running environment: Python - {}\n".format(sys.version))
            logger.log_all("User: {}\n".format(user))
            logger.log_all("Input gdb:\n\t{}\n".format(input_path))
            logger.log_all("Output dir:\n\t{}\n".format(output_path))

            # Create goedatabase
            gdb_name = 'BLM_CO_NCRMS_Crosswalk_{}'.format(date_time_stamp)
            arcpy.CreateFileGDB_management(output_path, gdb_name, "10.0")
            gdb_name = os.path.join(output_path, gdb_name) + '.gdb'
            # Schema from XML
            arcpy.ImportXMLWorkspaceDocument_management(gdb_name, gdb_template_xml, 'SCHEMA_ONLY')

            # Set workspace to fGDB
            arcpy.env.workspace = gdb_name

            ### Get the related table data ###
            assessment_table = os.path.join(input_path, 'Assessment')
            condition_table = os.path.join(input_path, 'Condition')
            organization_table = os.path.join(input_path, 'Organization')
            # Probably faster with SQL...
            # Get most recent value and date for each site in [Assessment, Condition, Organization]
            # {table: {site_id: {value: val, date: dt}}}
            tbl_updates = {
                'Assessment'   : {},
                'Condition'    : {},
                'Organization' : {},
                }
            for tbl, updates in tbl_updates.items():
                path = os.path.join(input_path, tbl)
                logger.console('Collecting updates from {} table..'.format(tbl))
                with arcpy.da.SearchCursor(path, ['Site_ID', tbl, 'Date']) as cur:
                    for site_id, val, dt in cur:
                        if not dt: continue  # Skip null
                        if not val: continue  # Skip null
                        if not val.strip(): continue  # skip empty strings - needed?
                        if site_id in updates:  # default to keys
                            if dt > updates[site_id]['date']:  # update if newer
                                updates[site_id] = {tbl: val, 'date': dt}
                        else:
                            updates[site_id] = {tbl: val, 'date': dt}
                logger.log_all('{} unique records: {}'.format(tbl, len(tbl_updates[tbl])))

            # Get the collection status from condition table
            logger.console('Getting collection status from Condition table')
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
            logger.log_all('Collections unique records: {}'.format(len(collections)))

            # Read in the domain mapping from CSV - necessary to keep up with source SHPO 'domain' changes
            domain_mapping = defaultdict(dict)

            logger.console('Reading domain mapping table..')
            with open(domain_map_csv, 'r') as f:  # rb py3 (once switched to pro)
                csv_reader = csv.reader(f)
                # Skip the header row
                csv_reader.next()
                for domain, src_val, dmn_val in csv_reader:
                    domain_mapping[domain][src_val] = dmn_val
            for domain in domain_mapping.keys():
                 logger.log_all('Found domain [{}]'.format(domain))

            #######################################################################################
            ##
            ## RESOURCES
            ##
            #######################################################################################

            logger.log_all('\n'+ 'Processing Sites'.center(80, '-') + '\n')

            # Remove the blank [CRM_Resources] - replace with input data copy and mod in place
            arcpy.Delete_management(os.path.join(gdb_name, 'CRM_Resources'))

            # Get the paths to output success and failure FCs, duplicate table, and M-to-M table
            success = os.path.join(gdb_name, 'CRM_Resources')
            failure = os.path.join(gdb_name, 'CRM_Resources_fails')
            duplicates = os.path.join(gdb_name, 'CRM_Resources_duplicates')
            site_survey_map_table = os.path.join(gdb_name, 'CRM_RSRCE_INVSTGTN_TBL')

            # Copy input fc to database and get as a feature layer
            # Will be success layer, failures will be copied to <failure> and removed
            input_fc = os.path.join(input_path, 'BLM_CO_Sites')
            arcpy.CopyFeatures_management(input_fc, success)
            working_lyr = arcpy.MakeFeatureLayer_management(success, r'in_memory\lyr')

            # Check for duplicates
            id_field = 'SITE_'
            arcpy.FindIdentical_management(working_lyr, duplicates, id_field, output_record_option='ONLY_DUPLICATES')
            if int(arcpy.GetCount_management(duplicates).getOutput(0)):
                logger.log_all('WARNING: Duplicate Site IDs found - see duplicate table for details\n')

            n_rows = int(arcpy.GetCount_management(working_lyr).getOutput(0))
            logger.log_all('Resources: {} total rows..\n'.format(n_rows))

            ### Add the target fields ###
            target_schema = OrderedDict()  # remembers insert order for iteration
            for key, val in [
                ('RSRCE_AGCY_ID', {'ALIAS': 'Agency Resource Identifier','TYPE': 'String','LENGTH': 50,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_SHPO_ID', {'ALIAS': 'SHPO Database Resource Identifier','TYPE': 'String','LENGTH': 50,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_NM', {'ALIAS': 'Resource Name','TYPE': 'String','LENGTH': 255,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_TMPRL_CLTRL_ASGNMNT', {'ALIAS': 'Resource Temporal Cultural Assignment','TYPE': 'String','LENGTH': 50,'DOMAIN': 'CRM_DOM_RSRCE_TMPRL_CLTRL_ASGNMNT','DEFAULT': 'Unknown',}),
                ('RSRCE_PRMRY_PRPRTY_CL', {'ALIAS': 'Resource Primary Property Class','TYPE': 'String','LENGTH': 30,'DOMAIN': 'CRM_DOM_RSRCE_PRMRY_PRPRTY_CL','DEFAULT': 'Site',}),
                ('RSRCE_PRMRY_CAT_NM', {'ALIAS': 'Resource Primary Category Name','TYPE': 'String','LENGTH': 30,'DOMAIN': 'CRM_DOM_RSRCE_PRMRY_CAT','DEFAULT': 'Unknown',}),
                ('RSRCE_CAT', {'ALIAS': 'Resource Category','TYPE': 'String','LENGTH': 2000,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_NRHP_ELGBLE_STTS', {'ALIAS': 'Resource NRHP Eligibility Status','TYPE': 'String','LENGTH': 12,'DOMAIN': 'DOM_YES_NO_UNDTRMND','DEFAULT': 'Undetermined',}),
                ('RSRCE_NRHP_ELGBLE_CRTRA', {'ALIAS': 'NRHP Eligibility Criteria','TYPE': 'String','LENGTH': 35,'DOMAIN': 'CRM_DOM_RSRCE_NRHP_ELGBLE_CRTRA','DEFAULT': 'Not Specified',}),
                ('RSRCE_NRHP_ELGBLE_AUTH_NM', {'ALIAS': 'Resource NRHP Eligibility Authority Name','TYPE': 'String','LENGTH': 35,'DOMAIN': 'CRM_DOM_ RSRCE_NRHP_ELGBLE_AUTH_NM','DEFAULT': 'NA',}),
                ('RSRCE_CNDTN_ASSMNT', {'ALIAS': 'Resource Condition Assessment','TYPE': 'String','LENGTH': 50,'DOMAIN': 'CRM_DOM_RSRCE_CNDTN_ASSMNT','DEFAULT': 'Unknown',}),
                ('RSRCE_LAST_RCRD_DT', {'ALIAS': 'Resource Last Recorded Date','TYPE': 'String','LENGTH': 20,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_DATE', {'ALIAS': 'Resource Last Recorded Date in Date Format','TYPE': 'Date','LENGTH': 20,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_CLCTN_PRFRM_STTS', {'ALIAS': 'Resource Collection Performed Status','TYPE': 'String','LENGTH': 20,'DOMAIN': 'CRM_DOM_RSRCE_CLCTN_PRFRM_STTS','DEFAULT': 'Unknown',}),
                ('RSRCE_DATA_SRCE', {'ALIAS': 'Resource Data Source','TYPE': 'String','LENGTH': 25,'DOMAIN': 'CRM_DOM_DATA_SRCE','DEFAULT': 'Unknown',}),
                ('RSRCE_SPTL_CLCTN_MTHD', {'ALIAS': 'Resource Spatial Collection Method','TYPE': 'String','LENGTH': 30,'DOMAIN': 'CRM_DOM_SPTL_CLCTN_MTHD','DEFAULT': 'Unknown',}),
                ('RSRCE_CMT', {'ALIAS': 'Resource Comments','TYPE': 'String','LENGTH': 2000,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_SITE_DOC_ID', {'ALIAS': 'Report ID','TYPE': 'String','LENGTH': 255,'DOMAIN': None,'DEFAULT': None,}),
                ('RSRCE_SITE_DOC_NAME', {'ALIAS': 'Report Name','TYPE': 'String','LENGTH': 2000,'DOMAIN': None,'DEFAULT': None,}),
                ('ADMIN_ST', {'ALIAS': 'Administrative State Code','TYPE': 'String','LENGTH': 2,'DOMAIN': 'DOM_ADMIN_ST','DEFAULT': None,}),
                ('GIS_ACRES', {'ALIAS': 'GIS Acres','TYPE': 'Double','LENGTH': 20, 'DOMAIN': None,'DEFAULT': None,}),
                ('BLM_ACRES', {'ALIAS': 'BLM Acres','TYPE': 'Double','LENGTH': 20, 'DOMAIN': None,'DEFAULT': None,}),
                ]: 
                target_schema[key] = val

            logger.console('Adding NCRMS Resources fields..')
            for field_name, field_params in target_schema.items():
                arcpy.AddField_management(
                    in_table=working_lyr,
                    field_name=field_name,
                    field_type=field_params['TYPE'],
                    field_length=field_params['LENGTH'],
                    field_alias=field_params['ALIAS'],
                    field_domain=field_params['DOMAIN'],
                    )
 
            # NCRMS_fields = sorted(target_schema.keys())
            NCRMS_fields = target_schema.keys()
            SHPO_fields = [
                'SITE_', 'site_doc_id', 'site_doc_name', 'name', 'resource_type', 'culture',  'archaeology', 'site_type',
                'NRC_A', 'NRC_B', 'NRC_C', 'NRC_D', 'feature', 'artifact',
                ]
            logger.logfile('SHPO fields:\n{}'.format(SHPO_fields))
            logger.logfile('NCRMS fields:\n{}'.format(NCRMS_fields))

            error_rows = []
            logger.console('Iterating rows..')
            update_fields = ['OBJECTID'] + SHPO_fields + NCRMS_fields
            report_ix = 1

            site_survey_mapping = []

            #######################################################################################
            ##
            ## RESOURCES MAIN PROCESSING LOOP
            ##
            #######################################################################################

            # Use and update cursor to transform the src data to the NCRMS fields
            # There has to be a better way.. indexing rows like this sucks.
            # Class based approach to processing rows - class SiteRecord() ?
            # A Record base class would make this easier to generalize
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
                        #TODO: REORDER
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

                        # NCRMS field indexes
                        # 15 'RSRCE_AGCY_ID'             
                        # 16 'RSRCE_SHPO_ID'             
                        # 17 'RSRCE_NM'                  
                        # 18 'RSRCE_TMPRL_CLTRL_ASGNMNT'
                        # 19 'RSRCE_PRMRY_PRPRTY_CL'    
                        # 20 'RSRCE_PRMRY_CAT_NM'       
                        # 21 'RSRCE_CAT'                
                        # 22 'RSRCE_NRHP_ELGBLE_STTS'   
                        # 23 'RSRCE_NRHP_ELGBLE_CRTRA'  
                        # 24 'RSRCE_NRHP_ELGBLE_AUTH_NM'
                        # 25 'RSRCE_CNDTN_ASSMNT'       
                        # 26 'RSRCE_LAST_RCRD_DT'       
                        # 27 'RSRCE_DATE'               
                        # 28 'RSRCE_CLCTN_PRFRM_STTS'   
                        # 29 'RSRCE_DATA_SRCE'          
                        # 30 'RSRCE_SPTL_CLCTN_MTHD'    
                        # 31 'RSRCE_CMT'                
                        # 32 'RSRCE_SITE_DOC_ID'        
                        # 33 'RSRCE_SITE_DOC_NAME'      
                        # 34 'ADMIN_ST'
                
                        # Track comments throughout and add to COMMENTS field
                        comments = ''

                        # RSRCE_AGCY_ID = row[15]
                        row[15] = SITE_

                        # RSRCE_SHPO_ID = row[16]
                        row[16] = SITE_

                        # RSRCE_NM = row[17]
                        if name:
                            row[17] = format_data(name, target_schema['RSRCE_NM'])
                        else:
                            row[17] = None

                        # RSRCE_TMPRL_CLTRL_ASGNMNT = row[18]
                        if resource_type:
                            try:
                                res_type = map_domain_values(resource_type, domain_mapping['CRM_DOM_RSRCE_TMPRL_CLTRL_ASGNMNT'])
                                row[18] = format_data(res_type, target_schema['RSRCE_TMPRL_CLTRL_ASGNMNT'])
                            except Exception as e:
                                raise ValueError('Resource Type Error', resource_type, e)
                        else:
                            row[18] = 'Unknown'

                        # RSRCE_PRMRY_PRPRTY_CL = row[19]
                        row[19] = 'Site'

                        # RSRCE_PRMRY_CAT_NM = row[20]
                        # RSRCE_CAT = row[21]
                        if archaeology:
                            archaeology = archaeology.replace('HISTORIC>', '')
                            arch_items = [ai for ai in archaeology.split('>') if ai.strip()]
                        else: arch_items = []

                        if site_type:
                            site_types = [st for st in site_type.split('>') if st.strip()]
                        else: site_types = []

                        rsrce_cats = arch_items + site_types
                        if rsrce_cats:
                            rsrce_cat = ', '.join(sorted(rsrce_cats))
                            row[21] = format_data(rsrce_cat, target_schema['RSRCE_CAT'])
                            # Remap each value to its corresponding domain value
                            dom_cat = [map_domain_values(v, domain_mapping['CRM_DOM_RSRCE_PRMRY_CAT'])
                                       for v in rsrce_cats]
                            # Pick the most common
                            res_cnt = Counter(dom_cat)
                            #TODO: what about ties?! Takes first alphabetically - aaaaaahahhaha
                            max_res_cat = res_cnt.most_common(1)[0][0]
                            row[20] = format_data(max_res_cat, target_schema['RSRCE_PRMRY_CAT_NM'])
                        else:
                            row[21] = None
                            row[20] = None

                        # RSRCE_CNDTN_ASSMNT = row[25]
                        cnd = tbl_updates['Condition'].get(SITE_)
                        if cnd:
                            cnd_val = cnd['Condition']
                            cnd_date = cnd['date']
                            try:
                                dom_cnd = map_domain_values(cnd_val, domain_mapping['CRM_DOM_RSRCE_CNDTN_ASSMNT'])
                                row[25] = format_data(dom_cnd, target_schema['RSRCE_CNDTN_ASSMNT'])
                            except Exception as e:
                                raise ValueError('Condition Error', cnd, e)
                        else:
                            row[25] = 'Unknown'                    

                        # Get most recent eligibility, authority, and date
                        # RSRCE_NRHP_ELGBLE_STTS = row[22]
                        # RSRCE_NRHP_ELGBLE_CRTRA = row[23]
                        # RSRCE_NRHP_ELGBLE_AUTH_NM = row[24]
                        # RSRCE_LAST_RCRD_DT = row[26] - year only as string
                        # RSRCE_DATE = row[27] - full date value as date
                        assessment = tbl_updates['Assessment'].get(SITE_)
                        if assessment:
                            assess_val = assessment['Assessment']
                            assess_date = assessment['date']

                            try:
                                row[22] = map_domain_values(assess_val, domain_mapping['DOM_YES_NO_UNDTRMND'])
                            except Exception as e:
                                raise ValueError('Assessment Error', assess_val, e)

                            try:
                                row[27] = assess_date
                                try:
                                    row[26] = assess_date.year
                                except:
                                    row[26] = None
                            except Exception as e:
                                raise ValueError('Assessment Date Error', assess_date, e)

                            try:
                                row[24] = map_domain_values(assess_val, domain_mapping['CRM_DOM_RSRCE_NRHP_ELGBLE_AUTH_NM'])
                            except Exception as e:
                                raise ValueError('Assessment Domain Error', assess_val, e)

                            try:
                                row[23] = parse_assessment_criteria((NRC_A, NRC_B, NRC_C, NRC_D))
                            except Exception as e:
                                raise ValueError('Parse Assessment Error', (NRC_A, NRC_B, NRC_C, NRC_D), e)
                        else:
                            row[27], row[26], row[24], row[23], row[22] = None, None, 'NA', None, 'Unknown'

                        # RSRCE_CLCTN_PRFRM_STTS = row[28]
                        collection_status = collections.get(SITE_)
                        row[28] = 'Yes' if collection_status else 'Unknown'

                        # RSRCE_DATA_SRCE = row[29]
                        row[29] = 'CO SHPO'

                        # RSRCE_SPTL_CLCTN_MTHD = row[30]
                        row[30] = 'Unknown'
                        
                        # RSRCE_CMT = row[31]
                        comments += '[FEATURES: {}] '.format(feature.replace('>', ', ')) if feature else ''
                        comments += '[ARTIFACTS: {}] '.format(artifact.replace('>', ', ')) if artifact else ''
                        row[31] = format_data(comments, target_schema['RSRCE_CMT'])

                        # RSRCE_SITE_DOC_ID = row[32]
                        if site_doc_id:
                            doc_ids = set([sid for sid in site_doc_id.split('>') if sid.strip()])
                            for doc_id in doc_ids:
                                site_survey_mapping.append((SITE_, doc_id))
                            id_string = ', '.join(sorted(doc_ids))
                            row[32] = format_data(id_string, target_schema['RSRCE_SITE_DOC_ID'])
                        else:
                            row[32] = None

                        # RSRCE_SITE_DOC_NAME = row[33]
                        if site_doc_name:
                            site_doc_name = ', '.join(['[{}]'.format(s) for s in site_doc_name.split('>')])
                            row[33] = format_data(site_doc_name, target_schema['RSRCE_SITE_DOC_NAME'])
                        else:
                            row[33] = None
                        
                        # ADMIN_ST = row[34]
                        row[34] = 'CO'

                        ### Update row ###
                        cur.updateRow(row)
                                       
                    except ValueError as e:
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] Error: [OID: {}][SITE: {}]\n{}\n{}'.format(OBJECTID, SITE_, traceback.format_exc(), e))  

                    except:  # We're Off the rails
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
                logger.console('Quarantining error rows..')
                where = buildWhereClauseFromList(working_lyr, 'OBJECTID', error_rows)
                arcpy.SelectLayerByAttribute_management(working_lyr, where_clause=where)
                arcpy.CopyFeatures_management(working_lyr, failure)
                arcpy.DeleteRows_management(working_lyr)

                # Delete the derived fields from failure (so can be input again)
                # Delete unnecesarry fields
                for field in arcpy.ListFields(failure):
                    if field.name in NCRMS_fields:
                        try:
                            arcpy.DeleteField_management(failure, field.name)
                        except:
                            # Should minimally fail on required fields
                            logger.logfile("Delete field from [Failure FC] failed: {}".format(field.name)) 

            # Delete unnecesarry fields from final output
            logger.console('Cleaning up fields..')
            for field in arcpy.ListFields(working_lyr):
                if field.name not in NCRMS_fields:
                    try:
                        arcpy.DeleteField_management(working_lyr, field.name)
                    except:
                        try:
                            # try again damn it.. sometimes this sucks
                            arcpy.DeleteField_management(working_lyr, field.name)
                        except:
                            # Should minimally fail on required fields
                            logger.logfile("Delete field from [Success FC] failed: {}".format(field.name)) 

            # Update acres
            logger.console('Updating GIS_ACRES..')
            arcpy.CalculateField_management(working_lyr, "GIS_ACRES", "!shape.area@ACRES!", "PYTHON_9.3")

            # Update the site-survey many-to-many relationship table
            logger.console('Updating many-to-many relate table..')
            with arcpy.da.InsertCursor(site_survey_map_table, ['CRM_RSRCE_ID', 'CRM_INVSTGTN_ID']) as cur:
                for site_id, doc_id in site_survey_mapping:
                    cur.insertRow((site_id, doc_id))
            
            
            #######################################################################################
            ##
            ## INVESTIGATIONS
            ##
            #######################################################################################

            logger.log_all('\n'+ 'Processing Surveys'.center(80, '-') + '\n')

            # Remove the old [CRM_Investigations] - replace with input data copy - mod in place
            arcpy.Delete_management(os.path.join(gdb_name, 'CRM_Investigations'))

            # Get the paths to output success and failure FCs, duplicate table, and M-to-M table
            success = os.path.join(gdb_name, 'CRM_Investigations')
            failure = os.path.join(gdb_name, 'CRM_Investigations_fails')
            duplicates = os.path.join(gdb_name, 'CRM_Investigations_duplicates')
            site_survey_map_table = os.path.join(gdb_name, 'CRM_RSRCE_INVSTGTN_TBL')

            # Copy input fc to database and get as a feature layer
            # Will be success layer, failures will be copied to <faliure> and removed
            input_fc = os.path.join(input_path, 'BLM_CO_Surveys')
            arcpy.CopyFeatures_management(input_fc, success)
            working_lyr = arcpy.MakeFeatureLayer_management(success, r'in_memory\lyr')

            # Check for duplicates
            id_field = 'DOC_'
            arcpy.FindIdentical_management(working_lyr, duplicates, id_field, output_record_option='ONLY_DUPLICATES')
            if int(arcpy.GetCount_management(duplicates).getOutput(0)):
                logger.log_all('WARNING: Duplicate Survey IDs found - see duplicate table for details\n')

            n_rows = int(arcpy.GetCount_management(working_lyr).getOutput(0))
            logger.log_all('Investigations: {} total rows..\n'.format(n_rows))

            ### Add the target fields ###
            target_schema = OrderedDict()  # remembers insert order for iteration
            for key, val in [
                ('INVSTGTN_AGCY_ID', {'ALIAS': 'Agency Investigation Unique Identifier','TYPE': 'String','LENGTH': 50,'DOMAIN': None, 'DEFAULT': None,}),
                ('INVSTGTN_SHPO_ID', {'ALIAS': 'State Investigation Unique Identifier','TYPE': 'String','LENGTH': 50,'DOMAIN': None, 'DEFAULT': None,}),
                ('INVSTGTN_CMPLT_MONTH_YR', {'ALIAS': 'Investigation Completed Month and Year','TYPE': 'String','LENGTH': 20, 'DOMAIN': None,'DEFAULT': None,}),
                ('INVSTGTN_DATE', {'ALIAS': 'Investigation Completed Date','TYPE': 'Date','LENGTH': 20, 'DOMAIN': None,'DEFAULT': None}),
                ('INVSTGTN_LEAD_BLM_ADMIN_ST', {'ALIAS': 'Investigation Lead BLM Administrative State','TYPE': 'String','LENGTH': 2,'DOMAIN': 'DOM_ADMIN_ST','DEFAULT': 'CO',}),
                ('INVSTGTN_TITLE', {'ALIAS': 'Investigation Title','TYPE': 'String','LENGTH': 255, 'DOMAIN': None, 'DEFAULT': None,}),
                ('INVSTGTN_AUTH', {'ALIAS': 'Investigation Authority', 'TYPE': 'String','LENGTH': 50,'DOMAIN': 'CRM_DOM_INVSTGTN_AUTH','DEFAULT': 'Unknown',}),
                ('INVSTGTN_CL', {'ALIAS': 'Investigation Class','TYPE': 'String','LENGTH': 30, 'DOMAIN': 'CRM_DOM_INVSTGTN_CL','DEFAULT': 'Unknown',}),
                ('INVSTGTN_PRFRM_PARTY_NM', {'ALIAS': 'Investigation Performed By Party Name','TYPE': 'String','LENGTH': 100, 'DOMAIN': None,'DEFAULT': None,}),
                ('INVSTGTN_NEPA_ID', {'ALIAS': 'Investigation NEPA Identifier','TYPE': 'String','LENGTH': 50,'DOMAIN': None, 'DEFAULT': None,}),
                ('INVSTGTN_DATA_SRCE', {'ALIAS': 'Investigation Data Source','TYPE': 'String','LENGTH': 25,'DOMAIN': 'CRM_DOM_DATA_SRCE', 'DEFAULT': 'Unknown',}),
                ('INVSTGTN_CMT', {'ALIAS': 'Investigation Comments','TYPE': 'String','LENGTH': 2000, 'DOMAIN': None,'DEFAULT': None, }),
                ('ADMIN_ST', {'ALIAS': 'Administartive State Code','TYPE': 'String','LENGTH': 2, 'DOMAIN': 'DOM_ADMIN_ST','DEFAULT': None,}),
                ('GIS_ACRES', {'ALIAS': 'GIS Acres','TYPE': 'Double','LENGTH': 20, 'DOMAIN': None,'DEFAULT': None,}),
                ('BLM_ACRES', {'ALIAS': 'BLM Acres','TYPE': 'Double','LENGTH': 20, 'DOMAIN': None,'DEFAULT': None,}),
                ]: 
                target_schema[key] = val

            logger.console('Adding NCRMS Investigation fields..')
            for field_name, field_params in target_schema.items():
                arcpy.AddField_management(
                    in_table=working_lyr,
                    field_name=field_name,
                    field_type=field_params['TYPE'],
                    field_length=field_params['LENGTH'],
                    field_alias=field_params['ALIAS'],
                    field_domain=field_params['DOMAIN'],
                    )

            NCRMS_fields = target_schema.keys()
            SHPO_fields = [
                'DOC_', 'LAST_AGENC', 'LAST_SOURC', 'LAST_DATE_', 'name', 'lead_agenc', 'institutio', 'method', 'completion', 'activity',
                ]

            logger.logfile('SHPO investigation fields:\n{}'.format(SHPO_fields))
            logger.logfile('NCRMS investigation fields:\n{}'.format(NCRMS_fields))

            error_rows = []
            logger.console('Iterating rows..')
            update_fields = ['OBJECTID'] + SHPO_fields + NCRMS_fields
            report_ix = 1

            site_survey_mapping = []

            #######################################################################################
            ##
            ## INVESTIGATIONS MAIN PROCESSING LOOP
            ##
            #######################################################################################

            with arcpy.da.UpdateCursor(working_lyr, update_fields) as cur:
                for row in cur:
                    if report_ix % 5000 == 0:
                        logger.console('Processed {} of {} rows..'.format(report_ix, n_rows))

                    try:
                        OBJECTID   = row[0]
                        DOC_       = row[1]
                        LAST_AGENC = row[2]
                        LAST_SOURC = row[3]
                        LAST_DATE_ = row[4]
                        name       = row[5]
                        lead_agenc = row[6]
                        institutio = row[7]
                        method     = row[8]
                        completion = row[9]
                        activity   = row[10]

                        # Clean the strings - no weird surprises!
                        DOC_       = clean_string(DOC_)
                        LAST_AGENC = clean_string(LAST_AGENC)
                        LAST_SOURC = clean_string(LAST_SOURC)
                        LAST_DATE_ = int(LAST_DATE_)
                        name       = clean_string(name)
                        lead_agenc = clean_string(lead_agenc)
                        institutio = clean_string(institutio)
                        method     = clean_string(method)
                        completion = clean_string(completion)
                        activity   = clean_string(activity)

                        # 11 'INVSTGTN_AGCY_ID'
                        # 12 'INVSTGTN_SHPO_ID'
                        # 13 'INVSTGTN_CMPLT_MONTH_YR'
                        # 14 'INVSTGTN_DATE'
                        # 15 'INVSTGTN_LEAD_BLM_ADMIN_ST'  
                        # 16 'INVSTGTN_TITLE'
                        # 17 'INVSTGTN_AUTH'
                        # 18 'INVSTGTN_CL'
                        # 19 'INVSTGTN_PRFRM_PARTY_NM'
                        # 20 'INVSTGTN_NEPA_ID'
                        # 21 'INVSTGTN_DATA_SRCE'
                        # 22 'INVSTGTN_CMT'
                        # 23 'ADMIN_ST'
                        # 24 'GIS_ACRES'
                        # 25 'BLM_ACRES'

                        # Track comments throughout and add to COMMENTS field
                        comments = ''

                        # INVSTGTN_AGCY_ID = row[11] - Agency or mine from name
                        row[11] = format_data(LAST_AGENC, target_schema['INVSTGTN_AGCY_ID'])

                        # INVSTGTN_SHPO_ID = row[12] - DOC_
                        row[12] = format_data(DOC_, target_schema['INVSTGTN_SHPO_ID'])

                        # INVSTGTN_DATE = row[14] - use LAST_DATE_ and fillna with completion date
                        # INVSTGTN_CMPLT_MONTH_YR = row[13] from INVSTGTN_DATE
                        dates = 'last_date: [{}] - completion: [{}]'.format(LAST_DATE_, completion)
                        if LAST_DATE_ > 30000:  # int days since 1/1/1900
                            try:
                                row_date = start_date + datetime.timedelta(LAST_DATE_)  
                                row[14] = row_date
                                row[15] = '{}-{}'.format(row_date.year, row_date.month)
                            except Exception as e:
                                raise ValueError('LAST_DATE_ Error', LAST_DATE_, e)
                        elif completion:
                            try:
                                row_date = tryParseDate(completion)
                                row[14] = row_date
                                row[15] = '{}-{}'.format(row_date.year, row_date.month)
                            except Exception as e:
                                raise ValueError('Completion Date Error', completion, e)

                        else:
                            row[14] = None
                            row[15] = None
                        
                        # INVSTGTN_LEAD_BLM_ADMIN_ST = row[15] - Default CO
                        row[15] = 'CO'

                        # INVSTGTN_TITLE = row[16] - name
                        row[16] = format_data(name, target_schema['INVSTGTN_TITLE'])

                        # INVSTGTN_AUTH = row[17] - activity
                        if activity:
                            try:
                                activity = map_domain_values(activity, domain_mapping['CRM_DOM_INVSTGTN_AUTH'])
                                row[17] = format_data(activity, target_schema['INVSTGTN_AUTH'])
                            except Exception as e:
                                raise ValueError('Activity Error', activity, e)
                        else:
                            row[17] = 'Unknown'

                        # INVSTGTN_CL = row[18] - method
                        if method:
                            try:
                                method = map_domain_values(method, domain_mapping['CRM_DOM_INVSTGTN_CL'])
                                row[18] = format_data(method, target_schema['INVSTGTN_CL'])
                            except Exception as e:
                                raise ValueError('Method Error', method, e)
                        else:
                            row[18] = 'Unknown'

                        # INVSTGTN_PRFRM_PARTY_NM = row[19] - institution
                        row[19] = format_data(institutio, target_schema['INVSTGTN_PRFRM_PARTY_NM'])

                        # INVSTGTN_NEPA_ID = row[20] -  mine from name. Maybe pull related tables from BLM src?
                        # This sucks..
                        if name:
                            nepa_ids = extract_nepa_ids(name)
                            if nepa_ids:
                                nepa_str = ', '.join(nepa_ids)
                                row[20] = format_data(nepa_str, target_schema['INVSTGTN_NEPA_ID'])
                            else:
                                row[20] = 'Unknown'
                        else:
                            row[20] = 'Unknown'        

                        # INVSTGTN_DATA_SRCE = row[21] - CO SHPO only relevant value in domain..? 
                        # Could parse more meaningful values from source (blank = SHPO, parse BLM vs External)
                        # i.e.
                        # if source:
                        #     if 'BLM' in source: row[21] = 'CO BLM'
                        #     else: row[21] = 'External'
                        # else: row[21] = 'CO SHPO'

                        row[21] = 'CO SHPO'

                        # INVSTGTN_CMT = row[22]
                        row[22] = format_data(comments, target_schema['INVSTGTN_CMT'])

                        # ADMIN_ST = row[23] - default CO
                        row[23] = 'CO'

                        ### Update row ###
                        cur.updateRow(row)
   
                    except ValueError:
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] Error: [OID: {}][DOC: {}]\n{}'.format(OBJECTID, DOC_, traceback.format_exc()))  

                    except:  # We're Off the rails
                        error_rows.append(OBJECTID)
                        logger.logfile('[-] Error: [OID: {}][DOC: {}]\n{}'.format(OBJECTID, DOC_, traceback.format_exc()))                    

                    finally:
                        report_ix += 1

            n_errors = len(error_rows)
            logger.log_all('Errors: {}'.format(n_errors))
            success_rate = (1-(float(n_errors)/n_rows))*100
            logger.log_all('Success rate: {:.3}%'.format(success_rate))
 
            # Clean up final feature class
            # Move and remove error_rows
            if error_rows:
                logger.console('Quarantining error rows..')
                where = buildWhereClauseFromList(working_lyr, 'OBJECTID', error_rows)
                arcpy.SelectLayerByAttribute_management(working_lyr, where_clause=where)
                arcpy.CopyFeatures_management(working_lyr, failure)
                arcpy.DeleteRows_management(working_lyr)

                # Delete the derived fields from failure (so can be input again)
                # Delete unnecesarry fields
                for field in arcpy.ListFields(failure):
                    if field.name in NCRMS_fields:
                        try:
                            arcpy.DeleteField_management(failure, field.name)
                        except:
                            # Should minimally fail on required fields
                            logger.logfile("Delete field from [Failure FC] failed: {}".format(field.name)) 

            # Delete unnecesarry fields from final output
            logger.console('Cleaning up fields..')
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

            # Update acres
            logger.console('Updating GIS_ACRES..')
            arcpy.CalculateField_management(working_lyr, "GIS_ACRES", "!shape.area@ACRES!", "PYTHON_9.3")


            #TODO: Update GIS acres for sites and surveys
            #TODO: Isolate BLM lands, dissolve, Intersect site/survey, dissolve, join?
            #TODO: Sites intersect will be super slow..

###################################################################################################
##
## EXCEPTIONS
##
###################################################################################################

        except Exception as e:
            try:
                logger.logfile(arcpy.GetMessages(2))
            except:
                arcpy.AddMessage(arcpy.GetMessages(2))
            arcpy.AddError(traceback.format_exc())
            

###################################################################################################
##
## CLEAN-UP
##
###################################################################################################

        finally:
            # Clear memory JIC
            arcpy.AddMessage('\n'+ 'Complete'.center(80, '-') + '\n')
            deleteInMemory()


###################################################################################################
