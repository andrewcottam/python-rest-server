from tornado.iostream import StreamClosedError
from tornado.process import Subprocess
from tornado.ioloop import IOLoop
from tornado import concurrent
from tornado import gen
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

####################################################################################################################################################################################################################################################################
## constant declarations
####################################################################################################################################################################################################################################################################
MARXAN_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/"
USER_DATA_FILENAME = "user.dat"
PROJECT_DATA_FILENAME = "input.dat"
OUTPUT_LOG_FILENAME = "output_log.dat"
BEST_SOLUTION_FILENAME = "output_mvbest.txt"
OUTPUT_SUM_FILENAME = "output_sum.txt"
SUMMED_SOLUTION_FILENAME = "output_ssoln.txt"
FEATURE_PREPROCESSING_FILENAME = "feature_preprocessing.dat"
PROTECTED_AREA_INTERSECTIONS_FILENAME = "protected_area_intersections.dat"
MARXAN_EXECUTABLE = MARXAN_FOLDER + "MarOpt_v243_Linux64"

####################################################################################################################################################################################################################################################################
## generic functions that dont belong to a class so can be called by subclasses of tornado.web.RequestHandler and tornado.websocket.WebSocketHandler equally - underscores are used so they dont mask the equivalent endpoints
####################################################################################################################################################################################################################################################################

#sets the various paths to the users folder and project folders using the request arguments in the passed object
def _setFolderPaths(obj):
    if "user" in obj.request.arguments.keys():
        user = obj.request.arguments["user"][0]
        obj.folder_user = MARXAN_FOLDER + user + os.sep
        if not os.path.exists(obj.folder_user):
            raise MarxanServicesError("The user folder '" + obj.folder_user +"' does not exist") 
        obj.user = user
        #get the project folder and the input and output folders
        if "project" in obj.request.arguments.keys():
            obj.folder_project = obj.folder_user + obj.request.arguments["project"][0] + os.sep
            if not os.path.exists(obj.folder_project):
                raise MarxanServicesError("The project folder '" + obj.folder_project +"' does not exist") 
            obj.folder_input =  obj.folder_project + "input" + os.sep
            obj.folder_output = obj.folder_project + "output" + os.sep
            obj.project = obj.get_argument("project")

#get the project data from the input.dat file - using the obj.folder_project path and creating an attribute called projectData in the obj for the return data
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
                conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
                df2 = pandas.read_sql_query("select * from marxan.get_planning_units_metadata('" + value + "')",con=conn)
                if (df2.shape[0] == 0):
                    metadataDict.update({'pu_alias': value,'pu_description': 'No description','pu_domain': 'Unknown domain','pu_area': 'Unknown area','pu_creation_date': 'Unknown date'})
                else:
                    #get the data from the metadata_planning_units table
                    metadataDict.update({'pu_alias': df2.iloc[0]['alias'],'pu_description': df2.iloc[0]['description'],'pu_domain': df2.iloc[0]['domain'],'pu_area': df2.iloc[0]['area'],'pu_creation_date': df2.iloc[0]['creation_date']})
                conn.close()
        elif k in ['CLASSIFICATION', 'NUMCLASSES','COLORCODE', 'TOPCLASSES','OPACITY']: # renderer section of the input.dat file
            key, value = _getKeyValue(s, k)
            rendererDict.update({key: value})
    #set the project data
    obj.projectData = {}
    obj.projectData.update({'project': obj.project, 'metadata': metadataDict, 'files': filesDict, 'runParameters': paramsArray, 'renderer': rendererDict})
    
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
    if obj.projectData["metadata"]["OLDVERSION"] == "True":
        #return the data from the spec.dat file with additional fields manually added
        output_df['tmp'] = 'Unique identifer: '
        output_df['alias'] = output_df['tmp'].str.cat((output_df['oid']).apply(str)) # returns: 'Unique identifer: 4702435'
        output_df['feature_class_name'] = output_df['oid']
        output_df['description'] = "No description"
        output_df['creation_date'] = "Unknown"
        output_df['area'] = -1
        output_df = output_df[["alias", "feature_class_name", "description", "creation_date", "area", "prop", "spf", "oid"]]
    else:
        #get the postgis feature data
        df2 = PostGIS().getDataFrame("select * from marxan.get_interest_features()")
        #join the species data to the PostGIS data
        output_df = output_df.join(df2.set_index("oid"))
    #rename the columns that are sent back to the client as the names of various properties are different in Marxan compared to the web client
    output_df = output_df.rename(index=str, columns={'prop': 'target_value', 'oid':'id'})    
    #get the target as an integer - Marxan has it as a percentage, i.e. convert 0.17 -> 17
    output_df['target_value'] = (output_df['target_value'] * 100).astype(int)
    obj.speciesData = output_df
        
