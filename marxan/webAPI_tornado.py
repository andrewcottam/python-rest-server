import tornado.ioloop
import tornado.web
import tornado.options
import logging
import json
import psycopg2
import pandas
import os
import re
import traceback

####################################################################################################################################################################################################################################################################
## constant declarations
####################################################################################################################################################################################################################################################################
MARXAN_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/"
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

####################################################################################################################################################################################################################################################################
## generic classes
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
    pass

####################################################################################################################################################################################################################################################################
## baseclass for handling REST requests
####################################################################################################################################################################################################################################################################

class MarxanRESTHandler(MarxanHandler):
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
                #get the project folder
                if "project" in self.request.arguments.keys():
                    self.folder_project = self.folder_user + self.get_argument("project") + os.sep
                    if not os.path.exists(self.folder_project):
                        raise MarxanServicesError("The project folder '" + self.folder_project +"' does not exist") 
                    self.folder_input =  self.folder_project + "input" + os.sep
                    self.folder_output = self.folder_project + "output" + os.sep
                    
        except (MarxanServicesError) as e:
            logging.error(e.message)
            self.response.update({"error": repr(e)})
    
    def writeReponse(self):
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
    
    def write_error(self, status_code, **kwargs):
        if "exc_info" in kwargs:
            trace = ""
            for line in traceback.format_exception(*kwargs["exc_info"]):
                trace = trace + line
            lastLine = traceback.format_exception(*kwargs["exc_info"])[len(traceback.format_exception(*kwargs["exc_info"]))-1]
            self.response.update({"error":lastLine, "trace" : trace})
            self.set_status(200)
            self.writeReponse()
            self.finish()
            
    def validateArguments(self, argumentList):
        for argument in argumentList:
            if argument not in self.request.arguments.keys():
                raise MarxanServicesError("Missing input argument:" + argument)
        
    def getUserData(self):
        #get the data on the user from the user.dat file 
        userDataFilename = self.folder_user + os.sep + "user.dat"
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
    
    def getProjectData(self):
        #get the project data from the input.dat file
        paramsArray = []
        filesDict = {}
        metadataDict = {}
        rendererDict = {}
        #get the file contents
        s = readFile(self.folder_project + "input.dat")
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
        self.projectData.update({'project': self.get_argument("project"), 'metadata': metadataDict, 'files': filesDict, 'runParameters': paramsArray, 'renderer': rendererDict})
        
    def getSpeciesData(self):
        #get the species data from the spec.dat file as a DataFrame and joins it to the data from the PostGIS database if it is the marxan web version
        if not hasattr(self, "projectData"):
            self.getProjectData()
        speciesDataFilename = self.projectData["files"]["SPECNAME"]
        
        #get the values from the spec.dat file - speciesDataFilename will be empty if it doesn't exist yet
        if speciesDataFilename:
            df = pandas.read_csv(self.folder_input + speciesDataFilename)
        else:
            df = pandas.DataFrame()

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
        
    def getAllSpeciesData(self):
        #get all species information from the PostGIS database
        self.allSpeciesData = PostGIS().getDataFrame("SELECT oid::integer as id, creation_date::text, feature_class_name, alias, _area area, description FROM marxan.metadata_interest_features order by alias;")

    def getSpeciesPreProcessingData(self):
        #get the information about which species have already been preprocessed
        if (os.path.exists(self.folder_input + FEATURE_PREPROCESSING_FILENAME)):
            df = pandas.read_csv(self.folder_input + FEATURE_PREPROCESSING_FILENAME)
        else:
            df = pandas.DataFrame()
        
        self.speciesPreProcessingData = df

    def getPlanningUnitsData(self):
        #get the planning units information
        if (os.path.exists(self.folder_input + "pu.dat")):
            df = pandas.read_csv(self.folder_input + "pu.dat")
        else:
            df = pandas.DataFrame()
        
        #normalise the planning unit data to make the payload smaller        
        self.planningUnitsData = normaliseDataFrame(df, "status", "id")

    def getProtectedAreaIntersectionsData(self):
        #get the protected area intersections information
        if (os.path.exists(self.folder_input + PROTECTED_AREA_INTERSECTIONS_FILENAME)):
            df = pandas.read_csv(self.folder_input + PROTECTED_AREA_INTERSECTIONS_FILENAME)
        else:
            df = pandas.DataFrame()
        
        #normalise the protected area intersections to make the payload smaller           
        self.protectedAreaIntersectionsData = normaliseDataFrame(df, "iucn_cat", "puid")

####################################################################################################################################################################################################################################################################
## RequestHandler subclasses
####################################################################################################################################################################################################################################################################

#https://db-server-blishten.c9users.io:8081/marxan-server/getCountries?callback=__jp0
class getCountries(MarxanRESTHandler):
    def get(self):
        content = PostGIS().getDict("SELECT iso3, original_n FROM marxan.gaul_2015_simplified_1km where original_n not like '%|%' and iso3 not like '%|%' order by 2;")
        self.response.update({'records': content})        
        self.writeReponse()

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
        self.writeReponse()

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
        self.writeReponse()

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
        self.writeReponse()

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
        self.writeReponse()

#gets all species information from the PostGIS database
#https://db-server-blishten.c9users.io:8081/marxan-server/getAllSpeciesData?callback=__jp2
class getAllSpeciesData(MarxanRESTHandler):
    def get(self):
        #get all the species data
        self.getAllSpeciesData()
        
        #set the response
        self.response.update({"data": self.allSpeciesData.to_dict(orient="records")})
        self.writeReponse()

#gets the species preprocessing information from the feature_preprocessing.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getSpeciesPreProcessingData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getSpeciesPreProcessingData(MarxanRESTHandler):
    def get(self):
        #get the species preprocessing data
        self.getSpeciesPreProcessingData()
        
        #set the response
        self.response.update({"data": self.speciesPreProcessingData.to_dict(orient="split")["data"]})
        self.writeReponse()

#gets the planning units information from the pu.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getPlanningUnitsData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getPlanningUnitsData(MarxanRESTHandler):
    def get(self):
        #get the planning units information
        self.getPlanningUnitsData()
        
        #set the response
        self.response.update({"data": self.planningUnitsData})
        self.writeReponse()

#gets the intersections of the planning units with the protected areas from the protected_area_intersections.dat file
#https://db-server-blishten.c9users.io:8081/marxan-server/getProtectedAreaIntersectionsData?user=andrew&project=Tonga%20marine%2030km2&callback=__jp2
class getProtectedAreaIntersectionsData(MarxanRESTHandler):
    def get(self):
        #get the protected area intersections
        self.getProtectedAreaIntersectionsData()
        
        #set the response
        self.response.update({"data": self.protectedAreaIntersectionsData})
        self.writeReponse()

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
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8081, '0.0.0.0')
    #turn on tornado logging 
    tornado.options.parse_command_line() 
    tornado.ioloop.IOLoop.current().start()