#!/home/ubuntu/anaconda2/bin/python
#the above line forces the CGI script to use the Anaconda Python interpreter
import sys, os, web, subprocess, urllib, pandas, json, glob, shutil, re, datetime, logging, spatialServer, CustomExceptionClasses
import geopandas as gpd
from collections import OrderedDict
from shutil import copyfile
from CustomExceptionClasses import MarxanServicesError

MARXAN_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/"
MARXAN_EXECUTABLE = MARXAN_FOLDER + "MarOpt_v243_Linux64"
MARXAN_OUTPUT_FOLDER = MARXAN_FOLDER + "output" + os.sep 
MARXAN_INPUT_PARAMETER_FILENAME = MARXAN_FOLDER + "input.dat"
MARXAN_INPUT_FOLDER = MARXAN_FOLDER + "input" + os.sep
SAMPLE_TILESET_ID = "blishten.3ogmvag8" #this is the sample data that comes with marxan and consists of a grid of 100 planning units
SAMPLE_TILESET_ID_PNG = "blishten.pulayer_costt" #png example

urls = (
  "/listUsers", "listUsers",
  "/createUser", "createUser",
  "/validateUser","validateUser",
  "/resendPassword","resendPassword",
  "/getUser","getUser",
  "/updateUser","updateUser",
  "/listScenarios", "listScenarios",
  "/getScenario","getScenario",
  "/createScenario", "createScenario",
  "/deleteScenario", "deleteScenario",
  "/renameScenario", "renameScenario",
  "/renameDescription", "renameDescription",
  "/updateRunParams","updateRunParams",
  "/runMarxan", "runMarxan", 
  "/pollResults","pollResults",
  "/loadSolution", "loadSolution", 
  "/postFile","postFile",
  "/updateParameter","updateParameter",
  "/createPlanningUnitsGrid","createPlanningUnitsGrid"
  )
 
def getQueryStringParams(querystring):
    if len(querystring):
        return dict([(q.split("=")[0].upper(), urllib.unquote(q.split("=")[1])) for q in querystring.split("&")])
    else:
        return None