#get all species information from the PostGIS database
def _getAllSpeciesData(obj):
    obj.allSpeciesData = PostGIS().getDataFrame("SELECT oid::integer as id, creation_date::text, feature_class_name, alias, _area area, description FROM marxan.metadata_interest_features order by alias;")

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

def _getOutputSum(obj):
    obj.outputSum = _loadCSV(obj.folder_output + OUTPUT_SUM_FILENAME)

def _getSummedSolution(obj):
    df = _loadCSV(obj.folder_output + SUMMED_SOLUTION_FILENAME)
    obj.summedSolution = _normaliseDataFrame(df, "number", "planning_unit")

#gets the projects for the current user
def _getProjects(obj):
    #get a list of folders underneath the users home folder
    project_folders = glob.glob(MARXAN_FOLDER + obj.user + os.sep + "*/")
    #sort the folders
    project_folders.sort()
    projects = []
    #iterate through the project folders and get the parameters for each project to return
    for dir in project_folders:
        #get the name of the folder 
        project = dir[:-1][dir[:-1].rfind("/")+1:]
        if (project[:2] != "__"): #folders beginning with __ are system folders
            #get the data from the input file for this project
            obj.project = project
            obj.folder_project = MARXAN_FOLDER + obj.user + os.sep + project + os.sep
            _getProjectData(obj)
            #create a dict to save the data
            projects.append({'name': project,'description': obj.projectData["metadata"]["DESCRIPTION"],'createdate': obj.projectData["metadata"]["CREATEDATE"],'oldVersion': obj.projectData["metadata"]["OLDVERSION"]})
    obj.projects = projects

#creates or updates the spec.dat file with the passed interest features
def _updateSpeciesFile(obj, interest_features, target_values, spf_values):
    #get the features to create/update as a list of integer ids
    ids = _txtIntsToList(interest_features)
    props = _txtIntsToList(target_values) 
    spfs = spf_values.split(",") 
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
        _deleteRecordsInTextFile(puvsprFilename, "species", removedIds, False)
        #update the preprocessing.dat file to remove any species that are no longer in the project - these will need to be preprocessed again
        _deleteRecordsInTextFile(obj.folder_input + FEATURE_PREPROCESSING_FILENAME, "id", removedIds, False)
    #create the dataframe to write to file
    records = []
    for i in range(len(ids)):
        if i not in removedIds:
            records.append({'id': str(ids[i]), 'prop': str(float(props[i])/100), 'spf': spfs[i]})
    df = pandas.DataFrame(records)
    #write the data to file
    _writeCSV(obj, "SPECNAME", df)

#gets the name of the input file from the projects input.dat file using the obj.folder_project path
def _getProjectInputFilename(obj, fileToGet):
    if not hasattr(obj, "projectData"):
        _getProjectData(obj)
    return obj.projectData["files"][fileToGet]

#gets the projects input data using the fileToGet, e.g. SPECNAME will return the data from the file corresponding to the input.dat file SPECNAME setting
def _getProjectInputData(obj, fileToGet, errorIfNotExists = False):
    filename = obj.folder_input + os.sep + _getProjectInputFilename(obj, fileToGet)
    return _loadCSV(filename, errorIfNotExists)
    
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

