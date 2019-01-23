from tornado.iostream import StreamClosedError
from tornado.process import Subprocess
from tornado.log import LogFormatter
from tornado.web import HTTPError
from tornado.ioloop import IOLoop
from tornado import concurrent
from tornado import gen
from psycopg2 import sql
from mapbox import Uploader
from mapbox import errors
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.options
import logging
import json
import psycopg2
import pandas
import os
import re
import traceback
import glob
import time
import datetime
import select
import subprocess
import sys
import commands
import zipfile
import shutil
import uuid
import signal

####################################################################################################################################################################################################################################################################
## constant declarations
####################################################################################################################################################################################################################################################################
##SECURITY SETTINGS
DISABLE_SECURITY = False                                                        # Set to True to turn off all security, i.e. authentication and authorisation
COOKIE_RANDOM_VALUE = "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__"           # This must be set to a random value as it is used to encrypt and sign cookies - if it is not changed then malicious hackers can use this default value to produce their own signed cookies compromising security
PERMITTED_DOMAINS = ["https://marxan-client-blishten.c9users.io:8081/"]         # Add domains that you want to allow to access your services and data - this only applies to cross-domain requests and is not relevant if the client and server software are on the same machine
PERMITTED_METHODS = ["createUser","validateUser"]                               # REST services that have no authentication/authorisation 
ROLE_UNAUTHORISED_METHODS = {                                                   # Add REST services that you want to lock down to specific roles - a class added to an array will make that method unavailable for that role
    "ReadOnly": ["createProject","createImportProject","upgradeProject","deleteProject","cloneProject","createProjectGroup","deleteProjects","renameProject","updateProjectParameters","getCountries","getPlanningUnitGrids","createPlanningUnitGrid","deletePlanningUnitGrid","uploadTilesetToMapBox","uploadShapefile","uploadFile","importPlanningUnitGrid","createFeaturePreprocessingFileFromImport","createUser","getUsers","updateUserParameters","getFeature","importFeature","getPlanningUnitsData","updatePUFile","getSpeciesData","getAllSpeciesData","getSpeciesPreProcessingData","updateSpecFile","getProtectedAreaIntersectionsData","getMarxanLog","getBestSolution","getOutputSummary","getSummedSolution","getMissingValues","preprocessFeature","preprocessPlanningUnits","preprocessProtectedAreas","runMarxan","stopMarxan","testRoleAuthorisation"],
    "User": ['testRoleAuthorisation','deleteProject'],
    "Admin": []
}
NOT_AUTHENTICATED_ERROR = "Request could not be authenticated. No secure cookie found."
NO_REFERER_ERROR = "The request header does not specify a referer and this is required for CORS access."
CONNECTION_STRING = "dbname='biopama' host='localhost' user='jrc' password='thargal88'"
MARXAN_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/"
MARXAN_EXECUTABLE = MARXAN_FOLDER + "MarOpt_v243_Linux64"
MARXAN_WEB_RESOURCES_FOLDER = MARXAN_FOLDER + "_marxan_web_resources/"
START_PROJECT_FOLDER = MARXAN_WEB_RESOURCES_FOLDER + "Start project/"
EMPTY_PROJECT_TEMPLATE_FOLDER = MARXAN_WEB_RESOURCES_FOLDER + "empty_project/"
CLUMP_FOLDER = MARXAN_FOLDER + "_clumping/"
OGR2OGR_EXECUTABLE = "/home/ubuntu/miniconda2/bin/ogr2ogr"
MAPBOX_USER = "blishten"
MAPBOX_ACCESS_TOKEN = "sk.eyJ1IjoiYmxpc2h0ZW4iLCJhIjoiY2piNm1tOGwxMG9lajMzcXBlZDR4aWVjdiJ9.Z1Jq4UAgGpXukvnUReLO1g"
USER_DATA_FILENAME = "user.dat"
PROJECT_DATA_FILENAME = "input.dat"
OUTPUT_LOG_FILENAME = "output_log.dat"
PLANNING_UNITS_FILENAME ="pu.dat"
PUVSPR_FILENAME = "puvspr.dat"
SPEC_FILENAME ="spec.dat"
BOUNDARY_LENGTH_FILENAME = "bounds.dat"
BEST_SOLUTION_FILENAME = "output_mvbest.txt"
OUTPUT_SUMMARY_FILENAME = "output_sum.txt"
SUMMED_SOLUTION_FILENAME = "output_ssoln.txt"
FEATURE_PREPROCESSING_FILENAME = "feature_preprocessing.dat"
PROTECTED_AREA_INTERSECTIONS_FILENAME = "protected_area_intersections.dat"
SOLUTION_FILE_PREFIX = "output_r"
MISSING_VALUES_FILE_PREFIX = "output_mv"

####################################################################################################################################################################################################################################################################
## generic functions that dont belong to a class so can be called by subclasses of tornado.web.RequestHandler and tornado.websocket.WebSocketHandler equally - underscores are used so they dont mask the equivalent url endpoints
####################################################################################################################################################################################################################################################################

#gets that method part of the REST service path, e.g. /marxan-server/validateUser will return validateUser
def _getRESTMethod(path):
    pos = path.rfind("/")
    if pos > -1:
        return path[pos+1:]
    else:
        return ""
    
#creates a new user
def _createUser(obj, user, fullname, email, password, mapboxaccesstoken):
    #get the list of users
    users = _getUsers()
    if user in users:
        raise MarxanServicesError("User '" + user + "' already exists")
    #create the user folder
    obj.folder_user = MARXAN_FOLDER + user + os.sep
    os.mkdir(obj.folder_user)
    #copy the user.dat file
    shutil.copyfile(MARXAN_WEB_RESOURCES_FOLDER + USER_DATA_FILENAME, obj.folder_user + USER_DATA_FILENAME)
    #update the user.dat file parameters
    _updateParameters(obj.folder_user + USER_DATA_FILENAME, {'NAME': fullname,'EMAIL': email,'PASSWORD': password,'MAPBOXACCESSTOKEN': mapboxaccesstoken})

#gets a list of users
def _getUsers():
    #get a list of folders underneath the marxan home folder
    user_folders = glob.glob(MARXAN_FOLDER + "*/")
    #convert these into a list of users
    users = [user[:-1][user[:-1].rfind("/")+1:] for user in user_folders]
    if "input" in users: 
        users.remove("input")
    if "output" in users: 
        users.remove("output")
    return [u for u in users if u[:1] != "_"]
    
#gets the projects for the current user
def _getProjects(obj):
    #get a list of folders underneath the users home folder
    project_folders = glob.glob(MARXAN_FOLDER + obj.user + os.sep + "*/")
    #sort the folders
    project_folders.sort()
    projects = []
    #iterate through the project folders and get the parameters for each project to return
    tmpObj = ExtendableObject()
    for dir in project_folders:
        #get the name of the folder 
        project = dir[:-1][dir[:-1].rfind("/")+1:]
        if (project[:2] != "__"): #folders beginning with __ are system folders
            #get the data from the input file for this project
            tmpObj.project = project
            tmpObj.folder_project = MARXAN_FOLDER + obj.user + os.sep + project + os.sep
            _getProjectData(tmpObj)
            #create a dict to save the data
            projects.append({'name': project,'description': tmpObj.projectData["metadata"]["DESCRIPTION"],'createdate': tmpObj.projectData["metadata"]["CREATEDATE"],'oldVersion': tmpObj.projectData["metadata"]["OLDVERSION"]})
    obj.projects = projects

#creates a new empty project with the passed parameters
def _createProject(obj, name):
    #make sure the project does not already exist
    if os.path.exists(obj.folder_user + name):
        raise MarxanServicesError("The project '" + name + "' already exists")
    #copy the _project_template folder to the new location
    _copyDirectory(EMPTY_PROJECT_TEMPLATE_FOLDER, obj.folder_user + name)
    #set the paths to this project in the passed object - the arguments are normally passed as lists in tornado.get_argument
    _setFolderPaths(obj, {'user': [obj.user], 'project': [name]})

#deletes a project
def _deleteProject(obj):
    #delete the folder and all of its contents
    shutil.rmtree(obj.folder_project)

