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

####################################################################################################################################################################################################################################################################
## constant declarations
####################################################################################################################################################################################################################################################################
MARXAN_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/"
USER_DATA_FILENAME = "user.dat"
PROJECT_DATA_FILENAME = "input.dat"
PLANNING_UNIT_DATA_FILENAME = "pu.dat"
OUTPUT_LOG_FILENAME = "output_log.dat"
BEST_SOLUTION_FILENAME = "output_mvbest.txt"
OUTPUT_SUM_FILENAME = "output_sum.txt"
SUMMED_SOLUTION_FILENAME = "output_ssoln.txt"
FEATURE_PREPROCESSING_FILENAME = "feature_preprocessing.dat"
PROTECTED_AREA_INTERSECTIONS_FILENAME = "protected_area_intersections.dat"

####################################################################################################################################################################################################################################################################
## generic functions
####################################################################################################################################################################################################################################################################
#gets a files contents as a string
def readFile(filename):
    f = open(filename)
    s = f.read()
    f.close()
    return s

#returns all the keys from a set of KEY/VALUE pairs in a string expression
def getKeys(s):
    #instantiate the return arrays
    keys = []
    #get all the parameter keys
    matches = re.findall('\\n[A-Z1-9_]{2,}', s, re.DOTALL)
    return [m[1:] for m in matches]
  
#gets the key value combination from the text, e.g. PUNAME pu.dat    
def getKeyValue(text, parameterName):
    p1 = text.index(parameterName)
    value = text[p1 + len(parameterName) + 1:text.index("\r",p1)]
    return parameterName, value

#converts a data frame with duplicate values into a normalised array
def normaliseDataFrame(df, columnToNormaliseBy, puidColumnName):
    #get the groups from the data
    groups = df.groupby(by = columnToNormaliseBy).groups
    #build the response, e.g. a normal data frame with repeated values in the columnToNormaliseBy -> [["VI", [7, 8, 9]], ["IV", [0, 1, 2, 3, 4]], ["V", [5, 6]]]
    response = [[g, df[puidColumnName][groups[g]].values.tolist()] for g in groups if g not in [0]]
    return response

#loads a csv file and returns the data as a dataframe or an empty dataframe if the file does not exist
def loadCSV(filename):
    if (os.path.exists(filename)):
        df = pandas.read_csv(filename)
    else:
        df = pandas.DataFrame()
    return df

#deletes the records in the text file that have id values that match the passed ids
def deleteRecordsInTextFile(filename, id_columnname, ids, write_index):
    if (filename) and (os.path.exists(filename)):
        #if the file exists then get the existing data
        df = loadCSV(filename)
        #remove the records with the matching ids
        df = df[~df[id_columnname].isin(ids)]
        #write the results back to the file
        df.to_csv(filename, index = write_index)

#converts a comma-separated set of integer values to a list of integers
def txtIntsToList(txtInts):
    return [int(s) for s in txtInts.split(",")] 

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
## generic baseclass for handling all requests
####################################################################################################################################################################################################################################################################

class MarxanHandler(tornado.web.RequestHandler):
    #to prevent CORS errors in the client
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
    pass

####################################################################################################################################################################################################################################################################
## baseclass for handling REST requests
####################################################################################################################################################################################################################################################################