def writeFile(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()
    
def readFile(filename):
    f = open(filename)
    s = f.read()
    f.close()
    return s

#gets the key value combination from the text, e.g. PUNAME pu.dat    
def getKeyValue(text, parameterName):
    p1 = text.index(parameterName)
    value = text[p1 + len(parameterName) + 1:text.index("\r",p1)]
    return parameterName, value

#gets the position of the end of the line which may be different in windows/unix generated files
def getEndOfLine(text):
    try:
        p = text.index("\r\n") 
    except (ValueError):
        p = text.index("\n") 
    return p

#gets a single input parameter, i.e. the actual value and not the parameter name
def getInputParameter(filename, parameter):
    #get the file contents
    s = readFile(filename)
    p1 = s.index(parameter) #get the first position of the parameter
    if p1>-1:
        p2 = s[p1:].index(" ") #get the position of the space
        if p2 > 0:
            p3 = getEndOfLine(s[p1:]) #get the position of the end of line
            if p3 > 0:
                return s[p1 + p2 + 1:p1 + p3]

def getKeys(s):
    #instantiate the return arrays
    keys = []
    #get all the parameter keys
    matches = re.findall('\\n[A-Z1-9]{2,}', s, re.DOTALL)
    return [m[1:] for m in matches]
  
def getUserData(filename):
    returnDict = {}
    #get the file contents
    s = readFile(filename)
    #get the keys from the file
    keys = getKeys(s)
    #iterate through the keys and get their values
    for k in keys:
        key, value = getKeyValue(s, k)
        #update the return dict
        if value == "true":
            value = True
        if value == "false":
            value = False
        if key not in ["PASSWORD"]:
            returnDict.update({ key:  value})
    return returnDict  
    
def getInputParameters(filename):
    #instantiate the return arrays
    paramsArray = []
    filesDict = {}
    metadataDict = {}
    rendererDict = {}
    #get the file contents
    s = readFile(filename)
    #get the keys from the file
    keys = getKeys(s)
    #iterate through the keys and get their values
    for k in keys:
        #some parameters we do not need to return
        if k in ["PUNAME","SPECNAME","PUVSPRNAME","BOUNDNAME","BLOCKDEF"]:
            key, value = getKeyValue(s, k)
            filesDict.update({ key:  value})
        elif k in ['BLM', 'PROP', 'RANDSEED', 'NUMREPS', 'NUMITNS', 'STARTTEMP', 'NUMTEMP', 'COSTTHRESH', 'THRESHPEN1', 'THRESHPEN2', 'SAVERUN', 'SAVEBEST', 'SAVESUMMARY', 'SAVESCEN', 'SAVETARGMET', 'SAVESUMSOLN', 'SAVEPENALTY', 'SAVELOG', 'RUNMODE', 'MISSLEVEL', 'ITIMPTYPE', 'HEURTYPE', 'CLUMPTYPE', 'VERBOSITY', 'SAVESOLUTIONSMATRIX']:
            key, value = getKeyValue(s, k)
            paramsArray.append({'key': key, 'value': value})
        elif k in ['DESCRIPTION','CREATEDATE','MAPID']:
            key, value = getKeyValue(s, k)
            metadataDict.update({key: value})
        elif k in ['CLASSIFICATION', 'NUMCLASSES','COLORCODE', 'TOPCLASSES','OPACITY']:
            key, value = getKeyValue(s, k)
            rendererDict.update({key: value})
                        
    return filesDict, paramsArray, metadataDict, rendererDict
    
#updates the parameters in the *.dat file with the new parameters passed as a dict
def updateParameters(data_file, newParams):
    if newParams:
        #get the existing parameters 
        s = readFile(data_file)
        #update any that are passed in as query params
        for k, v in newParams.iteritems():
            try:
                p1 = s.index(k) #get the first position of the parameter
                if p1>-1:
                    p2 = getEndOfLine(s[p1:]) #get the position of the end of line
                    s = s[:p1] + k + " " + v + s[(p1 + p2):]
                #write these parameters back to the *.dat file
                writeFile(data_file, s)
            except ValueError:
                continue
    return 

def createShapefileWithResults():
    #get the planning units as a GeoDataFrame
    planning_units = gpd.read_file(MARXAN_FOLDER + "pulayer1km.shp")
    #get the summed solutions as a DataFrame
    summed_solution = pandas.read_csv(MARXAN_OUTPUT_FOLDER + "output_ssoln.txt")
    #join these datasets together 
    summed_solution_shapes = planning_units.merge(summed_solution,left_on="PUID",right_on="planning_unit")
    #write the results to a shapefile
    summed_solution_shapes.to_file(MARXAN_OUTPUT_FOLDER + "results.shp")

def deleteAllFiles(folder):
    files = glob.glob(folder + "*")
    for f in files:
        os.remove(f)

#initialises the rest request and response from a GET request
# 1. initialises a response dict which is used to populate the response information
# 2. gets the request parameters as a dictionary which are passed as query parameters
# 3. sets the user, scenario, input and output folders for the user 
def initialiseGetRequest(queryString):
    #initialise the response dictionary
    response = {}
    #get the parameters to pass on to marxan
    params = getQueryStringParams(queryString)
    #get the user, input and output folders
    params.setdefault('USER','') # set to an empty string if it is not passed, e.g. in getUsers, createUsers etc.
    params.setdefault('SCENARIO','Sample scenario') # set to a sample string if it is not passed, e.g. in getUsers, createUsers etc.
    user_folder, scenario_folder, input_folder, output_folder = getFolders(params['USER'], params['SCENARIO'])
    return user_folder, scenario_folder, input_folder, output_folder, response, params

#initialises the folders from a POST request
def initialisePostRequest(data):
    try:
        #check the user parameter
        if not ("user" in data.keys()):
            raise MarxanServicesError("No user parameter found")

        #check the scenario parameter - if none is passed then set a default = some updates dont pass a scenario, e.g. updateUser, createUser etc
        if not ("scenario" in data.keys()):
            scenario = "Sample scenario"
        else:
            scenario = data.scenario

        #get the user, scenario, input and output folders
        user_folder, scenario_folder, input_folder, output_folder = getFolders(data.user, scenario)
        
    except (MarxanServicesError) as e:
        raise
        
    return user_folder, scenario_folder, input_folder, output_folder
    
def getFolders(user, scenario):
    user_folder = MARXAN_FOLDER + user + os.sep
    scenario_folder = user_folder + scenario + os.sep
    input_folder =  scenario_folder + "input" + os.sep
    output_folder = scenario_folder + "output" + os.sep
    return user_folder, scenario_folder, input_folder, output_folder
    
#creates the response payload by converting the dict to json, setting the response type and if necessary wrapping the response in a jsonp function to support asynchronous calls
def getResponse(params, response):
    #set the content type of the response
    web.header('Content-Type','application/json') 
    #convert the dict to json
    responseJson = json.dumps(response)
    #get the callback parameter for jsonp calls
    if "CALLBACK" in params.keys():
        return params["CALLBACK"] + "(" + responseJson + ")"
    else:
        return responseJson
    
def getUsers():
    #get a list of folders underneath the marxan home folder
    user_folders = glob.glob(MARXAN_FOLDER + "*/")
    #convert these into a list of users
    users = [user[:-1][user[:-1].rfind("/")+1:] for user in user_folders]
    if "input" in users: 
        users.remove("input")
    if "output" in users: 
        users.remove("output")
    return users

def getScenarios(user):
    #get a list of folders underneath the users home folder
    scenario_folders = glob.glob(MARXAN_FOLDER + user + os.sep + "*/")
    #sort the folders
    scenario_folders.sort()
    scenarios = []
    #iterate through the scenario folders and get the parameters for each scenario to return
    for dir in scenario_folders:
        #get the name of the folder 
        scenario = dir[:-1][dir[:-1].rfind("/")+1:]
        if (scenario[:2] != "__"): #folders beginning with __ are system folders
            #get the data from the input file
            s = readFile(dir + 'input.dat')
            #get the description
            desc = getInputParameter(dir + 'input.dat',"DESCRIPTION")
            createDate = getInputParameter(dir + 'input.dat',"CREATEDATE")
            #create a dict to save the data
            scenarios.append({'name':scenario,'description':desc,'createdate': createDate})
    return scenarios

def createEmptyScenario(input_folder, output_folder,scenario_folder, description):
    #create the scenario input and output folders
    os.makedirs(input_folder)
    os.makedirs(output_folder)
    #copy in the required files
    copyfile(MARXAN_FOLDER + 'input.dat.empty', scenario_folder + 'input.dat')
    #update the description and creation date parameters in the input.dat file
    updateParameters(scenario_folder + "input.dat", {'DESCRIPTION': description, 'CREATEDATE': datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")})

def checkScenarioExists(scenario_folder):
    if not (os.path.exists(scenario_folder)):
        raise MarxanServicesError("Scenario '" + scenario_folder[scenario_folder[:-1].rindex("/") + 1:-1] + "' does not exist")     

#reads in the text file and transforms the data so that each row has: <number of solutions>, <puid array>
def getVectorTileOptimisedOutput(csvFile, columnName):
    df= pandas.read_csv(csvFile).pivot(index=columnName,columns='planning_unit',values='planning_unit') #pivots the data
    transposed = df[df.columns].apply(lambda x: ','.join(x.dropna().astype(int).astype(str)),axis=1) #joins the multiple columns to produce a comma-separated string of PUIDs with the number
    arr = [[i,[int(n) for n in j.split(",")]] for (i,j) in transposed.items()][1:] #convert to an array of arrays and skip the first item as this one is all of the planning units which do not occur in any solution and dont need to be mapped
    return json.loads(json.dumps(arr))

#list users for the marxan server
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/listUsers?callback=__jp2
class listUsers():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            users = getUsers()
            response.update({'users':users})

        except (MarxanServicesError) as e: 
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#resends a users password
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/resendPassword?user=andrew&callback=__jp2
class resendPassword():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            
            #error checking
            if params["USER"] == "":
                raise MarxanServicesError("No user specified") 
                
            #read the password from the user.dat file
            password = getInputParameter(user_folder + "user.dat", "PASSWORD")
            
            #set the response
            response.update({'info': password})

        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#validates a user with the passed credentials
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/validateUser?user=andrew&password=thargal88&callback=__jp2
class validateUser():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            
            #error checking
            if "USER" not in params.keys():
                raise MarxanServicesError("No user specified") 
                
            #error checking
            if "PASSWORD" not in params.keys():
                raise MarxanServicesError("No password specified") 
                
            #check the user exists
            if not os.path.exists(user_folder):
                raise MarxanServicesError("Invalid login") 
            
            else:
                #read the password from the user.dat file
                password = getInputParameter(user_folder + "user.dat", "PASSWORD")
                
                #compare the two
                if params["PASSWORD"] == password:
                    #set the response
                    response.update({'info': "User " + params["USER"] + " validated"})
                #invalid login
                else:
                     raise MarxanServicesError("Invalid login")    

        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#create a new user for marxan server
class createUser():
    def POST(self):
        try:
            #there will be  variables in the data: 
            # user          = the user to create
            
            #get the data from the POST request
            data = web.input()

            #error checking
            for key in ["password", "name", "email", "mapboxaccesstoken"]:
                if key not in data.keys():
                    raise MarxanServicesError("No " + key + " parameter")

            #get the various folders
            user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
                        
            #get the users
            users = getUsers()
            
            #get the user to be created
            user = data.user
            
            #see if the user already exists
            if user in users:
                raise MarxanServicesError("User '" + user + "' already exists")
                
            #create the systems folders for the user
            if not os.path.exists(user_folder + "__shapefiles"):
                os.makedirs(user_folder + "__shapefiles")
            
            # if not os.path.exists(user_folder + "__shapefiles"):
            #     os.makedirs(user_folder + "__shapefiles")
            
            #create the folders for the PNG scenario and copy the input.dat file
            createEmptyScenario(input_folder, output_folder,scenario_folder,"Sample scenario for Papua New Guinea marine areas developed by The Nature Conservancy and the University of Queensland. For more information visit: http://www.environment.gov.au/marine/publications/national-marine-conservation-assessment-png")

            #copy the default user data
            copyfile(MARXAN_FOLDER + 'user.dat', user_folder + 'user.dat')

            #copy the sample scenario files into the input folder
            copyfile(MARXAN_INPUT_FOLDER + 'bound_png.dat', input_folder + 'bound_png.dat')
            copyfile(MARXAN_INPUT_FOLDER + 'pu_png.dat', input_folder + 'pu_png.dat')
            copyfile(MARXAN_INPUT_FOLDER + 'puvspr_png.dat', input_folder + 'puvspr_png.dat')
            copyfile(MARXAN_INPUT_FOLDER + 'spec_png.dat', input_folder + 'spec_png.dat')

            #update the input.dat file with information on the input files
            updateParameters(scenario_folder + "input.dat", {'PUNAME': 'pu_png.dat','SPECNAME': 'spec_png.dat','PUVSPRNAME': 'puvspr_png.dat','BOUNDNAME': 'bound_png.dat','MAPID': SAMPLE_TILESET_ID_PNG})

            #create another scenario for the marxan default data 
            data["scenario"] = "Marxan default scenario"
            user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)

            #create the folders for the PNG scenario and copy the input.dat file
            createEmptyScenario(input_folder, output_folder,scenario_folder,"Sample scenario using the Marxan sample data")
            
            #copy the sample scenario files into the input folder
            copyfile(MARXAN_INPUT_FOLDER + 'bound_orig.dat', input_folder + 'bound.dat')
            copyfile(MARXAN_INPUT_FOLDER + 'pu_orig.dat', input_folder + 'pu.dat')
            copyfile(MARXAN_INPUT_FOLDER + 'puvspr_orig.dat', input_folder + 'puvspr.dat')
            copyfile(MARXAN_INPUT_FOLDER + 'spec_orig.dat', input_folder + 'spec.dat')
            
            #update the input.dat file with information on the input files
            updateParameters(scenario_folder + "input.dat", {'PUNAME': 'pu.dat','SPECNAME': 'spec.dat','PUVSPRNAME': 'puvspr.dat','BOUNDNAME': 'bound.dat','MAPID': SAMPLE_TILESET_ID})

            #update the user.dat file with information from the POST request
            updateParameters(user_folder + "user.dat", {'NAME': data.name,'EMAIL': data.email,'PASSWORD': data.password,'MAPBOXACCESSTOKEN': data.mapboxaccesstoken})
            
            #write the response
            response = {'info': "User '" + user + "' created"}
            
        except (MarxanServicesError) as e:
            response = {'error': e.message}

        finally:
            return getResponse({}, response)
    
#gets a users information from the user folder
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/getUser?user=andrew&callback=__jp2
class getUser():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            
            #error checking
            if "USER" not in params.keys():
                raise MarxanServicesError("No user specified")     
                
            if not os.path.exists(user_folder):
                raise MarxanServicesError("User does not exist")     
            
            #get the users data
            userData = getUserData(user_folder + "user.dat")
            
            #set the response
            response.update({'info': "User data received", "userData" : userData})

        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#updates the user data in the user.dat file with the passed parameters
class updateUser:
    def POST(self):
        try:
            #there will be 5 variables in the data: 
            # user          = the currently logged on user
            data = web.input()

            #error check 
            if "user" not in data.keys():
                raise MarxanServicesError("No user parameter") 
                
            #get the appropriate folders
            user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
            
            #set the parameters in the user.dat file
            updateParameters(user_folder + "user.dat", data)
            
            # #write the response
            response = {'info': "User information saved"}
            
        except (MarxanServicesError) as e:
            response = {'error':  e.message}

        finally:
            return getResponse({}, response)

#list scenarios for the specific user
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/listScenarios?user=andrew&callback=__jp2
class listScenarios():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            scenarios = getScenarios(params["USER"])
            response.update({'scenarios':scenarios})

        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)
          
#loads all of the data for the scenario and returns the files and the run parameters as separate arrays
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/getScenario?user=andrew&scenario=Sample%20scenario&callback=__jp2
class getScenario():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            checkScenarioExists(scenario_folder)                

            #open the input.dat file to get all of the scenario files, parameters and metadata
            files, runParams, metadata, renderer = getInputParameters(scenario_folder + "input.dat")
            #set the response
            response.update({'scenario':params['SCENARIO'],'metadata':metadata, 'files':files, 'runParameters':runParams, 'renderer': renderer})
            
            #set the users last scenario so it will load on login
            updateParameters(user_folder + "user.dat", {'LASTSCENARIO': params['SCENARIO']})

        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#creates a new scenario in the users folder
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/createScenario?user=andrew&scenario=test2&description=Groovy%20description&callback=__jp2
class createScenario():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])

            #check the scenario doesnt already exist
            if (os.path.exists(scenario_folder)):
                raise MarxanServicesError("Scenario '" + params["SCENARIO"] + "' already exists") 

            #get the description
            if "DESCRIPTION" in params.keys():
                description = params["DESCRIPTION"]
            else:
                description = "No description"

            #create the folders for the scenario and copy the input.dat file
            createEmptyScenario(input_folder, output_folder,scenario_folder, description)

            #set the response
            response.update({'info': "Scenario '" + params["SCENARIO"] + "' created", 'name': params["SCENARIO"], 'description': description})

        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)
        