#saves the dataframe to a csv file specified by the fileToWrite, e.g. _writeCSV(self, "PUVSPRNAME", df) - this only applies to the files managed by Marxan in the input.dat file, e.g. SPEC, PU, PUVSPRNAME
def _writeCSV(obj, fileToWrite, df, writeIndex = False):
    _filename = _getProjectInputFilename(obj, fileToWrite)
    if _filename == "":
        raise MarxanServicesError("The filename for the " + fileToWrite + ".dat file has not been set in the input.dat file")
    df.to_csv(obj.folder_input + _filename, index = writeIndex)

#writes the dataframe to the file - for files not managed in the input.dat file
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
    
#gets a files contents as a string
def _readFile(filename):
    f = open(filename)
    s = f.read()
    f.close()
    return s

def _writeFile(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()
    
#deletes all of the files in the passed folder
def _deleteAllFiles(folder):
	files = glob.glob(folder + "*")
	for f in files:
		os.remove(f)

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
    return parameterName, value

#converts a data frame with duplicate values into a normalised array
def _normaliseDataFrame(df, columnToNormaliseBy, puidColumnName):
    #get the groups from the data
    groups = df.groupby(by = columnToNormaliseBy).groups
    #build the response, e.g. a normal data frame with repeated values in the columnToNormaliseBy -> [["VI", [7, 8, 9]], ["IV", [0, 1, 2, 3, 4]], ["V", [5, 6]]]
    response = [[g, df[puidColumnName][groups[g]].values.tolist()] for g in groups if g not in [0]]
    return response

#deletes the records in the text file that have id values that match the passed ids
def _deleteRecordsInTextFile(filename, id_columnname, ids, write_index):
    if (filename) and (os.path.exists(filename)):
        #if the file exists then get the existing data
        df = _loadCSV(filename)
        #remove the records with the matching ids
        df = df[~df[id_columnname].isin(ids)]
        #write the results back to the file
        df.to_csv(filename, index = write_index)

#converts a comma-separated set of integer values to a list of integers
def _txtIntsToList(txtInts):
    return [int(s) for s in txtInts.split(",")] 

#checks that all of the arguments in argumentList are in the arguments dictionary
def _validateArguments(arguments, argumentList):
    for argument in argumentList:
        if argument not in arguments.keys():
            raise MarxanServicesError("Missing input argument:" + argument)

####################################################################################################################################################################################################################################################################
## error classes
####################################################################################################################################################################################################################################################################

class MarxanServicesError(Exception):
    """Exception Class that allows the Marxan Services REST Server to raise custom exceptions"""
    pass

####################################################################################################################################################################################################################################################################
## class to return data from postgis
####################################################################################################################################################################################################################################################################

class PostGIS():
    def __init__(self):
        #get a connection to the database
        self.connection = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")

    def getDict(self, sql):
        df = pandas.read_sql_query(sql, self.connection)
        return df.to_dict(orient="records")
            
    def getDataFrame(self, sql):
        return pandas.read_sql_query(sql, self.connection)
            
    def __del__(self):
        self.connection.close()
    
####################################################################################################################################################################################################################################################################
## baseclass for handling REST requests
####################################################################################################################################################################################################################################################################

class MarxanRESTHandler(tornado.web.RequestHandler):
    #to prevent CORS errors in the client
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")

    #called before the request is processed 
    def prepare(self):
        try:
            #instantiate the response dictionary
            self.response = {}
            #set the folder paths for the user and optionally project
            _setFolderPaths(self)
        except (MarxanServicesError) as e:
            self.send_response({"error": repr(e)})
    
    #used by all descendent classes to write the return payload and send it
    def send_response(self, response):
        try:
            #set the return header as json
            self.set_header('Content-Type','application/json')
            #convert the response dictionary to json
            content = json.dumps(response)
        #sometimes the Marxan log causes json encoding issues
        except (UnicodeDecodeError) as e: 
            logging.error("UnicodeDecodeError")
            if 'log' in response.keys():
                response.update({"log": "Server warning: Unable to encode the Marxan log. <br/>" + repr(e), "warning": "Unable to encode the Marxan log"})
                content = json.dumps(response)        
        finally:
            if "callback" in self.request.arguments.keys():
                self.write(self.get_argument("callback") + "(" + content + ")")
            else:
                self.write(content)
    
    #uncaught exception handling that captures any exceptions in the descendent classes and writes them back to the client
    def write_error(self, status_code, **kwargs):
        if "exc_info" in kwargs:
            trace = ""
            for line in traceback.format_exception(*kwargs["exc_info"]):
                trace = trace + line
            lastLine = traceback.format_exception(*kwargs["exc_info"])[len(traceback.format_exception(*kwargs["exc_info"]))-1]
            self.set_status(200)
            self.send_response({"error":lastLine, "trace" : trace})
            self.finish()
    
####################################################################################################################################################################################################################################################################
## RequestHandler subclasses
####################################################################################################################################################################################################################################################################

#https://db-server-blishten.c9users.io:8081/marxan-server/getCountries?callback=__jp0
class getCountries(MarxanRESTHandler):
    def get(self):
        content = PostGIS().getDict("SELECT iso3, original_n FROM marxan.gaul_2015_simplified_1km where original_n not like '%|%' and iso3 not like '%|%' order by 2;")
        self.send_response({'records': content})        

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
            #set the response
            self.send_response({'info': "User " + self.user + " validated"})
        else:
            #invalid login
            raise MarxanServicesError("Invalid login")    

#gets a users information from the user folder
#https://db-server-blishten.c9users.io:8081/marxan-server/getUser?user=andrew&callback=__jp2
class getUser(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user'])    
        #get the user data from the user.dat file
        _getUserData(self)
        #set the response
        self.send_response({'info': "User data received", "userData" : {k: v for k, v in self.userData.iteritems() if k != 'PASSWORD'}})

#gets project information from the input.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getProject?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getProject(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
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
        #set the response
        self.send_response({'project': self.projectData["project"], 'metadata': self.projectData["metadata"], 'files': self.projectData["files"], 'runParameters': self.projectData["runParameters"], 'renderer': self.projectData["renderer"], 'features': self.speciesData.to_dict(orient="records"), 'allFeatures': self.allSpeciesData.to_dict(orient="records"), 'feature_preprocessing': self.speciesPreProcessingData.to_dict(orient="split")["data"], 'planning_units': self.planningUnitsData, 'protected_area_intersections': self.protectedAreaIntersectionsData})

#gets species information for a specific project from the spec.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getSpeciesData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
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

#gets the output sum for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getOutputSum?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getOutputSum(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        _validateArguments(self.request.arguments, ['user','project'])    
        #get the output sum
        _getOutputSum(self)
        #set the response
        self.send_response({"data": self.outputSum.to_dict(orient="split")["data"]})

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
        _getOutputSum(self)
        #get the summed solution
        _getSummedSolution(self)
        #set the response
        self.send_response({'info':'Results loaded', 'log': self.marxanLog, 'mvbest': self.bestSolution.to_dict(orient="split")["data"], 'sum':self.outputSum.to_dict(orient="split")["data"], 'ssoln': self.summedSolution})

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

####################################################################################################################################################################################################################################################################
## baseclass for handling WebSockets
####################################################################################################################################################################################################################################################################

class MarxanWebSocketHandler(tornado.websocket.WebSocketHandler):
    #to prevent CORS errors in the client
    def check_origin(self, origin):
        return True

    #gets the folder paths for the user and optionally the project
    def open(self):
        #set the folder paths for the user and optionally project
        _setFolderPaths(self)

    #sends the message with a timestamp
    def send_response(self, message):
        message.update({'timestamp': datetime.datetime.now().strftime("%H:%M:%S.%f on %d/%m/%Y")})
        self.write_message(message)

####################################################################################################################################################################################################################################################################
## baseclass for handling long-running PostGIS queries using WebSockets
####################################################################################################################################################################################################################################################################

class QueryWebSocketHandler(MarxanWebSocketHandler):
    
    #required for asyncronous queries
    def wait(self, conn):
        while 1:
            state = conn.poll()
            if state == psycopg2.extensions.POLL_OK:
                break
            elif state == psycopg2.extensions.POLL_WRITE:
                select.select([], [conn.fileno()], [])
            elif state == psycopg2.extensions.POLL_READ:
                select.select([conn.fileno()], [], [])
            else:
                raise psycopg2.OperationalError("poll() returned %s" % state)
                
    @gen.coroutine
    #runs a PostGIS query asynchronously, i.e. non-blocking
    def executeQueryAsynchronously(self, sql):
        try:
            self.send_response({'info': "Started PostGIS query"})
            #connect to postgis asyncronously
            conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'", async = True)
            #wait for the connection to be ready
            self.wait(conn)
            #get a cursor
            cur = conn.cursor()
            #execute the query
            cur.execute(sql)
            #poll to get the state of the query
            state = conn.poll()
            #poll at regular intervals to see if the query has finished
            while (state != psycopg2.extensions.POLL_OK):
                yield gen.sleep(1)
                state = conn.poll()
                self.send_response({'info': "Still processing"})
            #get the column names for the query
            columns = [desc[0] for desc in cur.description]
            #get the query results
            records = cur.fetchall()
            #set the values on the current object
            self.queryResults = {}
            self.queryResults.update({'columns': columns, 'records': records})
        #handle any issues with the query syntax
        except (psycopg2.Error) as e:
            self.send_response({'error': e.pgerror})
        #clean up code
        finally:
            cur.close()
            conn.close()
            self.send_response({'info': "Finished PostGIS query"})
            # self.close()

####################################################################################################################################################################################################################################################################
## WebSocket subclasses
####################################################################################################################################################################################################################################################################

#preprocesses the features by intersecting them with the planning units
#wss://db-server-blishten.c9users.io:8081/marxan-server/preprocessFeature?user=andrew&project=Tonga%20marine%2030km2&planning_grid_name=pu_ton_marine_hexagons_30&feature_class_name=volcano&id=63408475
class preprocessFeature(QueryWebSocketHandler):

    #run the preprocessing
    def open(self):
        #get the user folder and project folders
        super(preprocessFeature, self).open()
        try:
            _validateArguments(self.request.arguments, ['user','project','id','feature_class_name','planning_grid_name'])    
        except (MarxanServicesError) as e:
            self.send_response({'error': e.message})
        else:
            #get the project data
            _getProjectData(self)
            if (self.projectData["metadata"]["OLDVERSION"] == 'False'):
                #new version of marxan - do the intersection
                future = self.executeQueryAsynchronously("select * from marxan.get_pu_areas_for_interest_feature('" + self.get_argument('planning_grid_name') + "','" + self.get_argument('feature_class_name') + "');")
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
        if (future):
            #get the intersection data as a dataframe from the queryresults
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
        try: 
            #write the data to the PUVSPR.dat file
            _writeCSV(self, "PUVSPRNAME", df)
            #get the summary information and write it to the feature preprocessing file
            #get the count of intersecting planning units
            pu_count = df[df.species.isin([speciesId])].agg({'pu' : ['count']})['pu'].iloc[0]
            #get the total area of the feature across all planning units
            pu_area = df[df.species.isin([speciesId])].agg({'amount': ['sum']})['amount'].iloc[0]
            #write the pu_area and pu_count to the preprocessing.dat file 
            record = pandas.DataFrame({'id':speciesId, 'pu_area': [pu_area], 'pu_count': [pu_count]}).astype({'id': 'int', 'pu_area':'float', 'pu_count':'int'})
            _writeToDatFile(self.folder_input + FEATURE_PREPROCESSING_FILENAME, record)
        except (MarxanServicesError) as e:
            self.send_response({'error': e.message})
        #update the input.dat file
        _updateParameters(self.folder_project + "input.dat", {'PUVSPRNAME': 'puvspr.dat'})
        #set the response
        self.send_response({'info': "Feature " + self.get_argument('feature_class_name') + " preprocessed", "feature_class_name": self.get_argument('feature_class_name'), "pu_area" : str(pu_area),"pu_count" : str(pu_count), "id":str(speciesId)})

#wss://db-server-blishten.c9users.io:8081/marxan-server/preprocessFeature?user=andrew&project=Tonga%20marine%2030km2&planning_grid_name=pu_ton_marine_hexagons_30&feature_class_name=volcano&id=63408475
# class runMarxan(QueryWebSocketHandler):
#     def open(self):
#         #get the user folder and project folders
#         super(runMarxan, self).open()
#         try:    
#             #set the current folder to the project folder so files can be found in the input.dat file
#             os.chdir(self.folder_project)
#             print self.folder_project
#             #delete all of the current output files
#             _deleteAllFiles(self.folder_output)
#             #run marxan 
#             self.send_response({'info': 'Marxan starting'})
#             print 'Marxan starting'
#             p = subprocess.call(MARXAN_EXECUTABLE, stdout=subprocess.PIPE) 
#             print p
#             print 'Marxan finished'
#             self.send_response({'info': 'Marxan finished'})
#         except:
#             self.send_response({'error': sys.exc_info()[0]})

class runMarxan(MarxanWebSocketHandler):
    def open(self):
        super(runMarxan, self).open()
        #set the current folder to the project folder so files can be found in the input.dat file
        os.chdir(self.folder_project)
        #delete all of the current output files
        _deleteAllFiles(self.folder_output)
        #run marxan - the Subprocess.STREAM option does not work on Windows - see here: https://www.tornadoweb.org/en/stable/process.html?highlight=Subprocess#tornado.process.Subprocess
        self.app = Subprocess([MARXAN_EXECUTABLE + ";\n"], stdout=Subprocess.STREAM, stdin=subprocess.PIPE, shell=True)
        IOLoop.current().spawn_callback(self.stream_output)
        self.app.stdin.write('\n') # to end the marxan process send ENTER to the stdin

    @gen.coroutine
    def stream_output(self):
        try:
            while True:
                # line = yield self.app.stdout.read_bytes(4096)
                line = yield self.app.stdout.read_bytes(4096, partial=True)
                self.write_message(line)
        except StreamClosedError as e:
            print e.message
    
####################################################################################################################################################################################################################################################################
## tornado functions
####################################################################################################################################################################################################################################################################

def make_app():
    return tornado.web.Application([
        ("/marxan-server/getCountries", getCountries),
        ("/marxan-server/validateUser", validateUser),
        ("/marxan-server/getUser", getUser),
        ("/marxan-server/getProject", getProject),
        ("/marxan-server/getSpeciesData", getSpeciesData),
        ("/marxan-server/getAllSpeciesData", getAllSpeciesData),
        ("/marxan-server/getSpeciesPreProcessingData", getSpeciesPreProcessingData),
        ("/marxan-server/getPlanningUnitsData", getPlanningUnitsData),
        ("/marxan-server/getProtectedAreaIntersectionsData", getProtectedAreaIntersectionsData),
        ("/marxan-server/getMarxanLog", getMarxanLog),
        ("/marxan-server/getBestSolution", getBestSolution),
        ("/marxan-server/getOutputSum", getOutputSum),
        ("/marxan-server/getSummedSolution", getSummedSolution),
        ("/marxan-server/getResults", getResults),
        ("/marxan-server/getProjects", getProjects),
        ("/marxan-server/updateSpecFile", updateSpecFile),
        ("/marxan-server/preprocessFeature", preprocessFeature),
        ("/marxan-server/runMarxan", runMarxan),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8081, '0.0.0.0')
    #turn on tornado logging 
    tornado.options.parse_command_line() 
    tornado.ioloop.IOLoop.current().start()