class MarxanRESTHandler(MarxanHandler):
    #called before the request is processed 
    def prepare(self):
        try:
            #instantiate the response dictionary
            self.response = {}
            #get the user folder
            if "user" in self.request.arguments.keys():
                self.folder_user = MARXAN_FOLDER + self.get_argument("user") + os.sep
                if not os.path.exists(self.folder_user):
                    raise MarxanServicesError("The user folder '" + self.folder_user +"' does not exist") 
                self.user = self.get_argument("user")
                #get the project folder and the input and output folders
                if "project" in self.request.arguments.keys():
                    self.folder_project = self.folder_user + self.get_argument("project") + os.sep
                    if not os.path.exists(self.folder_project):
                        raise MarxanServicesError("The project folder '" + self.folder_project +"' does not exist") 
                    self.folder_input =  self.folder_project + "input" + os.sep
                    self.folder_output = self.folder_project + "output" + os.sep
                    self.project = self.get_argument("project")
                    
        except (MarxanServicesError) as e:
            logging.error(e.message)
            self.response.update({"error": repr(e)})
    
    #used by all descendent classes to write the return payload
    def write_response(self):
        try:
            #set the return header as json
            self.set_header('Content-Type','application/json')
            #convert the dictionary to json
            content = json.dumps(self.response)
            
        #sometimes the Marxan log causes json encoding issues
        except (UnicodeDecodeError) as e: 
            logging.error("UnicodeDecodeError")
            if 'log' in self.response.keys():
                self.response.update({"log": "Server warning: Unable to encode the Marxan log. <br/>" + repr(e), "warning": "Unable to encode the Marxan log"})
                content = json.dumps(self.response)        
                
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
            self.response.update({"error":lastLine, "trace" : trace})
            self.set_status(200)
            self.write_response()
            self.finish()
    
    #checks that the request object contains all of the arguments in the argumentList otherwise throws an exception
    def validateArguments(self, argumentList):
        for argument in argumentList:
            if argument not in self.request.arguments.keys():
                raise MarxanServicesError("Missing input argument:" + argument)
        
    #gets the name of the input file from the projects input.dat file
    def getProjectInputFilename(self, fileToGet):
        if not hasattr(self, "projectData"):
            self.getProjectData()
        speciesDataFilename = self.projectData["files"]["SPECNAME"]
        return self.projectData["files"][fileToGet]
    
    #get the data on the user from the user.dat file 
    def getUserData(self):
        userDataFilename = self.folder_user + USER_DATA_FILENAME
        if not os.path.exists(userDataFilename):
            raise MarxanServicesError("The user.dat file '" + userDataFilename +"' does not exist") 
        #get the file contents
        s = readFile(userDataFilename)
        #get the keys from the file
        keys = getKeys(s)
        #iterate through the keys, get their values add add them to this request object in the userData object
        self.userData = {}
        for k in keys:
            key, value = getKeyValue(s, k)
            #update the  dict
            if value == "true":
                value = True
            if value == "false":
                value = False
            self.userData[key] = value
    
    #get the project data from the input.dat file
    def getProjectData(self):
        paramsArray = []
        filesDict = {}
        metadataDict = {}
        rendererDict = {}
        #get the file contents
        s = readFile(self.folder_project + PROJECT_DATA_FILENAME)
        #get the keys from the file
        keys = getKeys(s)
        #iterate through the keys and get their values
        for k in keys:
            #some parameters we do not need to return
            if k in ["PUNAME","SPECNAME","PUVSPRNAME","BOUNDNAME","BLOCKDEF"]: # Input Files section of input.dat file
                key, value = getKeyValue(s, k) 
                filesDict.update({ key:  value})
            elif k in ['BLM', 'PROP', 'RANDSEED', 'NUMREPS', 'NUMITNS', 'STARTTEMP', 'NUMTEMP', 'COSTTHRESH', 'THRESHPEN1', 'THRESHPEN2', 'SAVERUN', 'SAVEBEST', 'SAVESUMMARY', 'SAVESCEN', 'SAVETARGMET', 'SAVESUMSOLN', 'SAVEPENALTY', 'SAVELOG', 'RUNMODE', 'MISSLEVEL', 'ITIMPTYPE', 'HEURTYPE', 'CLUMPTYPE', 'VERBOSITY', 'SAVESOLUTIONSMATRIX']:
                key, value = getKeyValue(s, k) #run parameters 
                paramsArray.append({'key': key, 'value': value})
            elif k in ['DESCRIPTION','CREATEDATE','PLANNING_UNIT_NAME','OLDVERSION','IUCN_CATEGORY']: # metadata section of the input.dat file
                key, value = getKeyValue(s, k)
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
                key, value = getKeyValue(s, k)
                rendererDict.update({key: value})
        #set the project data
        self.projectData = {}
        self.projectData.update({'project': self.project, 'metadata': metadataDict, 'files': filesDict, 'runParameters': paramsArray, 'renderer': rendererDict})
        
    #get the species data from the spec.dat file as a DataFrame (and joins it to the data from the PostGIS database if it is the Marxan web version)
    def getSpeciesData(self):
        speciesDataFilename = self.getProjectInputFilename("SPECNAME")
        #get the values from the spec.dat file - speciesDataFilename will be empty if it doesn't exist yet
        df = loadCSV(self.folder_input + speciesDataFilename)
        #create the output data frame using the id field as an index
        output_df = df.set_index("id")
        #add the index as a column
        output_df['oid'] = output_df.index
        #see if the version of marxan is the old version
        if self.projectData["metadata"]["OLDVERSION"] == "True":
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
        self.speciesData = output_df
        
    #get all species information from the PostGIS database
    def getAllSpeciesData(self):
        self.allSpeciesData = PostGIS().getDataFrame("SELECT oid::integer as id, creation_date::text, feature_class_name, alias, _area area, description FROM marxan.metadata_interest_features order by alias;")

    #get the information about which species have already been preprocessed
    def getSpeciesPreProcessingData(self):
        self.speciesPreProcessingData = loadCSV(self.folder_input + FEATURE_PREPROCESSING_FILENAME)

    #get the planning units information
    def getPlanningUnitsData(self):
        df = loadCSV(self.folder_input + PLANNING_UNIT_DATA_FILENAME)
        #normalise the planning unit data to make the payload smaller        
        self.planningUnitsData = normaliseDataFrame(df, "status", "id")

    #get the protected area intersections information
    def getProtectedAreaIntersectionsData(self):
        df = loadCSV(self.folder_input + PROTECTED_AREA_INTERSECTIONS_FILENAME)
        #normalise the protected area intersections to make the payload smaller           
        self.protectedAreaIntersectionsData = normaliseDataFrame(df, "iucn_cat", "puid")
        
    #gets the marxan log after a run
    def getMarxanLog(self):
        if (os.path.exists(self.folder_output + OUTPUT_LOG_FILENAME)):
            log = readFile(self.folder_output + OUTPUT_LOG_FILENAME)
        else:
            log = ""
        #there are some characters in the log file which cause the json parser to fail - remove them
        log = log.replace("\x90","")
        log = log.replace(chr(176),"") #Graphic character, low density dotted
        self.marxanLog = log

    def getBestSolution(self):
        self.bestSolution = loadCSV(self.folder_output + BEST_SOLUTION_FILENAME)

    def getOutputSum(self):
        self.outputSum = loadCSV(self.folder_output + OUTPUT_SUM_FILENAME)

    def getSummedSolution(self):
        df = loadCSV(self.folder_output + SUMMED_SOLUTION_FILENAME)
        self.summedSolution = normaliseDataFrame(df, "number", "planning_unit")

    #gets the projects for the current user
    def getProjects(self):
        #get a list of folders underneath the users home folder
        project_folders = glob.glob(MARXAN_FOLDER + self.user + os.sep + "*/")
        #sort the folders
        project_folders.sort()
        projects = []
        #iterate through the project folders and get the parameters for each project to return
        for dir in project_folders:
            #get the name of the folder 
            project = dir[:-1][dir[:-1].rfind("/")+1:]
            if (project[:2] != "__"): #folders beginning with __ are system folders
                #get the data from the input file for this project
                self.project = project
                self.folder_project = MARXAN_FOLDER + self.user + os.sep + project + os.sep
                self.getProjectData()
                #create a dict to save the data
                projects.append({'name': project,'description': self.projectData["metadata"]["DESCRIPTION"],'createdate': self.projectData["metadata"]["CREATEDATE"],'oldVersion': self.projectData["metadata"]["OLDVERSION"]})
        self.projects = projects
    
    #creates or updates the spec.dat file with the passed interest features
    def updateSpeciesFile(self, interest_features, target_values, spf_values):
        #get the features to create/update as a list of integer ids
        ids = txtIntsToList(interest_features)
        props = txtIntsToList(target_values) 
        spfs = spf_values.split(",") 
        #get the spec.dat filename from the projects input.dat file
        speciesDataFilename = self.getProjectInputFilename("SPECNAME")
        #get the current list of features
        df = loadCSV(self.folder_input + speciesDataFilename)
        currentIds = df.id.unique().tolist() 
        #get the list of features to remove from the current list (i.e. they are not in the passed list of interest features)
        removedIds = list(set(currentIds) - set(ids))
        #update the puvspr.dat file and the feature preprocessing files to remove any species that are no longer in the project
        if len(removedIds) > 0:
            #get the name of the puvspr file from the project data
            puvsprFilename = self.getProjectInputFilename("PUVSPRNAME")
            #update the puvspr.dat file
            deleteRecordsInTextFile(puvsprFilename, "species", removedIds, False)
            #update the preprocessing.dat file to remove any species that are no longer in the project - these will need to be preprocessed again
            deleteRecordsInTextFile(self.folder_input + FEATURE_PREPROCESSING_FILENAME, "id", removedIds, False)
        #open the file writer and write the header for the spec.dat file
        file = open(self.folder_input + speciesDataFilename, "w") 
        file.write('id,prop,spf\n')
        #write the spec data to file
        for i in range(len(ids)):
            if i not in removedIds:
                file.write(str(ids[i]) + "," + str(float(props[i])/100) + "," + spfs[i] + "\n")
        file.close()
        