#deletes the named scenario in the users folder
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/deleteScenario?user=andrew&scenario=test2&callback=__jp2
class deleteScenario():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            checkScenarioExists(scenario_folder)                

            #get the scenarios
            scenarios = getScenarios(params["USER"])
            if len(scenarios) == 1:
                raise MarxanServicesError("You cannot delete all scenarios")     
            #delete the folder and all of its contents
            shutil.rmtree(scenario_folder)
            #set the response
            response.update({'info': "Scenario '" + params["SCENARIO"] + "' deleted", 'scenario': params["SCENARIO"]})

        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#https://db-server-blishten.c9users.io/marxan/webAPI2.py/renameScenario?user=asd&scenario=wibble&newName=wibble2&callback=__jp2
class renameScenario():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            checkScenarioExists(scenario_folder)                
            
            #error checking
            if params["NEWNAME"] == "":
                raise MarxanServicesError("No name specified")     

            #rename the folder
            os.rename(scenario_folder, user_folder + params["NEWNAME"])

            #add the other items to the response
            response.update({"info": "Scenario renamed to '" + params["NEWNAME"] + "'", 'scenario':params["NEWNAME"]})
            
            #set the new name as the users last scenario so it will load on login
            updateParameters(user_folder + "user.dat", {'LASTSCENARIO': params['NEWNAME']})
            
        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#https://db-server-blishten.c9users.io/marxan/webAPI2.py/renameDescription?user=andrew&scenario=Sample%20scenario&newDesc=wibble2&callback=__jp2