#clones a project from the source_folder which is a full folder path to the destination_folder which is a full folder path
def _cloneProject(source_folder, destination_folder):
    #get the project name
    original_project_name = source_folder[:-1].split("/")[-1]
    #get the new project folder
    new_project_folder = destination_folder + original_project_name + os.sep
    #recursively check that the folder does not exist until we get a new folder that doesnt exist
    while (os.path.exists(new_project_folder)):
        new_project_folder = new_project_folder[:-1] + "_copy/"
    #copy the project
    shutil.copytree(source_folder, new_project_folder)
    #update the description and create date
    _updateParameters(new_project_folder + PROJECT_DATA_FILENAME, {'DESCRIPTION': "Clone of project '" + original_project_name + "'",  'CREATEDATE': datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")})
    #return the name of the new project
    return new_project_folder[:-1].split("/")[-1]

#sets the various paths to the users folder and project folders using the request arguments in the passed object
def _setFolderPaths(obj, arguments):
    if "user" in arguments.keys():
        user = arguments["user"][0]
        obj.folder_user = MARXAN_FOLDER + user + os.sep
        obj.user = user
        #get the project folder and the input and output folders
        if "project" in arguments.keys():
            obj.folder_project = obj.folder_user + arguments["project"][0] + os.sep
            obj.folder_input =  obj.folder_project + "input" + os.sep
            obj.folder_output = obj.folder_project + "output" + os.sep
            obj.project = obj.get_argument("project")

#get the project data from the input.dat file as a categorised list of settings - using the obj.folder_project path and creating an attribute called projectData in the obj for the return data
def _getProjectData(obj):
    paramsArray = []
    filesDict = {}
    metadataDict = {}
    rendererDict = {}
    #get the file contents
    s = _readFile(obj.folder_project + PROJECT_DATA_FILENAME)
    #get the keys from the file
    keys = _getKeys(s)
    #iterate through the keys and get their values
    for k in keys:
        #some parameters we do not need to return
        if k in ["PUNAME","SPECNAME","PUVSPRNAME","BOUNDNAME","BLOCKDEF"]: # Input Files section of input.dat file
            key, value = _getKeyValue(s, k) 
            filesDict.update({ key:  value})
        elif k in ['BLM', 'PROP', 'RANDSEED', 'NUMREPS', 'NUMITNS', 'STARTTEMP', 'NUMTEMP', 'COSTTHRESH', 'THRESHPEN1', 'THRESHPEN2', 'SAVERUN', 'SAVEBEST', 'SAVESUMMARY', 'SAVESCEN', 'SAVETARGMET', 'SAVESUMSOLN', 'SAVEPENALTY', 'SAVELOG', 'RUNMODE', 'MISSLEVEL', 'ITIMPTYPE', 'HEURTYPE', 'CLUMPTYPE', 'VERBOSITY', 'SAVESOLUTIONSMATRIX']:
            key, value = _getKeyValue(s, k) #run parameters 
            paramsArray.append({'key': key, 'value': value})
        elif k in ['DESCRIPTION','CREATEDATE','PLANNING_UNIT_NAME','OLDVERSION','IUCN_CATEGORY']: # metadata section of the input.dat file
            key, value = _getKeyValue(s, k)
            metadataDict.update({key: value})
            if k=='PLANNING_UNIT_NAME':
                df2 = PostGIS().getDataFrame("select * from marxan.get_planning_units_metadata(%s)", [value])
                if (df2.shape[0] == 0):
                    metadataDict.update({'pu_alias': value,'pu_description': 'No description','pu_domain': 'Unknown domain','pu_area': 'Unknown area','pu_creation_date': 'Unknown date'})
                else:
                    #get the data from the metadata_planning_units table
                    metadataDict.update({'pu_alias': df2.iloc[0]['alias'],'pu_description': df2.iloc[0]['description'],'pu_domain': df2.iloc[0]['domain'],'pu_area': df2.iloc[0]['area'],'pu_creation_date': df2.iloc[0]['creation_date']})

        elif k in ['CLASSIFICATION', 'NUMCLASSES','COLORCODE', 'TOPCLASSES','OPACITY']: # renderer section of the input.dat file
            key, value = _getKeyValue(s, k)
            rendererDict.update({key: value})
    #set the project data
    obj.projectData = {}
    obj.projectData.update({'project': obj.project, 'metadata': metadataDict, 'files': filesDict, 'runParameters': paramsArray, 'renderer': rendererDict})
    
#gets the name of the input file from the projects input.dat file using the obj.folder_project path
def _getProjectInputFilename(obj, fileToGet):
    if not hasattr(obj, "projectData"):
        _getProjectData(obj)
    return obj.projectData["files"][fileToGet]

#gets the projects input data using the fileToGet, e.g. SPECNAME will return the data from the file corresponding to the input.dat file SPECNAME setting
def _getProjectInputData(obj, fileToGet, errorIfNotExists = False):
    filename = obj.folder_input + os.sep + _getProjectInputFilename(obj, fileToGet)
    return _loadCSV(filename, errorIfNotExists)
    
#get the data on the user from the user.dat file 
def _getUserData(obj):
    userDataFilename = obj.folder_user + USER_DATA_FILENAME
    if not os.path.exists(userDataFilename):
        raise MarxanServicesError("The user.dat file '" + userDataFilename +"' does not exist") 
    #get the file contents
    s = _readFile(userDataFilename)
    #get the keys from the file
    keys = _getKeys(s)
    #iterate through the keys, get their values add add them to this request object in the userData object
    obj.userData = {}
    for k in keys:
        key, value = _getKeyValue(s, k)
        #update the  dict
        if value == "true":
            value = True
        if value == "false":
            value = False
        obj.userData[key] = value

#get the species data from the spec.dat file as a DataFrame (and joins it to the data from the PostGIS database if it is the Marxan web version)
def _getSpeciesData(obj):
    #get the values from the spec.dat file - speciesDataFilename will be empty if it doesn't exist yet
    df = _getProjectInputData(obj, "SPECNAME")
    #create the output data frame using the id field as an index
    output_df = df.set_index("id")
    #add the index as a column
    output_df['oid'] = output_df.index
    #see if the version of marxan is the old version
    if obj.projectData["metadata"]["OLDVERSION"]:
        #return the data from the spec.dat file with additional fields manually added
        output_df['tmp'] = 'Unique identifer: '
        output_df['alias'] = output_df['tmp'].str.cat((output_df['oid']).apply(str)) # returns: 'Unique identifer: 4702435'
        output_df['feature_class_name'] = output_df['oid']
        output_df['description'] = "No description"
        output_df['creation_date'] = "Unknown"
        output_df['area'] = -1
        output_df['tilesetid'] = ''
        output_df = output_df[["alias", "feature_class_name", "description", "creation_date", "area", "tilesetid", "prop", "spf", "oid"]]
    else:
        #get the postgis feature data
        df2 = PostGIS().getDataFrame("select * from marxan.get_features()")
        #join the species data to the PostGIS data
        output_df = output_df.join(df2.set_index("oid"))
    #rename the columns that are sent back to the client as the names of various properties are different in Marxan compared to the web client
    output_df = output_df.rename(index=str, columns={'prop': 'target_value', 'oid':'id'})    
    #get the target as an integer - Marxan has it as a percentage, i.e. convert 0.17 -> 17
    output_df['target_value'] = (output_df['target_value'] * 100).astype(int)
    obj.speciesData = output_df
        
#gets data for a single feature
def _getFeature(obj, oid):
    obj.data = PostGIS().getDataFrame("SELECT * FROM marxan.get_feature(%s)", [oid])

#get all species information from the PostGIS database
def _getAllSpeciesData(obj):
    obj.allSpeciesData = PostGIS().getDataFrame("select oid::integer id,feature_class_name , alias , description , _area area, extent, creation_date::text, tilesetid from marxan.metadata_interest_features order by alias;")

#get the information about which species have already been preprocessed
def _getSpeciesPreProcessingData(obj):
    obj.speciesPreProcessingData = _loadCSV(obj.folder_input + FEATURE_PREPROCESSING_FILENAME)

#get the planning units information
def _getPlanningUnitsData(obj):
    df = _getProjectInputData(obj, "PUNAME")
    #normalise the planning unit data to make the payload smaller        
    obj.planningUnitsData = _normaliseDataFrame(df, "status", "id")

#get the protected area intersections information
def _getProtectedAreaIntersectionsData(obj):
    df = _loadCSV(obj.folder_input + PROTECTED_AREA_INTERSECTIONS_FILENAME)
    #normalise the protected area intersections to make the payload smaller           
    obj.protectedAreaIntersectionsData = _normaliseDataFrame(df, "iucn_cat", "puid")
    
#gets the marxan log after a run
def _getMarxanLog(obj):
    if (os.path.exists(obj.folder_output + OUTPUT_LOG_FILENAME)):
        log = _readFile(obj.folder_output + OUTPUT_LOG_FILENAME)
    else:
        log = ""
    #there are some characters in the log file which cause the json parser to fail - remove them
    log = log.replace("\x90","")
    log = log.replace(chr(176),"") #Graphic character, low density dotted
    obj.marxanLog = log

def _getBestSolution(obj):
    obj.bestSolution = _loadCSV(obj.folder_output + BEST_SOLUTION_FILENAME)

def _getOutputSummary(obj):
    obj.outputSummary = _loadCSV(obj.folder_output + OUTPUT_SUMMARY_FILENAME)

def _getSummedSolution(obj):
    df = _loadCSV(obj.folder_output + SUMMED_SOLUTION_FILENAME)
    obj.summedSolution = _normaliseDataFrame(df, "number", "planning_unit")

def _getSolution(obj, solutionId):
    if os.path.exists(obj.folder_output + SOLUTION_FILE_PREFIX + "%05d" % int(solutionId) + ".txt"):
        df = _loadCSV(obj.folder_output + SOLUTION_FILE_PREFIX + "%05d" % int(solutionId) + ".txt")
        obj.solution = _normaliseDataFrame(df, "solution", "planning_unit")
    else:
        obj.solution = []
        raise MarxanServicesError("Solution '" + str(solutionId) + "' in project '" + obj.get_argument('project') + "' no longer exists")

def _getMissingValues(obj, solutionId):
    df = _loadCSV(obj.folder_output + MISSING_VALUES_FILE_PREFIX + "%05d" % int(solutionId) + ".txt")
    obj.missingValues = df.to_dict(orient="split")["data"]

#updates/creates the spec.dat file with the passed interest features
def _updateSpeciesFile(obj, interest_features, target_values, spf_values, create = False):
    #get the features to create/update as a list of integer ids
    ids = _txtIntsToList(interest_features)
    props = _txtIntsToList(target_values) 
    spfs = spf_values.split(",") 
    if create:
        #there are no existing ids as we are creating a new pu.dat file
        removedIds = []    
    else:
        #get the current list of features
        df = _getProjectInputData(obj, "SPECNAME")
        if df.empty:
            currentIds = []
        else:
            currentIds = df.id.unique().tolist() 
        #get the list of features to remove from the current list (i.e. they are not in the passed list of interest features)
        removedIds = list(set(currentIds) - set(ids))
        #update the puvspr.dat file and the feature preprocessing files to remove any species that are no longer in the project
        if len(removedIds) > 0:
            #get the name of the puvspr file from the project data
            puvsprFilename = _getProjectInputFilename(obj, "PUVSPRNAME")
            #update the puvspr.dat file
            _deleteRecordsInTextFile(obj.folder_input + puvsprFilename, "species", removedIds, False)
            #update the preprocessing.dat file to remove any species that are no longer in the project - these will need to be preprocessed again
            _deleteRecordsInTextFile(obj.folder_input + FEATURE_PREPROCESSING_FILENAME, "id", removedIds, False)
    #create the dataframe to write to file
    records = []
    for i in range(len(ids)):
        if i not in removedIds:
            records.append({'id': str(ids[i]), 'prop': str(float(props[i])/100), 'spf': spfs[i]})
    df = pandas.DataFrame(records)
    #sort the records by the id fied
    df = df.sort_values(by=['id'])
    #write the data to file
    _writeCSV(obj, "SPECNAME", df)

#create the array of the puids 
def _puidsArrayToPuDatFormat(puid_array, pu_status):
    return pandas.DataFrame([[int(i),pu_status] for i in puid_array], columns=['id','status_new']).astype({'id':'int64','status_new':'int64'})

#creates the pu.dat file using the ids from the PostGIS feature class as the planning unit ids in the pu.dat file
def _createPuFile(obj, planning_grid_name):
    #get the path to the pu.dat file
    filename = obj.folder_input + PLANNING_UNITS_FILENAME
    #create the pu.dat file using a postgis query
    PostGIS().executeToText(sql.SQL("COPY (SELECT puid as id,1::double precision as cost,0::integer as status FROM marxan.{}) TO STDOUT WITH CSV HEADER;").format(sql.Identifier(planning_grid_name)), filename)
    #update the input.dat file
    _updateParameters(obj.folder_project + PROJECT_DATA_FILENAME, {'PUNAME': PLANNING_UNITS_FILENAME})

#updates the pu.dat file with the passed arrays of ids for the various statuses
def _updatePuFile(obj, status1_ids, status2_ids, status3_ids):
    status1 = _puidsArrayToPuDatFormat(status1_ids,1)
    status2 = _puidsArrayToPuDatFormat(status2_ids,2)
    status3 = _puidsArrayToPuDatFormat(status3_ids,3)
    #get the path to the pu.dat file
    filename = obj.folder_input + _getProjectInputFilename(obj, "PUNAME")
    #read the data from the pu.dat file 
    df = _loadCSV(filename)
    #reset the status for all planning units
    df['status'] = 0
    #concatenate the status arrays
    df2 = pandas.concat([status1, status2, status3])
    #join the new statuses to the ones from the pu.dat file
    df = df.merge(df2, on='id', how='left')
    #update the status value
    df['status_final'] = df['status_new'].fillna(df['status']).astype('int')
    df = df.drop(['status_new', 'status'], axis=1)
    df.rename(columns={'status_final':'status'}, inplace=True)
    #set the datatypes
    df = df.astype({'id':'int64','cost':'int64','status':'int64'})
    #sort the records by the id fied
    df = df.sort_values(by=['id'])
    #write to file
    _writeCSV(obj, "PUNAME", df)
    
#loads a csv file and returns the data as a dataframe or an empty dataframe if the file does not exist. If errorIfNotExists is True then it raises an error.
def _loadCSV(filename, errorIfNotExists = False):
    if (os.path.exists(filename)):
        df = pandas.read_csv(filename)
    else:
        if errorIfNotExists:
            raise MarxanServicesError("The file '" + filename + "' does not exist")
        else:
            df = pandas.DataFrame()
    return df

#saves the dataframe to a csv file specified by the fileToWrite, e.g. _writeCSV(self, "PUVSPRNAME", df) - this only applies to the files managed by Marxan in the input.dat file, e.g. SPECNAME, PUNAME, PUVSPRNAME, BOUNDNAME
def _writeCSV(obj, fileToWrite, df, writeIndex = False):
    _filename = _getProjectInputFilename(obj, fileToWrite)
    if _filename == "": #the file has not previously been created
        raise MarxanServicesError("The filename for the " + fileToWrite + ".dat file has not been set in the input.dat file")
    df.to_csv(obj.folder_input + _filename, index = writeIndex)

#writes the dataframe to the file - for files not managed in the input.dat file or if the filename has not yet been set in the input.dat file
def _writeToDatFile(file, dataframe):
    #see if the file exists
    if (os.path.exists(file)):
        #read the current data
        df = pandas.read_csv(file)
    else:
        #create the new dataframe
        df = pandas.DataFrame()
    #append the new records
    df = df.append(dataframe)
    #write the file
    df.to_csv(file, index=False)
    
def _writeFile(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()
    
#gets a files contents as a string
def _readFile(filename):
    f = open(filename)
    s = f.read()
    f.close()
    return s

#deletes all of the files in the passed folder
def _deleteAllFiles(folder):
    files = glob.glob(folder + "*")
    for f in files:
        os.remove(f)

#copies a directory from src to dest recursively
def _copyDirectory(src, dest):
    try:
        shutil.copytree(src, dest)
    # Directories are the same
    except shutil.Error as e:
        raise MarxanServicesError('Directory not copied. Error: %s' % e)
    # Any error saying that the directory doesn't exist
    except OSError as e:
        raise MarxanServicesError('Directory not copied. Error: %s' % e)
        
#updates the parameters in the *.dat file with the new parameters passed as a dict
def _updateParameters(data_file, newParams):
    if newParams:
        #get the existing parameters 
        s = _readFile(data_file)
        #update any that are passed in as query params
        for k, v in newParams.iteritems():
            try:
                p1 = s.index(k) #get the first position of the parameter
                if p1>-1:
                    p2 = _getEndOfLine(s[p1:]) #get the position of the end of line
                    s = s[:p1] + k + " " + v + s[(p1 + p2):]
                #write these parameters back to the *.dat file
                _writeFile(data_file, s)
            except ValueError:
                continue
    return 

#gets the position of the end of the line which may be different in windows/unix generated files
def _getEndOfLine(text):
    try:
        p = text.index("\r\n") 
    except (ValueError):
        p = text.index("\n") 
    return p

#returns all the keys from a set of KEY/VALUE pairs in a string expression
def _getKeys(s):
    #get all the parameter keys
    matches = re.findall('\\n[A-Z1-9_]{2,}', s, re.DOTALL)
    return [m[1:] for m in matches]
  
#gets the key value combination from the text, e.g. PUNAME pu.dat    
def _getKeyValue(text, parameterName):
    p1 = text.index(parameterName)
    value = text[p1 + len(parameterName) + 1:text.index("\r",p1)]
    #convert any boolean text strings to boolean values - these will then get returned as javascript bool types
    if value == "True":
        value = True
    if value == "False":
        value = False
    return parameterName, value

#converts a data frame with duplicate values into a normalised array
def _normaliseDataFrame(df, columnToNormaliseBy, puidColumnName):
    if df.empty:
        return []
    #get the groups from the data
    groups = df.groupby(by = columnToNormaliseBy).groups
    #build the response, e.g. a normal data frame with repeated values in the columnToNormaliseBy -> [["VI", [7, 8, 9]], ["IV", [0, 1, 2, 3, 4]], ["V", [5, 6]]]
    response = [[g, df[puidColumnName][groups[g]].values.tolist()] for g in groups if g not in [0]]
    return response

#gets the statistics for a species from the puvspr.dat file, i.e. count and area, as a dataframe record
def _getPuvsprStats(df, speciesId):
    #get the count of intersecting planning units
    pu_count = df[df.species.isin([speciesId])].agg({'pu' : ['count']})['pu'].iloc[0]
    #get the total area of the feature across all planning units
    pu_area = df[df.species.isin([speciesId])].agg({'amount': ['sum']})['amount'].iloc[0]
    #return the pu_area and pu_count to the preprocessing.dat file 
    return pandas.DataFrame({'id':speciesId, 'pu_area': [pu_area], 'pu_count': [pu_count]}).astype({'id': 'int', 'pu_area':'float', 'pu_count':'int'})
            
#deletes the records in the text file that have id values that match the passed ids
def _deleteRecordsInTextFile(filename, id_columnname, ids, write_index):
    if (filename) and (os.path.exists(filename)):
        #if the file exists then get the existing data
        df = _loadCSV(filename)
        #remove the records with the matching ids
        df = df[~df[id_columnname].isin(ids)]
        #write the results back to the file
        df.to_csv(filename, index = write_index)
    else:
        raise MarxanServicesError("The file '" + filename + "' does not exist")

#converts a comma-separated set of integer values to a list of integers
def _txtIntsToList(txtInts):
    if txtInts:
        return [int(s) for s in txtInts.split(",")] 
    else:
        return []

#checks that all of the arguments in argumentList are in the arguments dictionary
def _validateArguments(arguments, argumentList):
    for argument in argumentList:
        if argument not in arguments.keys():
            raise MarxanServicesError("Missing input argument:" + argument)

#converts the raw arguments from the request.arguments parameter into a simple dict excluding those in omitArgumentList
#e.g. _getSimpleArguments(self.request.arguments, ['user','project','callback']) would convert {'project': ['Tonga marine 30km2'], 'callback': ['__jp13'], 'COLORCODE': ['PiYG'], 'user': ['andrew']} to {'COLORCODE': 'PiYG'}
def _getSimpleArguments(arguments, omitArgumentList):
    returnDict = {}
    for argument in arguments:
        if argument not in omitArgumentList:
            returnDict.update({argument: arguments[argument][0]})
    return returnDict

#gets the passed argument name as an array of integers, e.g. ['12,15,4,6'] -> [12,15,4,6]
def _getIntArrayFromArg(arguments, argName):
    if argName in arguments.keys():
        return [int(s) for s in arguments[argName][0].split(",")]
    else:
        return []
    
#creates a zip file with the list of files in the folder with the filename zipfilename
def _createZipfile(lstFileNames, folder, zipfilename):
    with zipfile.ZipFile(folder + zipfilename, 'w') as myzip:
        for f in lstFileNames:   
            arcname = os.path.split(f)[1]
            myzip.write(f,arcname)

#deletes a zip file and the archive files, e.g. deleteZippedShapefile(MARXAN_FOLDER, "pngprovshapes.zip","pngprov")
def _deleteZippedShapefile(folder, zipfile, archivename):
    files = glob.glob(folder + archivename + '.*')
    if len(files)>0:
        [os.remove(f) for f in files if f[-3:] in ['shx','shp','xml','sbx','prj','sbn','zip','dbf','cpg','qpj']]       
    if (os.path.exists(folder + zipfile)):
        os.remove(folder + zipfile)

#unzips a zip file
def _unzipFile(filename):
    #unzip the shapefile
    if not os.path.exists(MARXAN_FOLDER + filename):
        raise MarxanServicesError("The zip file '" + filename + "' does not exist")
    zip_ref = zipfile.ZipFile(MARXAN_FOLDER + filename, 'r')
    filenames = zip_ref.namelist()
    rootfilename = filenames[0][:-4]
    zip_ref.extractall(MARXAN_FOLDER)
    zip_ref.close()
    return rootfilename

#uploads a tileset to mapbox using the filename of the file (filename) to upload and the name of the resulting tileset (_name)
def _uploadTileset(filename, _name):
    #create an instance of the upload service
    service = Uploader(access_token=MAPBOX_ACCESS_TOKEN)    
    with open(filename, 'rb') as src:
        upload_resp = service.upload(src, _name)
        upload_id = upload_resp.json()['id']
        return upload_id
        
def _uploadTilesetToMapbox(feature_class_name, mapbox_layer_name):
    #create the file to upload to MapBox - now using shapefiles as kml files only import the name and description properties into a mapbox tileset
    cmd = OGR2OGR_EXECUTABLE + ' -f "ESRI Shapefile" ' + MARXAN_FOLDER + feature_class_name + '.shp' + ' "PG:host=localhost dbname=biopama user=jrc password=thargal88" -sql "select * from Marxan.' + feature_class_name + '" -nln ' + mapbox_layer_name + ' -s_srs EPSG:3410 -t_srs EPSG:3857'
    status, output = commands.getstatusoutput(cmd) 
    #check for errors from the ogr2ogr command
    if output != "":
        raise MarxanServicesError("The ogr2ogr command failed with the error: " + output)
    #zip the shapefile to upload to Mapbox
    lstFilenames = glob.glob(MARXAN_FOLDER + feature_class_name + '.*')
    zipfilename = MARXAN_FOLDER + feature_class_name + ".zip"
    _createZipfile(lstFilenames, MARXAN_FOLDER, feature_class_name + ".zip")
    #upload to mapbox
    uploadId = _uploadTileset(zipfilename, feature_class_name)
    #delete the temporary shapefile file and zip file
    _deleteZippedShapefile(MARXAN_FOLDER, feature_class_name + ".zip", feature_class_name)
    return uploadId
    
#imports the feature from a zipped shapefile (given by filename)
def _importFeature(filename, name, description):
    #unzip the shapefile
    rootfilename = _unzipFile(filename) 
    #import the shapefile into PostGIS
    postgis = PostGIS()
    postgis.importShapefile(rootfilename + ".shp", "undissolved", "EPSG:3410")
    #TODO: implement the upload to Mapbox
    uploadId = _uploadTileset(MARXAN_FOLDER + filename, rootfilename)
    tilesetId = MAPBOX_USER + "." + rootfilename
    #delete the shapefile and the zip file
    #TODO: _deleteZippedShapefile is cleanup code and wherever it occurs it should always be run even if an exception occurs
    _deleteZippedShapefile(MARXAN_FOLDER, filename, rootfilename)
    #dissolve the feature class
    postgis.execute(sql.SQL("SELECT ST_Union(wkb_geometry) geometry INTO marxan.{} FROM marxan.undissolved;").format(sql.Identifier(rootfilename)))   
    #create an index
    postgis.execute(sql.SQL("CREATE INDEX idx_" + uuid.uuid4().hex + " ON marxan.{} USING GIST (geometry);").format(sql.Identifier(rootfilename)))
    #drop the undissolved feature class
    postgis.execute("DROP TABLE IF EXISTS marxan.undissolved;") 
    #create a record for this new feature in the metadata_interest_features table
    id = postgis.execute(sql.SQL("INSERT INTO marxan.metadata_interest_features SELECT %s, %s, %s, now(), sub._area, %s, sub.extent FROM (SELECT ST_Area(geometry) _area, box2d(ST_Transform(ST_SetSRID(geometry,3410),4326)) extent FROM marxan.{} GROUP BY geometry) AS sub RETURNING oid;").format(sql.Identifier(rootfilename)), [rootfilename, name, description, tilesetId], "One")[0]
    return id

#imports the planning unit grid from a zipped shapefile (given by filename) and starts the upload to Mapbox
def _importPlanningUnitGrid(filename, name, description):
    #unzip the shapefile
    rootfilename = _unzipFile(filename) 
    #import the shapefile into PostGIS
    postgis = PostGIS()
    postgis.importShapefile(rootfilename + ".shp", rootfilename, "EPSG:3410")
    #create an index
    postgis.execute(sql.SQL("CREATE INDEX idx_" + uuid.uuid4().hex + " ON marxan.{} USING GIST (wkb_geometry);").format(sql.Identifier(rootfilename)))
    #create a record for this new feature in the metadata_planning_units table
    feature_class_name = postgis.execute("INSERT INTO marxan.metadata_planning_units(feature_class_name,alias,description,creation_date) VALUES (%s,%s,%s,now()) RETURNING feature_class_name;", [rootfilename, name, description], "One")[0]
    #upload to mapbox
    uploadId = _uploadTileset(MARXAN_FOLDER + filename, rootfilename)
    #delete the shapefile and the zip file
    _deleteZippedShapefile(MARXAN_FOLDER, filename, rootfilename)
    return {'feature_class_name': feature_class_name, 'uploadId': uploadId}
    
#populates the data in the feature_preprocessing.dat file from an existing puvspr.dat file, e.g. after an import from an old version of Marxan
def _createFeaturePreprocessingFileFromImport(obj):
    #read the unique species ids from the puvspr file
    df = _getProjectInputData(obj, "PUVSPRNAME")
    #get the unique species ids
    ids = sorted(df.species.unique().tolist())
    #iterate through the species ids and get the data for them
    for id in ids:
        #get the summary information and write it to the feature preprocessing file
        record = _getPuvsprStats(df, id)
        _writeToDatFile(obj.folder_input + FEATURE_PREPROCESSING_FILENAME, record)
        
#detects whether the request is for a websocket from a tornado.httputil.HTTPServerRequest
def _requestIsWebSocket(request):
    if "upgrade" in request.headers:
        if request.headers["upgrade"] == "websocket":
            return True
        else:
            return False
    else:
        return True

#to prevent CORS errors in the client
def _checkCORS(obj):
    if DISABLE_SECURITY:
        return 
    #get the referer
    if "Referer" in obj.request.headers.keys():
        referer = obj.request.headers.get("Referer")
        #for GET requests the 'Referer' header will be used - this will include a trailing forward slash
        #for POST requests the 'Origin' header will be used - this has no url parameters and no trailing forward slash
        origin = referer if obj.request.method == "GET" else referer[:-1]
        if referer in PERMITTED_DOMAINS:
            obj.set_header("Access-Control-Allow-Origin", origin)
            obj.set_header("Access-Control-Allow-Credentials", "true")
        else:
            raise HTTPError(403, "The origin '" + referer + "' does not have permission to access the service (CORS error)", reason = "The origin '" + referer + "' does not have permission to access the service (CORS error)")
    else:
        raise HTTPError(403, NO_REFERER_ERROR, reason = NO_REFERER_ERROR)

#test all requests to make sure the user is authenticated - if not returns a 403
def _authenticate(obj):
    if DISABLE_SECURITY:
        return 
    #check for an authenticated user
    if not obj.current_user: 
        #if not return a 401
        raise HTTPError(401, NOT_AUTHENTICATED_ERROR, reason = NOT_AUTHENTICATED_ERROR)

#tests the role has access to the method
def _authoriseRole(obj, method):
    if DISABLE_SECURITY:
        return 
    #get the requested role
    role = obj.get_secure_cookie("role")
    #get the list of methods that this role cannot access
    unauthorised = ROLE_UNAUTHORISED_METHODS[role]
    if method in unauthorised:
        raise HTTPError(403, "The '" + role + "' role does not have permission to access the '" + method + "' service", reason = "The '" + role + "' role does not have permission to access the '" + method + "' service")

#tests if the user can access the service - Admin users can access projects belonging to other users
def _authoriseUser(obj):
    if DISABLE_SECURITY:
        return 
    #if the call includes a user argument
    if "user" in obj.request.arguments.keys():
        #see if the user argument matches the obj.current_user and is not the _clumping project (this is the only exception as it is needed for the clumping)
        if ((obj.get_argument("user") != obj.current_user) and (obj.get_argument("user") != "_clumping")):
            #get the requested role
            role = obj.get_secure_cookie("role")
            if role != "Admin":
                raise HTTPError(403, "The user '" + obj.current_user + "' has no permission to access a project of another user", reason = "The user '" + obj.current_user + "' has no permission to access a project of another user")    
    
####################################################################################################################################################################################################################################################################
## generic classes
####################################################################################################################################################################################################################################################################

class MarxanServicesError(Exception):
    """Exception Class that allows the Marxan Services REST Server to raise custom exceptions"""
    pass

class ExtendableObject(object):
    pass

####################################################################################################################################################################################################################################################################
## class to return data from postgis synchronously - the asynchronous version is the QueryWebSocketHandler class
####################################################################################################################################################################################################################################################################

class PostGIS():
    def __init__(self):
        #get a connection to the database
        self.connection = psycopg2.connect(CONNECTION_STRING)
        self.cursor = self.connection.cursor()

    #does argument binding to prevent sql injection attacks
    def _mogrify(self, sql, data):
        if data is not None:
            return self.cursor.mogrify(sql, data)
        else:
            return sql
    
    #get a pandas data frame 
    def _getDataFrame(self, sql, data):
        #do any argument binding 
        sql = self._mogrify(sql, data)
        return pandas.read_sql_query(sql, self.connection)

    #called in exceptions to close the cursor and connection
    def _cleanup(self):
        self.cursor.close()
        self.connection.commit()
        self.connection.close()
        
    #executes a query and returns the data as a data frame
    def getDataFrame(self, sql, data = None):
        return self._getDataFrame(sql, data)

    #executes a query and returns the data as a records array
    def getDict(self, sql, data = None):
        df = self._getDataFrame(sql, data)
        return df.to_dict(orient="records")
            
    #executes a query and returns the first records as specified by the numberToFetch parameter
    def execute(self, sql, data = None, numberToFetch = "None"):
        try:
            records = []
            #do any argument binding 
            sql = self._mogrify(sql, data)
            self.cursor.execute(sql)
            #commit the transaction immediately
            self.connection.commit()
            if numberToFetch == "One":
                records = self.cursor.fetchone()
            elif numberToFetch == "All":
                records = self.cursor.fetchall()
            return records
        except Exception as e:
            self._cleanup()
            raise MarxanServicesError(e.message)
    
    #executes a query and writes the results to a text file
    def executeToText(self, sql, filename):
        try:
            with open(filename, 'w') as f:
                self.cursor.copy_expert(sql, f)
                self.connection.commit()
        except Exception as e:
            self._cleanup()
            raise MarxanServicesError(e.message)
        
    #imports a shapefile into PostGIS
    def importShapefile(self, shapefile, feature_class_name, epsgCode):
        try:
            #drop the feature class if it already exists
            self.execute(sql.SQL("DROP TABLE IF EXISTS marxan.{};").format(sql.Identifier(feature_class_name)))
            #using ogr2ogr produces an additional field - the ogc_fid field which is an autonumbering oid
            cmd = OGR2OGR_EXECUTABLE + ' -f "PostgreSQL" PG:"host=localhost user=jrc dbname=biopama password=thargal88" ' + MARXAN_FOLDER + shapefile + ' -nlt GEOMETRY -lco SCHEMA=marxan -nln ' + feature_class_name + ' -t_srs ' + epsgCode
            #run the import
            status, output = commands.getstatusoutput(cmd) 
            #check for errors
            if (output != ''):
                raise MarxanServicesError("Error importing shapefile: " + output)
        except Exception as e:
            self._cleanup()
            raise MarxanServicesError(e.message)
                
    def __del__(self):
        self._cleanup()

####################################################################################################################################################################################################################################################################
## baseclass for handling REST requests
####################################################################################################################################################################################################################################################################

class MarxanRESTHandler(tornado.web.RequestHandler):
    #to prevent CORS errors in the client
    def set_default_headers(self):
        if DISABLE_SECURITY:
            self.set_header("Access-Control-Allow-Origin", "*")

    #get the current user
    def get_current_user(self):
        return self.get_secure_cookie("user")

    #called before the request is processed - does the neccessary authentication/authorisation
    def prepare(self):
        #check the referer can call the REST end point from their domain
        _checkCORS(self)
        #get the requested method
        method = _getRESTMethod(self.request.path)
        #allow access to some methods without authentication/authorisation, e.g. to create new users or validate a user
        if method not in PERMITTED_METHODS:
            #check the request is authenticated
            _authenticate(self)
            #check the users role has access to the requested service
            _authoriseRole(self, method)
            #check the user has access to the specific resource, i.e. the 'User' role cannot access projects from other users
            _authoriseUser(self)
            #instantiate the response dictionary
            self.response = {}
        #set the folder paths for the user and optionally project
        _setFolderPaths(self, self.request.arguments)
        # self.send_response({"error": repr(e)})
    
    #used by all descendent classes to write the return payload and send it
    def send_response(self, response):
        try:
            #set the return header as json
            self.set_header('Content-Type','application/json')
            #convert the response dictionary to json
            content = json.dumps(response)
        #sometimes the Marxan log causes json encoding issues
        except (UnicodeDecodeError) as e: 
            if 'log' in response.keys():
                response.update({"log": "Server warning: Unable to encode the Marxan log. <br/>" + repr(e), "warning": "Unable to encode the Marxan log"})
                content = json.dumps(response)        
        finally:
            if "callback" in self.request.arguments.keys():
                self.write(self.get_argument("callback") + "(" + content + ")")
            else:
                self.write(content)
    
    #uncaught exception handling that captures any exceptions in the descendent classes and writes them back to the client - RETURNING AN HTTP STATUS CODE OF 200 CAN BE CAUGHT BY JSONP
    # def write_error(self, status_code, **kwargs):
        # if "exc_info" in kwargs:
        #     trace = ""
        #     for line in traceback.format_exception(*kwargs["exc_info"]):
        #         trace = trace + line
        #     lastLine = traceback.format_exception(*kwargs["exc_info"])[len(traceback.format_exception(*kwargs["exc_info"]))-1]
        #     self.set_status(status_code)
        #     # self.set_status(200)
        #     # self.send_response({"error":lastLine, "trace" : trace})
        #     self.finish()
    
####################################################################################################################################################################################################################################################################
## RequestHandler subclasses
####################################################################################################################################################################################################################################################################

#creates a new user
#POST ONLY
class createUser(MarxanRESTHandler):
    def post(self):
        #validate the input arguments 
        _validateArguments(self.request.arguments, ["user","password", "fullname", "email", "mapboxaccesstoken"])  
        #create the user
        _createUser(self, self.get_argument('user'), self.get_argument('fullname'), self.get_argument('email'), self.get_argument('password'), self.get_argument('mapboxaccesstoken'))
        #copy the start project into the users folder
        _cloneProject(START_PROJECT_FOLDER, MARXAN_FOLDER + self.get_argument('user') + os.sep)
        #set the response
        self.send_response({'info': "User '" + self.get_argument('user') + "' created"})

#creates a project
#POST ONLY
class createProject(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','description','planning_grid_name','interest_features','target_values','spf_values'])  
        #create the empty project folder
        _createProject(self, self.get_argument('project'))
        #update the projects parameters
        _updateParameters(self.folder_project + PROJECT_DATA_FILENAME, {'DESCRIPTION': self.get_argument('description'), 'CREATEDATE': datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S"), 'PLANNING_UNIT_NAME': self.get_argument('planning_grid_name')})
        #create the spec.dat file
        _updateSpeciesFile(self, self.get_argument("interest_features"), self.get_argument("target_values"), self.get_argument("spf_values"), True)
        #create the pu.dat file
        _createPuFile(self, self.get_argument('planning_grid_name'))
        #set the response
        self.send_response({'info': "Project '" + self.get_argument('project') + "' created", 'name': self.get_argument('project')})

#creates a simple project for the import wizard
#POST ONLY
class createImportProject(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])  
        #create the empty project folder
        _createProject(self, self.get_argument('project'))
        #set the response
        self.send_response({'info': "Project '" + self.get_argument('project') + "' created", 'name': self.get_argument('project')})

#updates a project from the Marxan old version to the new version
#https://db-server-blishten.c9users.io:8081/marxan-server/upgradeProject?user=andrew&project=test2&callback=__jp7
class upgradeProject(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])  
        #get the projects existing data from the input.dat file
        old = _readFile(self.folder_project + PROJECT_DATA_FILENAME)
        #get an empty projects data
        new = _readFile(EMPTY_PROJECT_TEMPLATE_FOLDER + PROJECT_DATA_FILENAME)
        #everything from the 'DESCRIPTION No description' needs to be added
        pos = new.find("DESCRIPTION No description")
        if pos > -1:
            newText = new[pos:]
            old = old + "\n" + newText
            _writeFile(self.folder_project + PROJECT_DATA_FILENAME, old)
        else:
            raise MarxanServicesError("Unable to update the old version of Marxan to the new one")
        #populate the feature_preprocessing.dat file using data in the puvspr.dat file
        _createFeaturePreprocessingFileFromImport(self)
        #delete the contents of the output folder
        _deleteAllFiles(self.folder_output)
        #set the response
        self.send_response({'info': "Project '" + self.get_argument("project") + "' updated", 'project': self.get_argument("project")})

#deletes a project
#https://db-server-blishten.c9users.io:8081/marxan-server/deleteProject?user=andrew&project=test2&callback=__jp7
class deleteProject(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])  
        #get the existing projects
        _getProjects(self)
        if len(self.projects) == 1:
            raise MarxanServicesError("You cannot delete all projects")   
        _deleteProject(self)
        #set the response
        self.send_response({'info': "Project '" + self.get_argument("project") + "' deleted", 'project': self.get_argument("project")})

#clones the project
#https://db-server-blishten.c9users.io:8081/marxan-server/cloneProject?user=andrew&project=Tonga%20marine%2030km2&callback=__jp15
class cloneProject(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])  
        #clone the folder recursively
        clonedName = _cloneProject(self.folder_project, self.folder_user)
        #set the response
        self.send_response({'info': "Project '" + clonedName + "' created", 'name': clonedName})

#creates n clones of the project with a range of BLM values in the _clumping folder
#https://db-server-blishten.c9users.io:8081/marxan-server/createProjectGroup?user=andrew&project=Tonga%20marine%2030km2&copies=5&blmValues=0.1,0.2,0.3,0.4,0.5&callback=__jp15
class createProjectGroup(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','copies','blmValues'])  
        #get the BLM values as a list
        blmValuesList = self.get_argument("blmValues").split(",")
        #initialise the project name array
        projects = []
        #clone the users project folder n times
        for i in range(int(self.get_argument("copies"))):
            #get the project name
            projectName = uuid.uuid4().hex
            #add the project name to the array
            projects.append({'projectName': projectName, 'clump': i})
            shutil.copytree(self.folder_project, CLUMP_FOLDER + projectName)
            #delete the contents of the output folder in that cloned project
            _deleteAllFiles(CLUMP_FOLDER + projectName + os.sep + "output" + os.sep)
            #update the BLM and NUMREP values in the project
            _updateParameters(CLUMP_FOLDER + projectName + os.sep + PROJECT_DATA_FILENAME, {'BLM': blmValuesList[i], 'NUMREPS': '1'})
        #set the response
        self.send_response({'info': "Project group created", 'data': projects})

#deletes a project cluster
#https://db-server-blishten.c9users.io:8081/marxan-server/deleteProjects?projectNames=2dabf1b862da4c2e87b2cd9d8b38bb73,81eda0a43a3248a8b4881caae160667a,313b0d3f733142e3949cf6129855be19,739f40f4d1c94907b2aa814470bcd7f7,15210235bec341238a816ce43eb2b341&callback=__jp15
class deleteProjects(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['projectNames'])  
        #get the project names
        projectNames = self.get_argument("projectNames").split(",")
        #delete the folders
        for projectName in projectNames:
            if os.path.exists(CLUMP_FOLDER + projectName):
                shutil.rmtree(CLUMP_FOLDER + projectName)        
        #set the response
        self.send_response({'info': "Projects deleted"})

#renames a project
#https://db-server-blishten.c9users.io:8081/marxan-server/renameProject?user=andrew&project=Tonga%20marine%2030km2&newName=Tonga%20marine%2030km&callback=__jp5
class renameProject(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','newName'])  
        #rename the folder
        os.rename(self.folder_project, self.folder_user + self.get_argument("newName"))
        #set the new name as the users last project so it will load on login
        _updateParameters(self.folder_user + USER_DATA_FILENAME, {'LASTPROJECT': self.get_argument("newName")})
        #set the response
        self.send_response({"info": "Project renamed to '" + self.get_argument("newName") + "'", 'project': self.get_argument("project")})

#https://db-server-blishten.c9users.io:8081/marxan-server/getCountries?callback=__jp0
class getCountries(MarxanRESTHandler):
    def get(self):
        content = PostGIS().getDict("SELECT iso3, original_n FROM marxan.gaul_2015_simplified_1km where original_n not like '%|%' and iso3 not like '%|%' order by 2;")
        self.send_response({'records': content})        

#https://db-server-blishten.c9users.io:8081/marxan-server/getPlanningUnitGrids?callback=__jp0
class getPlanningUnitGrids(MarxanRESTHandler):
    def get(self):
        content = PostGIS().getDict("SELECT feature_class_name ,alias ,description ,creation_date::text ,country_id ,aoi_id,domain,_area,ST_AsText(envelope) envelope FROM marxan.metadata_planning_units order by 1;")
        self.send_response({'info': 'Planning unit grids retrieved', 'planning_unit_grids': content})        
        
#https://db-server-blishten.c9users.io:8081/marxan-server/createPlanningUnitGrid?iso3=AND&domain=Terrestrial&areakm2=50&callback=__jp10        
class createPlanningUnitGrid(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['iso3','domain','areakm2'])    
        #create the new planning unit and get the first row back
        data = PostGIS().execute("SELECT * FROM marxan.hexagons(%s,%s,%s);", [self.get_argument('areakm2'), self.get_argument('iso3'), self.get_argument('domain')], "One")
        #set the response
        self.send_response({'info':'Planning unit grid created', 'planning_unit_grid': data[0]})

#https://db-server-blishten.c9users.io:8081/marxan-server/deletePlanningUnitGrid?planning_grid_name=pu_sample&callback=__jp10        
class deletePlanningUnitGrid(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['planning_grid_name'])    
        #delete the new planning unit record from the metadata_planning_units table
        PostGIS().execute("DELETE FROM marxan.metadata_planning_units WHERE feature_class_name = %s;", [self.get_argument('planning_grid_name')])
        #delete the feature class
        PostGIS().execute(sql.SQL("DROP TABLE marxan.{};").format(sql.Identifier(self.get_argument('planning_grid_name'))))
        #set the response
        self.send_response({'info':'Planning unit grid deleted'})

#validates a user with the passed credentials
#https://db-server-blishten.c9users.io:8081/marxan-server/validateUser?user=andrew&password=thargal88&callback=__jp2
class validateUser(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','password'])   
        try:
            #get the user data from the user.dat file
            _getUserData(self)
        except:
            raise MarxanServicesError("Invalid login")
        #compare the passed password to the one in the user.dat file
        if self.get_argument("password") == self.userData["PASSWORD"]:
            #set a response cookie for the authenticated user
            self.set_secure_cookie("user", self.get_argument("user"), httponly = True) 
            #set a response cookie for the authenticated users role
            self.set_secure_cookie("role", self.userData["ROLE"], httponly = True)
            #set the response
            self.send_response({'info': "User " + self.user + " validated"})
        else:
            #invalid login
            raise MarxanServicesError("Invalid login")    

#gets a users information from the user folder
#curl 'https://db-server-blishten.c9users.io:8081/marxan-server/getUser?user=andrew&callback=__jp1' -H 'If-None-Match: "0798406453417c47c0b5ab5bd11d56a60fb4df7d"' -H 'Accept-Encoding: gzip, deflate, br' -H 'Accept-Language: en-US,en;q=0.9,fr;q=0.8' -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36' -H 'Accept: */*' -H 'Referer: https://marxan-client-blishten.c9users.io:8081/' -H 'Cookie: c9.live.user.jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjE2MzQxNDgiLCJuYW1lIjoiYmxpc2h0ZW4iLCJjb2RlIjoiOWNBUzdEQldsdWYwU2oyU01ZaEYiLCJpYXQiOjE1NDgxNDg0MTQsImV4cCI6MTU0ODIzNDgxNH0.yJ9mPz4bM7L3htL8vXVFMCcQpTO0pkRvhNHJP9WnJo8; c9.live.user.sso=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjE2MzQxNDgiLCJuYW1lIjoiYmxpc2h0ZW4iLCJpYXQiOjE1NDgxNDg0MTQsImV4cCI6MTU0ODIzNDgxNH0.ifW5qlkpC19iyMNBgZLtGZzxuMRyHKWldGg3He-__gI; role="2|1:0|10:1548151226|4:role|8:QWRtaW4=|d703b0f18c81cf22c85f41c536f99589ce11492925d85833e78d3d66f4d7fd62"; user="2|1:0|10:1548151226|4:user|8:YW5kcmV3|e5ed3b87979273b1b8d1b8983310280507941fe05fb665847e7dd5dacf36348d"' -H 'Connection: keep-alive' --compressed
class getUser(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user'])    
        #get the user data from the user.dat file
        _getUserData(self)
        #get the permissions for the users role
        role = self.userData["ROLE"]
        unauthorised = ROLE_UNAUTHORISED_METHODS[role]
        #set the response
        self.send_response({'info': "User data received", "userData" : {k: v for k, v in self.userData.iteritems() if k != 'PASSWORD'}, "unauthorisedMethods": unauthorised})

#gets a list of all users
#https://db-server-blishten.c9users.io:8081/marxan-server/getUsers
class getUsers(MarxanRESTHandler):
    def get(self):
        #get the users
        users = _getUsers()
        #set the response
        self.send_response({'info': users})

#gets project information from the input.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getProject?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getProject(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project']) 
        #if the guest user is getting a project there will be none
        if (self.current_user == "guest"):
            self.send_response({'error': 'Logged in as a read-only user'})
        else:
            #if the project name is an empty string, then get the first project for the user
            if (self.get_argument("project") == ""):
                _getProjects(self)
                project = self.projects[0]['name']
                #set the project argument
                self.request.arguments['project'] = [project]
                #and set the paths to this project
                _setFolderPaths(self, self.request.arguments)
            #get the project data from the input.dat file
            _getProjectData(self)
            #get the species data from the spec.dat file and the PostGIS database
            _getSpeciesData(self)
            #get all species data from the PostGIS database
            _getAllSpeciesData(self)
            #get the species preprocessing from the feature_preprocessing.dat file
            _getSpeciesPreProcessingData(self)
            #get the planning units information
            _getPlanningUnitsData(self)
            #get the protected area intersections
            _getProtectedAreaIntersectionsData(self)
            #set the project as the users last project so it will load on login
            _updateParameters(self.folder_user + USER_DATA_FILENAME, {'LASTPROJECT': self.get_argument("project")})
            #set the response
            self.send_response({'project': self.projectData["project"], 'metadata': self.projectData["metadata"], 'files': self.projectData["files"], 'runParameters': self.projectData["runParameters"], 'renderer': self.projectData["renderer"], 'features': self.speciesData.to_dict(orient="records"), 'allFeatures': self.allSpeciesData.to_dict(orient="records"), 'feature_preprocessing': self.speciesPreProcessingData.to_dict(orient="split")["data"], 'planning_units': self.planningUnitsData, 'protected_area_intersections': self.protectedAreaIntersectionsData})

#gets feature information from postgis
#https://db-server-blishten.c9users.io:8081/marxan-server/getFeature?oid=63407942&callback=__jp2
class getFeature(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['oid'])    
        #get the data
        _getFeature(self, self.get_argument("oid"))
        #set the response
        self.send_response({"data": self.data.to_dict(orient="records")})

#gets the features planning unit ids from the puvspr.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getFeaturePlanningUnits?user=andrew&project=Tonga%20marine%2030Km2&oid=63407942&callback=__jp2
class getFeaturePlanningUnits(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','oid'])    
        #get the data from the puvspr.dat file as a dataframe
        df = _loadCSV(self.folder_input + PUVSPR_FILENAME)
        #get the planning unit ids as a list
        puids = df.loc[df['species'] == int(self.get_argument("oid"))]['pu'].tolist()
        #set the response
        self.send_response({"data": puids})

#gets species information for a specific project from the spec.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getSpeciesData?user=andrew&project=Tonga%20marine%2030Km2&callback=__jp3
class getSpeciesData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the species data from the spec.dat file and PostGIS
        _getSpeciesData(self)
        #set the response
        self.send_response({"data": self.speciesData.to_dict(orient="records")})

#gets all species information from the PostGIS database
#https://db-server-blishten.c9users.io:8081/marxan-server/getAllSpeciesData?callback=__jp2
class getAllSpeciesData(MarxanRESTHandler):
    def get(self):
        #get all the species data
        _getAllSpeciesData(self)
        #set the response
        self.send_response({"data": self.allSpeciesData.to_dict(orient="records")})

#gets the species preprocessing information from the feature_preprocessing.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getSpeciesPreProcessingData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getSpeciesPreProcessingData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the species preprocessing data
        _getSpeciesPreProcessingData(self)
        #set the response
        self.send_response({"data": self.speciesPreProcessingData.to_dict(orient="split")["data"]})

#gets the planning units information from the pu.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getPlanningUnitsData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getPlanningUnitsData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the planning units information
        _getPlanningUnitsData(self)
        #set the response
        self.send_response({"data": self.planningUnitsData})

#gets the intersections of the planning units with the protected areas from the protected_area_intersections.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getProtectedAreaIntersectionsData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getProtectedAreaIntersectionsData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the protected area intersections
        _getProtectedAreaIntersectionsData(self)
        #set the response
        self.send_response({"data": self.protectedAreaIntersectionsData})

#gets the Marxan log for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getMarxanLog?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getMarxanLog(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the log
        _getMarxanLog(self)
        #set the response
        self.send_response({"log": self.marxanLog})

#gets the best solution for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getBestSolution?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getBestSolution(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the best solution
        _getBestSolution(self)
        #set the response
        self.send_response({"data": self.bestSolution.to_dict(orient="split")["data"]})

#gets the output summary for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getOutputSummary?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getOutputSummary(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the output sum
        _getOutputSummary(self)
        #set the response
        self.send_response({"data": self.outputSummary.to_dict(orient="split")["data"]})

#gets the summed solution for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getSummedSolution?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getSummedSolution(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the summed solution
        _getSummedSolution(self)
        #set the response
        self.send_response({"data": self.summedSolution})

#gets an individual solution
#https://db-server-blishten.c9users.io:8081/marxan-server/getSolution?user=andrew&project=Tonga%20marine%2030km2&solution=1&callback=__jp7
class getSolution(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','solution'])  
        #get the solution
        _getSolution(self, self.get_argument("solution"))
        #get the corresponding missing values file, e.g. output_mv00031.txt
        _getMissingValues(self, self.get_argument("solution"))
        #set the response
        self.send_response({'solution': self.solution, 'mv': self.missingValues, 'user': self.get_argument("user"), 'project': self.get_argument("project")})
 
#gets the missing values for a single solution
#https://db-server-blishten.c9users.io:8081/marxan-server/getMissingValues?user=andrew&project=Tonga%20marine%2030km2&solution=1&callback=__jp7
class getMissingValues(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','solution'])  
        #get the missing values file, e.g. output_mv00031.txt
        _getMissingValues(self, self.get_argument("solution"))
        #set the response
        self.send_response({'missingValues': self.missingValues})
 
#gets the combined results for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getResults?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getResults(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the log
        _getMarxanLog(self)
        #get the best solution
        _getBestSolution(self)
        #get the output sum
        _getOutputSummary(self)
        #get the summed solution
        _getSummedSolution(self)
        #set the response
        self.send_response({'info':'Results loaded', 'log': self.marxanLog, 'mvbest': self.bestSolution.to_dict(orient="split")["data"], 'summary':self.outputSummary.to_dict(orient="split")["data"], 'ssoln': self.summedSolution})

#gets a list of projects for the user
#https://db-server-blishten.c9users.io:8081/marxan-server/getProjects?user=andrew&callback=__jp2
class getProjects(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user'])    
        #get the projects
        _getProjects(self)
        #set the response
        self.send_response({"projects": self.projects})

#updates the spec.dat file with the posted data
class updateSpecFile(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','interest_features','spf_values','target_values'])    
        #update the spec.dat file and other related files 
        _updateSpeciesFile(self, self.get_argument("interest_features"), self.get_argument("target_values"), self.get_argument("spf_values"))
        #set the response
        self.send_response({'info': "spec.dat file updated"})

#updates the pu.dat file with the posted data
class updatePUFile(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project']) 
        #get the ids for the different statuses
        status1_ids = _getIntArrayFromArg(self.request.arguments, "status1")
        status2_ids = _getIntArrayFromArg(self.request.arguments, "status2")
        status3_ids = _getIntArrayFromArg(self.request.arguments, "status3")
        #update the file 
        _updatePuFile(self, status1_ids, status2_ids, status3_ids)
        #set the response
        self.send_response({'info': "pu.dat file updated"})

#used to populate the feature_preprocessing.dat file from an imported puvspr.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/createFeaturePreprocessingFileFromImport?user=andrew&project=test&callback=__jp2
class createFeaturePreprocessingFileFromImport(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project']) 
        #run the internal routine
        _createFeaturePreprocessingFileFromImport(self)
        #set the response
        self.send_response({'info': "feature_preprocessing.dat file populated"})

#updates parameters in the users user.dat file       
#POST ONLY
class updateUserParameters(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user'])  
        #get the parameters to update as a simple dict
        params = _getSimpleArguments(self.request.arguments, ['user','callback'])
        #update the parameters
        _updateParameters(self.folder_user + USER_DATA_FILENAME, params)
        #set the response
        self.send_response({'info': ",".join(params.keys()) + " parameters updated"})

#updates parameters in the projects input.dat file       
#POST ONLY
class updateProjectParameters(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])  
        #get the parameters to update as a simple dict
        params = _getSimpleArguments(self.request.arguments, ['user','project','callback'])
        #update the parameters
        _updateParameters(self.folder_project + PROJECT_DATA_FILENAME, params)
        #set the response
        self.send_response({'info': ",".join(params.keys()) + " parameters updated"})
        
#uploads a feature class with the passed feature class name to MapBox as a tileset using the MapBox Uploads API
#https://db-server-blishten.c9users.io:8081/marxan-server/uploadTilesetToMapBox?feature_class_name=pu_ton_marine_hexagons_20&mapbox_layer_name=hexagons&callback=__jp9
class uploadTilesetToMapBox(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['feature_class_name','mapbox_layer_name'])  
        uploadId = _uploadTilesetToMapbox(self.get_argument('feature_class_name'),self.get_argument('mapbox_layer_name'))
        #set the response for uploading to mapbox
        self.send_response({'info': "Tileset '" + self.get_argument('feature_class_name') + "' uploading",'uploadid': uploadId})
            
#uploads a shapefile to the marxan root folder
#POST ONLY 
class uploadShapefile(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['filename','name','description'])   
        #write the file to the server
        _writeFile(MARXAN_FOLDER + self.get_argument('filename'), self.request.files['value'][0].body)
        #set the response
        self.send_response({'info': "File '" + self.get_argument('filename') + "' uploaded", 'file': self.get_argument('filename')})
        
#saves an uploaded file to the filename - 3 input parameters: user, project, filename (relative) and the file itself as a request file
#POST ONLY 
class uploadFile(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project','filename'])   
        #write the file to the server
        _writeFile(self.folder_project + self.get_argument('filename'), self.request.files['value'][0].body)
        #set the response
        self.send_response({'info': "File '" + self.get_argument('filename') + "' uploaded", 'file': self.get_argument('filename')})
            
#imports a shapefile which has been uploaded to the marxan root folder into PostGIS as a new feature dataset
#https://db-server-blishten.c9users.io:8081/marxan-server/importFeature?filename=netafu.zip&name=Netafu%20island%20habitat&description=Digitised%20in%20ArcGIS%20Pro&callback=__jp5
class importFeature(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['filename','name','description'])   
        #import the shapefile
        id = _importFeature(self.get_argument('filename'), self.get_argument('name'), self.get_argument('description'))
        #set the response
        self.send_response({'info': "File '" + self.get_argument('filename') + "' imported", 'file': self.get_argument('filename'), 'id': id})

#imports a zipped planning unit shapefile which has been uploaded to the marxan root folder into PostGIS as a planning unit grid feature class
#https://db-server-blishten.c9users.io:8081/marxan-server/importPlanningUnitGrid?filename=pu_sample.zip&name=pu_test&description=wibble&callback=__jp5
class importPlanningUnitGrid(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['filename','name','description'])   
        #import the shapefile
        data = _importPlanningUnitGrid(self.get_argument('filename'), self.get_argument('name'), self.get_argument('description'))
        #set the response
        self.send_response({'info': "File '" + self.get_argument('filename') + "' imported", 'feature_class_name': data['feature_class_name'], 'uploadId': data['uploadId']})

#kills a running marxan job
#https://db-server-blishten.c9users.io:8081/marxan-server/stopMarxan?pid=12345&callback=__jp5
class stopMarxan(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['pid'])   
        try:
            os.kill(int(self.get_argument('pid')), signal.SIGTERM)
        except OSError:
            raise MarxanServicesError("The PID does not exist")
        else:
            self.send_response({'info': "PID '" + self.get_argument('pid') + "' terminated"})
            
#for testing role access to servivces            
#https://db-server-blishten.c9users.io:8081/marxan-server/testRoleAuthorisation&callback=__jp5
class testRoleAuthorisation(MarxanRESTHandler):
    def get(self):
        self.send_response({'info': "Service successful"})

####################################################################################################################################################################################################################################################################
## baseclass for handling WebSockets
####################################################################################################################################################################################################################################################################

class MarxanWebSocketHandler(tornado.websocket.WebSocketHandler):
    #get the current user
    def get_current_user(self):
        return self.get_secure_cookie("user")

    #check CORS access for the websocket
    def check_origin(self, origin):
        if DISABLE_SECURITY:
            return True
        #check the origin is in the permitted origins - the Origin header will not end in a forward slash
        if origin + "/" in PERMITTED_DOMAINS:
            return True
        else:
            raise HTTPError(403, "The origin '" + origin + "' does not have permission to access the service (CORS error)", reason = "The origin '" + origin + "' does not have permission to access the service (CORS error)")

    #called when the websocket is opened - does authentication/authorisation then gets the folder paths for the user and optionally the project
    def open(self):
        #set the start time of the websocket
        self.startTime = datetime.datetime.now()
        #set the folder paths for the user and optionally project
        _setFolderPaths(self, self.request.arguments)
        #check the request is authenticated
        _authenticate(self)
        #get the requested method
        method = _getRESTMethod(self.request.path)
        #check the users role has access to the requested service
        _authoriseRole(self, method)
        #check the user has access to the specific resource, i.e. the 'User' role cannot access projects from other users
        _authoriseUser(self)

    #sends the message with a timestamp
    def send_response(self, message):
        if self.startTime: 
            elapsedtime = str((datetime.datetime.now() - self.startTime).seconds) + " seconds"
            message.update({'elapsedtime': elapsedtime})
        self.write_message(message)

####################################################################################################################################################################################################################################################################
## MarxanWebSocketHandler subclasses
####################################################################################################################################################################################################################################################################

#wss://db-server-blishten.c9users.io:8081/marxan-server/runMarxan?user=andrew&project=Tonga%20marine%2030km2
#starts a Marxan run on the server and streams back the output as websockets
class runMarxan(MarxanWebSocketHandler):
    #authenticate and get the user folder and project folders
    def open(self):
        try:
            super(runMarxan, self).open()
        except (HTTPError) as e:
            self.send_response({'error': e.reason, 'status': 'Finished'})
        else:
            self.send_response({'info': "Running Marxan", 'status':'Started'})
            #set the current folder to the project folder so files can be found in the input.dat file
            if (os.path.exists(self.folder_project)):
                os.chdir(self.folder_project)
                #delete all of the current output files
                _deleteAllFiles(self.folder_output)
                #run marxan - the Subprocess.STREAM option does not work on Windows - see here: https://www.tornadoweb.org/en/stable/process.html?highlight=Subprocess#tornado.process.Subprocess
                #the "exec " in front allows you to get the pid of the child process, i.e. marxan, and therefore to be able to kill the process using os.kill(pid, signal.SIGTERM) instead of the tornado process - see here: https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true/4791612#4791612
                self.app = Subprocess(["exec " + MARXAN_EXECUTABLE], stdout=Subprocess.STREAM, stdin=subprocess.PIPE, shell=True)
                #return the pid so that the process can be stopped
                self.send_response({'pid': self.app.pid, 'status':'pid'})
                IOLoop.current().spawn_callback(self.stream_output)
                self.app.stdin.write('\n') # to end the marxan process by sending ENTER to the stdin
            else:
                self.send_response({'error': "Project '" + self.get_argument("project") + "' does not exist", 'status': 'Finished', 'project': self.get_argument("project"), 'user': self.get_argument("user")})
                #close the websocket
                self.close()

    @gen.coroutine
    def stream_output(self):
        try:
            while True:
                # line = yield self.app.stdout.read_bytes(4096)
                line = yield self.app.stdout.read_bytes(4096, partial=True)
                self.send_response({'info':line, 'status':'Running'})
        except StreamClosedError: #fired when the stream closes
            self.send_response({'info': 'Run completed', 'status': 'Finished', 'project': self.get_argument("project"), 'user': self.get_argument("user")})
            #close the websocket
            self.close()

####################################################################################################################################################################################################################################################################
## baseclass for handling long-running PostGIS queries using WebSockets
####################################################################################################################################################################################################################################################################

class QueryWebSocketHandler(MarxanWebSocketHandler):
    
    #authenticate and get the user folder and project folders
    def open(self):
        super(QueryWebSocketHandler, self).open()

    #required for asyncronous queries
    def wait(self):
        while 1:
            state = self.conn.poll()
            if state == psycopg2.extensions.POLL_OK:      #0
                break
            elif state == psycopg2.extensions.POLL_WRITE: #2
                select.select([], [self.conn.fileno()], [])
            elif state == psycopg2.extensions.POLL_READ:  #1
                select.select([self.conn.fileno()], [], [])
            else:
                raise psycopg2.OperationalError("poll() returned %s" % state)
                
    @gen.coroutine
    #runs a PostGIS query asynchronously, i.e. non-blocking
    def executeQueryAsynchronously(self, sql, data = None, startedMessage = "", processingMessage = "", finishingMessage = ""):
        try:
            self.send_response({'info': startedMessage, 'status':'Started'})
            #connect to postgis asyncronously
            self.conn = psycopg2.connect(CONNECTION_STRING, async = True)
            #wait for the connection to be ready
            self.wait()
            #get a cursor
            cur = self.conn.cursor()
            #parameter bind if necessary
            if data is not None:
                sql = cur.mogrify(sql, data)
            #execute the query
            cur.execute(sql)
            #poll to get the state of the query
            state = self.conn.poll()
            #poll at regular intervals to see if the query has finished
            while (state != psycopg2.extensions.POLL_OK):
                yield gen.sleep(1)
                state = self.conn.poll()
                self.send_response({'info': processingMessage, 'status':'Running'})
            #if the query returns data, then return the data
            if cur.description is not None:
                #get the column names for the query
                columns = [desc[0] for desc in cur.description]
                #get the query results
                records = cur.fetchall()
                #set the values on the current object
                self.queryResults = {}
                self.queryResults.update({'columns': columns, 'records': records})

        #handle any issues with the query syntax
        except (psycopg2.Error) as e:
            self.send_response({'error': e.pgerror, 'status':'Running'})
        #clean up code
        finally:
            cur.close()
            self.conn.close()
            self.send_response({'info': finishingMessage, 'status':'Finishing'})

####################################################################################################################################################################################################################################################################
## WebSocket subclasses
####################################################################################################################################################################################################################################################################

#preprocesses the features by intersecting them with the planning units
#wss://db-server-blishten.c9users.io:8081/marxan-server/preprocessFeature?user=andrew&project=Tonga%20marine%2030km2&planning_grid_name=pu_ton_marine_hexagons_30&feature_class_name=volcano&alias=volcano&id=63408475
class preprocessFeature(QueryWebSocketHandler):

    #run the preprocessing
    def open(self):
        try:
            super(preprocessFeature, self).open()
        except (HTTPError) as e:
            self.send_response({'error': e.reason, 'status': 'Finished'})
        else:
            _validateArguments(self.request.arguments, ['user','project','id','feature_class_name','alias','planning_grid_name'])    
            #get the project data
            _getProjectData(self)
            if (not self.projectData["metadata"]["OLDVERSION"]):
                #new version of marxan - do the intersection
                future = self.executeQueryAsynchronously("SELECT * FROM marxan.get_pu_areas_for_interest_feature(%s,%s);", [self.get_argument('planning_grid_name'),self.get_argument('feature_class_name')], "Preprocessing '" + self.get_argument('alias') + "'", "  Preprocessing..", "Finishing preprocessing")
                future.add_done_callback(self.intersectionComplete)
            else:
                #pass None as the Future object to the callback for the old version of marxan
                self.intersectionComplete(None) 

    #callback which is called when the intersection has been done
    def intersectionComplete(self, future):
        #get an empty dataframe 
        d = {'amount':pandas.Series([], dtype='float64'), 'species':pandas.Series([], dtype='int64'), 'pu':pandas.Series([], dtype='int64')}
        emptyDataFrame = pandas.DataFrame(data=d)[['species', 'pu', 'amount']] #reorder the columns
        #get the intersection data
        if (future): #i.e. new version of marxan
            #get the intersection data as a dataframe from the queryresults - TODO - this needs to be rewritten to be scalable - getting the records in this way fails when you have > 1000 records and you need to use a method that creates a tmp table - see preprocessPlanningUnits
            intersectionData = pandas.DataFrame.from_records(self.queryResults["records"], columns = self.queryResults["columns"])
        else:
            #old version of marxan so an empty dataframe
            intersectionData = emptyDataFrame
        #get the existing data
        try:
            #load the existing preprocessing data
            df = _getProjectInputData(self, "PUVSPRNAME", True)
        except:
            #no existing preprocessing data so use the empty data frame
            df = emptyDataFrame
        #get the species id from the arguments
        speciesId = int(self.get_argument('id'))
        #make sure there are not existing records for this feature - otherwise we will get duplicates
        df = df[~df.species.isin([speciesId])]
        #append the intersection data to the existing data
        df = df.append(intersectionData)
        #sort the values by the species column then pu column
        df = df.sort_values(by=['species','pu'])
        try: 
            #write the data to the PUVSPR.dat file
            _writeCSV(self, "PUVSPRNAME", df)
            #get the summary information and write it to the feature preprocessing file
            record = _getPuvsprStats(df, speciesId)
            _writeToDatFile(self.folder_input + FEATURE_PREPROCESSING_FILENAME, record)
        except (MarxanServicesError) as e:
            self.send_response({'error': e.message, 'status':'Finished'})
        #update the input.dat file
        _updateParameters(self.folder_project + PROJECT_DATA_FILENAME, {'PUVSPRNAME': PUVSPR_FILENAME})
        #set the response
        self.send_response({'info': "Feature '" + self.get_argument('alias') + "' preprocessed", "feature_class_name": self.get_argument('feature_class_name'), "pu_area" : str(record.iloc[0]['pu_area']),"pu_count" : str(record.iloc[0]['pu_count']), "id":str(speciesId), 'status':'Finished'})
        #close the websocket
        self.close()

#preprocesses the protected areas by intersecting them with the planning units
#wss://db-server-blishten.c9users.io:8081/marxan-server/preprocessProtectedAreas?user=andrew&project=Tonga%20marine%2030km2&planning_grid_name=pu_ton_marine_hexagons_30
class preprocessProtectedAreas(QueryWebSocketHandler):

    #run the preprocessing
    def open(self):
        try:
            super(preprocessProtectedAreas, self).open()
        except (HTTPError) as e:
            self.send_response({'error': e.reason, 'status': 'Finished'})
        else:
            _validateArguments(self.request.arguments, ['user','project','planning_grid_name'])    
            #get the project data
            _getProjectData(self)
            #do the intersection with the protected areas
            future = self.executeQueryAsynchronously(sql.SQL("SELECT DISTINCT iucn_cat, grid.puid FROM (SELECT iucn_cat, geom FROM marxan.wdpa) AS wdpa, marxan.{} grid WHERE ST_Intersects(wdpa.geom, ST_Transform(grid.geometry, 4326)) ORDER BY 1,2;").format(sql.Identifier(self.get_argument('planning_grid_name'))), None, "Preprocessing protected areas", "  Preprocessing protected areas..", "Finishing preprocessing")
            future.add_done_callback(self.preprocessProtectedAreasComplete)
    
    #callback which is called when the intersection has been done
    def preprocessProtectedAreasComplete(self, future):
        if hasattr(self, "queryResults"):
            #get the intersection data as a dataframe from the queryresults
            df = pandas.DataFrame.from_records(self.queryResults["records"], columns = self.queryResults["columns"])
            #write the intersections to file
            df.to_csv(self.folder_input + PROTECTED_AREA_INTERSECTIONS_FILENAME, index =False)
        #get the data
        _getProtectedAreaIntersectionsData(self)
        #set the response
        self.send_response({'info': self.protectedAreaIntersectionsData, 'status':'Finished'})
    
#preprocesses the planning units to get the boundary lengths where they intersect
#wss://db-server-blishten.c9users.io:8081/marxan-server/preprocessPlanningUnits?user=andrew&project=Tonga%20marine%2030km2
class preprocessPlanningUnits(QueryWebSocketHandler):

    #run the preprocessing
    def open(self):
        try:
            super(preprocessPlanningUnits, self).open()
        except (HTTPError) as e:
            self.send_response({'error': e.reason, 'status': 'Finished'})
        else:
            _validateArguments(self.request.arguments, ['user','project'])    
            #get the project data
            _getProjectData(self)
            if (not self.projectData["metadata"]["OLDVERSION"]):
                #new version of marxan - get the boundary lengths
                PostGIS().execute("DROP TABLE IF EXISTS marxan.tmp;") 
                future = self.executeQueryAsynchronously(sql.SQL("CREATE TABLE marxan.tmp AS SELECT DISTINCT a.puid id1, b.puid id2, ST_Length(ST_CollectionExtract(ST_Intersection(a.geometry, b.geometry), 2))/1000 boundary  FROM marxan.{0} a, marxan.{0} b  WHERE a.puid < b.puid AND ST_Touches(a.geometry, b.geometry);").format(sql.Identifier(self.projectData["metadata"]["PLANNING_UNIT_NAME"])), None, "Getting boundary lengths", "  Processing ..", "Finishing preprocessing")
                future.add_done_callback(self.preprocessPlanningUnitsComplete)
            else:
                #pass None as the Future object to the callback for the old version of marxan
                self.preprocessPlanningUnitsComplete(None) 
    
    #callback which is called when the boundary lengths have been calculated
    def preprocessPlanningUnitsComplete(self, future):
        try:
            if (future): #i.e. new version of marxan
                #delete the file if it already exists
                if (os.path.exists(self.folder_input + BOUNDARY_LENGTH_FILENAME)):
                    os.remove(self.folder_input + BOUNDARY_LENGTH_FILENAME)
                #write the boundary lengths to file
                postgis = PostGIS()
                postgis.executeToText("COPY (SELECT * FROM marxan.tmp) TO STDOUT WITH CSV HEADER;", self.folder_input + BOUNDARY_LENGTH_FILENAME)
                #delete the tmp table
                postgis.execute("DROP TABLE IF EXISTS marxan.tmp;") 
                #update the input.dat file
                _updateParameters(self.folder_project + PROJECT_DATA_FILENAME, {'BOUNDNAME': 'bounds.dat'})
                #set the response
                self.send_response({'info': 'Boundary lengths calculated', 'status':'Finished'})
        except Exception as e:
            print e.message

####################################################################################################################################################################################################################################################################
## tornado functions
####################################################################################################################################################################################################################################################################

def make_app():
    return tornado.web.Application([
        ("/marxan-server/getProjects", getProjects),
        ("/marxan-server/getProject", getProject),
        ("/marxan-server/createProject", createProject),
        ("/marxan-server/createImportProject", createImportProject),
        ("/marxan-server/upgradeProject", upgradeProject),
        ("/marxan-server/deleteProject", deleteProject),
        ("/marxan-server/cloneProject", cloneProject),
        ("/marxan-server/createProjectGroup", createProjectGroup),
        ("/marxan-server/deleteProjects", deleteProjects),
        ("/marxan-server/renameProject", renameProject),
        ("/marxan-server/updateProjectParameters", updateProjectParameters),
        ("/marxan-server/getCountries", getCountries),
        ("/marxan-server/getPlanningUnitGrids", getPlanningUnitGrids),
        ("/marxan-server/createPlanningUnitGrid", createPlanningUnitGrid),
        ("/marxan-server/deletePlanningUnitGrid", deletePlanningUnitGrid),
        ("/marxan-server/uploadTilesetToMapBox", uploadTilesetToMapBox),
        ("/marxan-server/uploadShapefile", uploadShapefile),
        ("/marxan-server/uploadFile", uploadFile),
        ("/marxan-server/importPlanningUnitGrid", importPlanningUnitGrid),
        ("/marxan-server/createFeaturePreprocessingFileFromImport", createFeaturePreprocessingFileFromImport),
        ("/marxan-server/createUser", createUser),
        ("/marxan-server/validateUser", validateUser),
        ("/marxan-server/getUser", getUser),
        ("/marxan-server/getUsers", getUsers),
        ("/marxan-server/updateUserParameters", updateUserParameters),
        ("/marxan-server/getFeature", getFeature),
        ("/marxan-server/importFeature", importFeature),
        ("/marxan-server/getFeaturePlanningUnits", getFeaturePlanningUnits),
        ("/marxan-server/getPlanningUnitsData", getPlanningUnitsData), #currently not used
        ("/marxan-server/updatePUFile", updatePUFile),
        ("/marxan-server/getSpeciesData", getSpeciesData), #currently not used
        ("/marxan-server/getAllSpeciesData", getAllSpeciesData), #currently not used
        ("/marxan-server/getSpeciesPreProcessingData", getSpeciesPreProcessingData), #currently not used
        ("/marxan-server/updateSpecFile", updateSpecFile),
        ("/marxan-server/getProtectedAreaIntersectionsData", getProtectedAreaIntersectionsData), #currently not used
        ("/marxan-server/getMarxanLog", getMarxanLog), #currently not used - bugs in the Marxan output log
        ("/marxan-server/getBestSolution", getBestSolution), #currently not used
        ("/marxan-server/getOutputSummary", getOutputSummary), #currently not used
        ("/marxan-server/getSummedSolution", getSummedSolution), #currently not used
        ("/marxan-server/getResults", getResults),
        ("/marxan-server/getSolution", getSolution),
        ("/marxan-server/getMissingValues", getMissingValues), #currently not used
        ("/marxan-server/preprocessFeature", preprocessFeature),
        ("/marxan-server/preprocessPlanningUnits", preprocessPlanningUnits),
        ("/marxan-server/preprocessProtectedAreas", preprocessProtectedAreas),
        ("/marxan-server/runMarxan", runMarxan),
        ("/marxan-server/stopMarxan", stopMarxan),
        ("/marxan-server/testRoleAuthorisation", testRoleAuthorisation)
    ], cookie_secret=COOKIE_RANDOM_VALUE)

if __name__ == "__main__":
    try:
        #turn on tornado logging 
        tornado.options.parse_command_line() 
        # create an instance of tornado formatter
        my_log_formatter = LogFormatter(fmt='%(color)s[%(levelname)1.1s %(asctime)s.%(msecs)03d]%(end_color)s %(message)s', datefmt='%d-%m-%y %H:%M:%S', color=True)
        # get the parent logger of all tornado loggers 
        root_logger = logging.getLogger()
        # set your format to root_logger
        root_streamhandler = root_logger.handlers[0]
        root_streamhandler.setFormatter(my_log_formatter)
        # logging.disable(logging.ERROR)
        #test for prerequisites
        if not os.path.exists(OGR2OGR_EXECUTABLE):
            raise MarxanServicesError("The path to the ogr2ogr executable '" + OGR2OGR_EXECUTABLE + "' could not be found")
        if not os.path.exists(MARXAN_EXECUTABLE):
            raise MarxanServicesError("The path to the Marxan executable '" + MARXAN_EXECUTABLE + "' could not be found")
        app = make_app()
        app.listen(8081, '0.0.0.0')
        tornado.ioloop.IOLoop.current().start()
    except Exception as e:
        print e.message