####################################################################################################################################################################################################################################################################
## RequestHandler subclasses
####################################################################################################################################################################################################################################################################

#https://db-server-blishten.c9users.io:8081/marxan-server/getCountries?callback=__jp0
class getCountries(MarxanRESTHandler):
    def get(self):
        content = PostGIS().getDict("SELECT iso3, original_n FROM marxan.gaul_2015_simplified_1km where original_n not like '%|%' and iso3 not like '%|%' order by 2;")
        self.response.update({'records': content})        
        self.write_response()

#validates a user with the passed credentials
#https://db-server-blishten.c9users.io:8081/marxan-server/validateUser?user=andrew&password=thargal88&callback=__jp2
class validateUser(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','password'])    
        #get the user data from the user.dat file
        self.getUserData()
        #compare the passed password to the one in the user.dat file
        if self.get_argument("password") == self.userData["PASSWORD"]:
            #set the response
            self.response.update({'info': "User " + self.user + " validated"})
        else:
            #invalid login
            raise MarxanServicesError("Invalid login")    
        self.write_response()

#gets a users information from the user folder
#https://db-server-blishten.c9users.io:8081/marxan-server/getUser?user=andrew&callback=__jp2
class getUser(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user'])    
        #get the user data from the user.dat file
        self.getUserData()
        #set the response
        self.response.update({'info': "User data received", "userData" : {k: v for k, v in self.userData.iteritems() if k != 'PASSWORD'}})
        self.write_response()

#gets project information from the input.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getProject?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getProject(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the project data from the input.dat file
        self.getProjectData()
        #get the species data from the spec.dat file and the PostGIS database
        self.getSpeciesData()
        #get all species data from the PostGIS database
        self.getAllSpeciesData()
        #get the species preprocessing from the feature_preprocessing.dat file
        self.getSpeciesPreProcessingData()
        #get the planning units information
        self.getPlanningUnitsData()
        #get the protected area intersections
        self.getProtectedAreaIntersectionsData()
        #set the response
        self.response.update({'project': self.projectData["project"], 'metadata': self.projectData["metadata"], 'files': self.projectData["files"], 'runParameters': self.projectData["runParameters"], 'renderer': self.projectData["renderer"], 'features': self.speciesData.to_dict(orient="records"), 'allFeatures': self.allSpeciesData.to_dict(orient="records"), 'feature_preprocessing': self.speciesPreProcessingData.to_dict(orient="split")["data"], 'planning_units': self.planningUnitsData, 'protected_area_intersections': self.protectedAreaIntersectionsData})
        self.write_response()

#gets species information for a specific project from the spec.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getSpeciesData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getSpeciesData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the species data from the spec.dat file and PostGIS
        self.getSpeciesData()
        #set the response
        self.response.update({"data": self.speciesData.to_dict(orient="records")})
        self.write_response()

#gets all species information from the PostGIS database
#https://db-server-blishten.c9users.io:8081/marxan-server/getAllSpeciesData?callback=__jp2
class getAllSpeciesData(MarxanRESTHandler):
    def get(self):
        #get all the species data
        self.getAllSpeciesData()
        #set the response
        self.response.update({"data": self.allSpeciesData.to_dict(orient="records")})
        self.write_response()

#gets the species preprocessing information from the feature_preprocessing.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getSpeciesPreProcessingData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getSpeciesPreProcessingData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the species preprocessing data
        self.getSpeciesPreProcessingData()
        #set the response
        self.response.update({"data": self.speciesPreProcessingData.to_dict(orient="split")["data"]})
        self.write_response()

#gets the planning units information from the pu.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getPlanningUnitsData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getPlanningUnitsData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the planning units information
        self.getPlanningUnitsData()
        #set the response
        self.response.update({"data": self.planningUnitsData})
        self.write_response()

#gets the intersections of the planning units with the protected areas from the protected_area_intersections.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getProtectedAreaIntersectionsData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getProtectedAreaIntersectionsData(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the protected area intersections
        self.getProtectedAreaIntersectionsData()
        #set the response
        self.response.update({"data": self.protectedAreaIntersectionsData})
        self.write_response()

#gets the Marxan log for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getMarxanLog?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getMarxanLog(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the log
        self.getMarxanLog()
        #set the response
        self.response.update({"log": self.marxanLog})
        self.write_response()

#gets the best solution for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getBestSolution?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getBestSolution(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the best solution
        self.getBestSolution()
        #set the response
        self.response.update({"data": self.bestSolution.to_dict(orient="split")["data"]})
        self.write_response()

#gets the output sum for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getOutputSum?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getOutputSum(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the output sum
        self.getOutputSum()
        #set the response
        self.response.update({"data": self.outputSum.to_dict(orient="split")["data"]})
        self.write_response()

#gets the summed solution for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getSummedSolution?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getSummedSolution(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the summed solution
        self.getSummedSolution()
        #set the response
        self.response.update({"data": self.summedSolution})
        self.write_response()

#gets the combined results for the project
#https://db-server-blishten.c9users.io:8081/marxan-server/getResults?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getResults(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user','project'])    
        #get the log
        self.getMarxanLog()
        #get the best solution
        self.getBestSolution()
        #get the output sum
        self.getOutputSum()
        #get the summed solution
        self.getSummedSolution()
        #set the response
        self.response.update({'info':'Results loaded', 'log': self.marxanLog, 'mvbest': self.bestSolution.to_dict(orient="split")["data"], 'sum':self.outputSum.to_dict(orient="split")["data"], 'ssoln': self.summedSolution})
        self.write_response()

#gets a list of projects for the user
#https://db-server-blishten.c9users.io:8081/marxan-server/getProjects?user=andrew&callback=__jp2
class getProjects(MarxanRESTHandler):
    def get(self):
        #validate the input arguments
        self.validateArguments(['user'])    
        #get the projects
        self.getProjects()
        #set the response
        self.response.update({"projects": self.projects})
        self.write_response()

#updates the spec.dat file with the posted data
class updateSpecFile(MarxanRESTHandler):
    def post(self):
        #validate the input arguments
        self.validateArguments(['user','project','interest_features','spf_values','target_values'])    
        #update the spec.dat file and other related files 
        self.updateSpeciesFile(self.get_argument("interest_features"), self.get_argument("target_values"), self.get_argument("spf_values"))
        #set the response
        self.response.update({'info': "spec.dat file updated"})
        self.write_response()
        
class EchoWebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket opened")
    
    #to avoid CORS issues
    def check_origin(self, origin):
        return True
    
    def on_message(self, message):
        self.write_message(u"You said: " + message)

    def on_close(self):
        print("WebSocket closed")
        
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
        ("/marxan-server/EchoWebSocket", EchoWebSocket),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8081, '0.0.0.0')
    #turn on tornado logging 
    tornado.options.parse_command_line() 
    tornado.ioloop.IOLoop.current().start()