class renameDescription():
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            checkScenarioExists(scenario_folder)                
            
            #error checking
            if params["NEWDESC"] == "":
                raise MarxanServicesError("No new description specified")     

            #update the description
            updateParameters(scenario_folder + "input.dat", {'DESCRIPTION': params["NEWDESC"]})
            
            #add the other items to the response
            response.update({"info": "Description updated", 'description':params["NEWDESC"]})
            
        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#updates the run parameters for the passed user/scenario 
class updateRunParams:
    def POST(self):
        try:
            data = web.input()
            #error check 
            if "user" not in data.keys():
                raise MarxanServicesError("No user parameter") 
                
            #error check 
            if "scenario" not in data.keys():
                raise MarxanServicesError("No scenario parameter") 
                
            #get the appropriate folders
            user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
            
            #set the parameters in the user.dat file
            updateParameters(scenario_folder + "input.dat", data)
            
            # #write the response
            response = {'info': "Run parameters saved"}
            
        except (MarxanServicesError) as e:
            response = {'error':  e.message}

        finally:
            return getResponse({}, response)

#runs marxan 
    #https://db-server-blishten.c9users.io/marxan/webAPI/runMarxan?user=asd2&scenario=Marxan%20default%20scenario&callback=__jp2
class runMarxan:
    def GET(self):
        try:
            #initialise the logging
            logging.basicConfig(filename='/home/ubuntu/lib/apache2/log/error.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
            logging.info("Marxan request started")
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            #update the run parameters in the input.dat file using the passed query parameters
            updateParameters(scenario_folder + "input.dat", params)
            #set the current folder to the scenario folder so files can be found in the input.dat file
            os.chdir(scenario_folder) 
            #delete all of the current output files
            deleteAllFiles(output_folder)
            #run marxan 
            p = subprocess.call(MARXAN_EXECUTABLE, stdout=subprocess.PIPE) 

        except:
            response.update({'error': sys.exc_info()[0]})
            
        finally:
            return getResponse(params, response)

#polls the server for the results of a marxan run and if complete returns the sum of solutions, summary info on all runs and the log
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/pollResults?user=asd2&scenario=Marxan%20default%20scenario&numreps=10&returnall=false&callback=__jp2
class pollResults:
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            if "NUMREPS" not in params.keys():
                raise MarxanServicesError("No numreps parameter")
            
            if "CHECKFOREXISTINGRUN" not in params.keys():
                raise MarxanServicesError("No checkForExistingRun parameter")

            #see how many runs have been completed
            runsCompleted = len(glob.glob(output_folder + "output_r*"))
            
            #if complete then return the data
            if runsCompleted == int(params['NUMREPS']):
                
                #log
                logging.info("Marxan request finished")
                
                #read the log from the log file
                log = readFile(output_folder + "output_log.dat")
                
                #read the data from the text file
                sum = pandas.read_csv(output_folder + "output_sum.txt").to_json(orient='values') 
                
                #get the summed solution as a json string
                ssoln = getVectorTileOptimisedOutput(output_folder + "output_ssoln.txt", "number")

                #get the info message to return
                if params["CHECKFOREXISTINGRUN"] == "true":
                    info = "Existing results loaded"
                else:
                    info = "Run succeeded"
                
                #add the other items to the response
                response.update({'info':info, 'log': log, 'sum':json.loads(sum),'ssoln': ssoln})
        
            else:
                #return the number of runs completed
                response.update({'info': str(runsCompleted) + " runs completed", 'runsCompleted': runsCompleted})
            
        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        except:
            "Unexpected error:", sys.exc_info()[0]
            
        finally:
            return getResponse(params, response)        

#for loading each individual solutions data
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/loadSolution?user=andrew&scenario=Sample%20scenaio&solution=1&callback=__jp2
class loadSolution:
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            if "SOLUTION" not in params.keys():
                raise MarxanServicesError("No solution parameter")
                
            #get the content from the solution - this will be 'output_r00001.txt'
            solutionFile = output_folder + "output_r" + "%05d" % (int(params["SOLUTION"]),)  + ".txt"
            try:
                solution = getVectorTileOptimisedOutput(solutionFile, "solution")
                
            except (IOError):
                raise MarxanServicesError("Solution not found")
                
            response.update({'solution': solution})
                
        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#saves an uploaded file to the input folder where it can be used in the marxan run
class postFile:
    def POST(self):
        try:
            #there will be 5 variables in the data: 
            # parameter    = the type of marxan file being uploaded (SPECNAME, PUNAME, PUVSPRNAME, BOUNDNAME, BLOCKDEFNAME)
            # value         = the content of the file
            # filename      = the filename of the uploaded file
            # user          = the currently logged on user
            # scenario      = the scenario name
            data = web.input()

            #get the appropriate folders
            user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
            
            #write the file to the input folder
            writeFile(input_folder + data.filename, data.value)
            
            #set the parameter in the input.dat file
            updateParameters(scenario_folder + "input.dat", {data.parameter: data.filename})
            
            #write the response
            response = {'info': "File '" + data.filename + "' uploaded", 'file': data.filename}
            
        except (MarxanServicesError) as e:
            response = {'error': e.message}

        finally:
            return getResponse({}, response)

#updates a parameter in the input.dat file directly, e.g. for updating the MAPID after the user sets their source spatial data
    #https://db-server-blishten.c9users.io/marxan/webAPI2.py/updateParameter?user=andrew&scenario=Sample%20scenario&parameter=MAPID&value=wibble&callback=__jp2
class updateParameter:
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            if "USER" not in params.keys():
                raise MarxanServicesError("No user parameter")
            if "SCENARIO" not in params.keys():
                raise MarxanServicesError("No scenario parameter")
            if "PARAMETER" not in params.keys():
                raise MarxanServicesError("No parameter name")
            if "VALUE" not in params.keys():
                raise MarxanServicesError("No parameter value")
            updateParameters(scenario_folder + "input.dat", {params["PARAMETER"]: params["VALUE"]})
            response.update({'info': "Parameter updated"})
            
        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

#creates a hexagon grid on the server to use for partitioning the area of interest into hexagons
    #https://db-server-blishten.c9users.io/marxan/webAPI.py/createPlanningUnitsGrid?user=andrew&scenario=Sample%20scenario2&type=hexagon&area=50000000&minx=13405242.3514&miny=-1872878.36099&maxx=15678140.8211&maxy=333209.676673&name=test_hexagon
class createPlanningUnitsGrid:
    def GET(self):
        try:
            #initialise the request objects
            user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
            if "USER" not in params.keys():
                raise MarxanServicesError("No user parameter")
            if "SCENARIO" not in params.keys():
                raise MarxanServicesError("No scenario parameter")
            if "TYPE" not in params.keys():
                raise MarxanServicesError("No type parameter")
            if "AREA" not in params.keys():
                raise MarxanServicesError("No area parameter")
            if "MINX" not in params.keys():
                raise MarxanServicesError("No minx parameter")
            if "MINY" not in params.keys():
                raise MarxanServicesError("No miny parameter")
            if "MAXX" not in params.keys():
                raise MarxanServicesError("No maxx parameter")
            if "MAXY" not in params.keys():
                raise MarxanServicesError("No maxy parameter")
            if "NAME" not in params.keys():
                raise MarxanServicesError("No name parameter")
            
            #create the grid
            msg = spatialServer.CreatePUGrid(params["TYPE"],float(params["AREA"]),float(params["MINX"]),float(params["MINY"]),float(params["MAXX"]),float(params["MAXY"]),params["NAME"])

            #return the response
            response.update({'info': msg})
            
        except (MarxanServicesError) as e:
            response.update({'error': e.message})

        finally:
            return getResponse(params, response)

app = web.application(urls, locals()) 
web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)

if __name__ == "__main__":
    app.run()