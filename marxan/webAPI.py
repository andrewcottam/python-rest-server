#!/home/ubuntu/miniconda2/bin/python
#the above line forces the CGI script to use the Anaconda Python interpreter
import sys, os, web, subprocess, urllib, pandas, json, glob, shutil, re, datetime, logging, CustomExceptionClasses, shapefile, math, psycopg2, zipfile, commands, numpy
from collections import OrderedDict
from shutil import copyfile
from CustomExceptionClasses import MarxanServicesError
from pandas.io.sql import DatabaseError
from mapbox import Uploader
from mapbox import errors

MAPBOX_ACCESS_TOKEN = "sk.eyJ1IjoiYmxpc2h0ZW4iLCJhIjoiY2piNm1tOGwxMG9lajMzcXBlZDR4aWVjdiJ9.Z1Jq4UAgGpXukvnUReLO1g"
MARXAN_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/"
MARXAN_COUNTRY_SHAPEFILE_FOLDER = "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/input_shapefiles"
MARXAN_EXECUTABLE = MARXAN_FOLDER + "MarOpt_v243_Linux64"
MARXAN_OUTPUT_FOLDER = MARXAN_FOLDER + "output" + os.sep 
MARXAN_INPUT_PARAMETER_FILENAME = MARXAN_FOLDER + "input.dat"
MARXAN_INPUT_FOLDER = MARXAN_FOLDER + "input" + os.sep
SAMPLE_TILESET_ID = "blishten.3ogmvag8" #this is the sample data that comes with marxan and consists of a grid of 100 planning units
SAMPLE_TILESET_ID_PNG = "blishten.pulayer_costt" #png example
ISO3_FIELD_NAME = "iso3"
PLANNING_UNIT_GRID_NAME = "grid"
FEATURE_PREPROCESSING_FILENAME = "feature_preprocessing.dat"
PROTECTED_AREA_INTERSECTIONS_FILENAME = "protected_area_intersections.dat"

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
  "/createScenarioFromWizard", "createScenarioFromWizard",
  "/cloneScenario", "cloneScenario",
  "/deleteScenario", "deleteScenario",
  "/renameScenario", "renameScenario",
  "/renameDescription", "renameDescription",
  "/updateRunParams","updateRunParams",
  "/runMarxan", "runMarxan", 
  "/pollResults","pollResults",
  "/loadSolution", "loadSolution", 
  "/postFile","postFile",
  "/postFileWithFolder","postFileWithFolder",
  "/postShapefile","postShapefile",
  "/importShapefile","importShapefile",
  "/updateParameter","updateParameter",
  "/uploadTilesetToMapBox","uploadTilesetToMapBox",
  "/deleteInterestFeature","deleteInterestFeature",
  "/updateSpecFile","updateSpecFile",
  "/preprocessFeature","preprocessFeature",
  "/getPlanningUnitGrids","getPlanningUnitGrids",
  "/updatePlanningUnitStatuses","updatePlanningUnitStatuses",
  "/getPAIntersections","getPAIntersections"
  )

def log(message, messageType=0):
	#messageTypes are 0: normal, 1: start a new block, 2: end a block
	if messageType!=0:
		if messageType == 1:
			logtext = "\n" + ("=" * 100) + "\n" + message
		else:
			logtext = message + "\n" + ("=" * 100)
	else:
		logtext = message
	logging.info(logtext)
	
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

#there are some characters in the log file which cause the json parser to fail - this functions removes them
def cleanLog(log):
	return log.replace("\x90","")
	
def createZipfile(lstFileNames, folder, zipfilename):
	with zipfile.ZipFile(folder + zipfilename, 'w') as myzip:
	    for f in lstFileNames:   
	        arcname = os.path.split(f)[1]
	        myzip.write(f,arcname)
	        
#deletes a zip file and the archive files, e.g. deleteZippedShapefile(MARXAN_FOLDER, "/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/pu_asm_terrestrial_hexagons_50.zip", "pngprov")
def deleteZippedShapefile(folder, zipfilename, archivename):
	os.remove(zipfilename)	
	files = glob.glob(folder + archivename + '.*')
	if len(files)>0:
		[os.remove(f) for f in files]       
	
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
	matches = re.findall('\\n[A-Z1-9_]{2,}', s, re.DOTALL)
	return [m[1:] for m in matches]
  
#create the array of the puids 
def puidsArrayToPuDatFormat(puid_array, pu_status):
	return pandas.DataFrame([[int(i),pu_status] for i in puid_array], columns=['id','status_new']).astype({'id':'int64','status_new':'int64'})

def updatePuValues(csvFile, status1_ids, status2_ids, status3_ids):
	status1 = puidsArrayToPuDatFormat(status1_ids,1)
	status2 = puidsArrayToPuDatFormat(status2_ids,2)
	status3 = puidsArrayToPuDatFormat(status3_ids,3)
	log (status1)
	log (status2)
	log (status3)
	#read the data from the pu.dat file 
	df = pandas.read_csv(csvFile)
	
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
	
	#write to file
	df.to_csv(csvFile, sep=',',index =False)
	
def getUserData(filename):
	log("getUserData for " + filename)
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
	log("getInputParameters for " + filename)
	#instantiate the return arrays
	paramsArray = []
	filesDict = {}
	metadataDict = {}
	rendererDict = {}
	#get the file contents
	s = readFile(filename)
	#get the keys from the file
	keys = getKeys(s)
	log("Input parameters: " + ",".join(keys))
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
						
	return filesDict, paramsArray, metadataDict, rendererDict
	
#updates the parameters in the *.dat file with the new parameters passed as a dict
def updateParameters(data_file, newParams):
	log("updateParameters for data_file: " + data_file) 
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

def deleteAllFiles(folder):
	log("deleteAllFiles")
	files = glob.glob(folder + "*")
	for f in files:
		os.remove(f)

#writes the dataframe to the dat file - appending it if it already exists
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
	df.to_csv(file, index =False)

#initialises the rest request and response from a GET request
# 1. initialises a response dict which is used to populate the response information
# 2. gets the request parameters as a dictionary which are passed as query parameters
# 3. sets the user, scenario, input and output folders for the user 
def initialiseGetRequest(queryString):
	log("initialiseGetRequest with queryString: " + queryString)
	#initialise the response dictionary
	response = {}
	#get the parameters to pass on to marxan
	params = getQueryStringParams(queryString)
	#get the user, input and output folders
	params.setdefault('USER','') # set to an empty string if it is not passed, e.g. in getUsers, createUsers etc.
	params.setdefault('SCENARIO','Sample case study') # set to a sample string if it is not passed, e.g. in getUsers, createUsers etc.
	user_folder, scenario_folder, input_folder, output_folder = getFolders(params['USER'], params['SCENARIO'])
	# log("user_folder: " + user_folder)
	# log("scenario_folder: " + scenario_folder)
	# log("input_folder: " + input_folder)
	# log("output_folder: " + output_folder)
	return user_folder, scenario_folder, input_folder, output_folder, response, params

#initialises the folders from a POST request
def initialisePostRequest(data):
	try:
		#check the user parameter
		if not ("user" in data.keys()):
			raise MarxanServicesError("No user parameter found")

		#check the scenario parameter - if none is passed then set a default = some updates dont pass a scenario, e.g. updateUser, createUser etc
		if not ("scenario" in data.keys()):
			scenario = "Sample case study"
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
	try:
		#set the content type of the response
		web.header('Content-Type','application/json') 
		#convert the dict to json
		responseJson = json.dumps(response)
		log("RESPONSE: " + responseJson[:100], 2)
		#get the callback parameter for jsonp calls
		if "CALLBACK" in params.keys():
			return params["CALLBACK"] + "(" + responseJson + ")"
		else:
			return responseJson
			
	except (UnicodeDecodeError) as e:
		return {'error': e}
		
	
def getUsers():
	log("getUsers")
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
	log("getScenarios for user: " + user)
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
			oldVersion = getInputParameter(dir + 'input.dat',"OLDVERSION")
			#create a dict to save the data
			scenarios.append({'name':scenario,'description':desc,'createdate': createDate,'oldVersion':oldVersion})
	return scenarios

def createEmptyScenario(input_folder, output_folder,scenario_folder, description):
	log("createEmptyScenario")
	#create the scenario input and output folders
	os.makedirs(input_folder)
	os.makedirs(output_folder)
	#copy in the required files
	copyfile(MARXAN_FOLDER + 'input.dat.empty', scenario_folder + 'input.dat')
	#update the description and creation date parameters in the input.dat file
	updateParameters(scenario_folder + "input.dat", {'DESCRIPTION': description, 'CREATEDATE': datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")})

def checkScenarioExists(scenario_folder):
	log("checkScenarioExists: " + scenario_folder)
	if not (os.path.exists(scenario_folder)):
		raise MarxanServicesError("Scenario '" + scenario_folder[scenario_folder[:-1].rindex("/") + 1:-1] + "' does not exist")     


#creates the pu.dat file using the passed paramters - used in the web API and internally in the createScenarioFromWizard function
def _createPUdatafile(scenario_folder, input_folder, planning_grid_name):
	#create the pu.dat file
	try:
		log("_createPUdatafile")
		log("Creating pu.dat file in folder '" + input_folder + "' using planning grid name '" + planning_grid_name + "'")
		
		#connect to the db
		conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
		cur = conn.cursor()

		#run the query to create the pu.dat file
		with open(input_folder + 'pu.dat', 'w') as f:
		    cur.copy_expert("COPY (SELECT puid as id,1::double precision as cost,0::integer as status FROM marxan." + planning_grid_name + ") TO STDOUT WITH CSV HEADER;", f)

		log("pu.dat file created in folder " + input_folder)
		
	except (psycopg2.InternalError, psycopg2.IntegrityError, IOError) as e: #postgis error
		raise MarxanServicesError("Error creating pu.dat file: " + e.message)
		
	finally:
		cur.close() 
		conn.commit()
		conn.close()
	
	#update the input.dat file
	updateParameters(scenario_folder + "input.dat", {'PUNAME': 'pu.dat'})

def _updatePUdatafile(input_folder, id_values, cost_values, status_values):
	try:
		log("_updatePUdatafile")
		ids = id_values.split(",")
		costs = cost_values.split(",") 
		statuses = status_values.split(",") 

		#open the file writer
		file = open(input_folder  + "pu.dat","w") 
		file.write('id,cost,status\n')
		
		#write the pu data to file
		for i in range(len(ids)):
			file.write(ids[i] + "," + costs[i] + "," + statuses[i] + "\n")
		file.close()
		log("pu.dat file updated")

	except (MarxanServicesError) as e: 
		raise e.message
		
	finally:
		return ""	

#creates the spec.dat file using the passed paramters - used in the web API and internally in the createScenarioFromWizard function
def _updateSPECdatafile(scenario_folder, input_folder, interest_features, target_values, spf_values):
	#update the spec.dat file
	try:
		ids = interest_features.split(",")
		log("Updating spec.dat file using interest features " + ",".join([str(i) for i in ids]))
		ids = [int(id) for id in ids]
		props = target_values.split(",") 
		spfs = spf_values.split(",") 

		#get the data from the spec.dat file
		df = getSpecDatData(input_folder, scenario_folder)
		
		#get all the species that are no longer in the scenario
		df = getSpecDatData(input_folder, scenario_folder)
		oldsIds = df.id.unique().tolist() 
		removedIds = list(set(oldsIds) - set(ids))

		log("Removing features " + ",".join([str(i) for i in removedIds]))

		#update the puvspr.dat file to remove any species that are no longer in the scenario
		if len(removedIds) > 0:
			
			#get the name of the puvspr file from the input.dat file
			puvsprname = getInputParameter(scenario_folder + 'input.dat',"PUVSPRNAME")
			if (puvsprname) and (os.path.exists(input_folder + puvsprname)):

				#if the file exists then get the existing data
				df2 = pandas.read_csv(input_folder + puvsprname)

				#remove the species records for those species that are no longer in the scenario
				df2 = df2[~df2.species.isin(removedIds)]

				#write the results to the puvspr.dat file
				df2.to_csv(input_folder + puvsprname, index =False)
	
			#update the preprocessing.dat file to remove any species that are no longer in the scenario - these will need to be preprocessed again
			if (os.path.exists(input_folder + FEATURE_PREPROCESSING_FILENAME)):
				
				#if the file exists then get the existing data
				df2 = pandas.read_csv(input_folder + FEATURE_PREPROCESSING_FILENAME)
				
				#remove the feature records for those features that are no longer in the scenario
				df2 = df2[~df2.id.isin(removedIds)]

				#write the results to the puvspr.dat file
				log("writing the preprocessing file")
				log(df2)
				df2.to_csv(input_folder + FEATURE_PREPROCESSING_FILENAME, index =False)
		
		#open the file writer
		file = open(input_folder  + "spec.dat","w") 
		file.write('id,prop,spf\n')
		
		#write the spec data to file
		for i in range(len(ids)):
			if i not in removedIds:
				file.write(str(ids[i]) + "," + str(float(props[i])/100) + "," + spfs[i] + "\n")
				
		file.close()
		log("spec.dat file created")
			
	except (MarxanServicesError) as e: 
		log(e.message)
		
	finally:
		#update the input.dat file
		updateParameters(scenario_folder + "input.dat", {'SPECNAME': 'spec.dat'})

def getSpecDatData(input_folder, scenario_folder):

	#get the name of the spec.dat file
	specname = getInputParameter(scenario_folder + 'input.dat',"SPECNAME")

	#get the values from the spec.dat file
	df = pandas.read_csv(input_folder + specname)
	
	#test the spec.dat file is not empty
	if (df.empty):
		raise MarxanServicesError("There are no conservation features")

	return df

#returns the following
#[{"description": "Groovy", "feature_class_name": "seagrasses_pacific", "creation_date": "2018-08-29 12:30:09.836061", "alias": "Pacific Seagrasses", "target_value": 70, "id": 63407942, "spf": 40}, {"description": "Groovy", "feature_class_name": "png2", "creation_date": "2018-08-29 12:30:09.836061", "alias": "Pacific Coral Reefs", "target_value": 80, "id": 63408006, "spf": 40}]
def _getInterestFeaturesForScenario(scenario_folder,input_folder, web_call):
	#set web_call to True if the results will be transformed for a webclient, e.g. in spec.dat the target_value is called 'prop'
	try:
		log("_getInterestFeaturesForScenario: " + input_folder)
		
		#get the data from the spec.dat file
		df = getSpecDatData(input_folder, scenario_folder)
		
		try:
			#connect to the db
			conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
			
			#get the values from the marxan.metadata_interest_features table using the get_interest_features function
			df2 = pandas.read_sql_query('select * from marxan.get_interest_features()',con=conn)   

			#join the dataframes using the id field as the key from the spec.dat file and the oid as the key from the metadata_interest_features table
			output_df = df.set_index("id").join(df2.set_index("oid"))

			# #get the name of the puvspr file from the input.dat file
			# puvsprname = getInputParameter(scenario_folder + 'input.dat',"PUVSPRNAME")

			# #if it is a new scenario there may not be an entry in the input.dat file for PUVSPRNAME or the file may not exist
			# if (puvsprname) and (os.path.exists(input_folder + puvsprname)):
				
			# 		#if the file exists then get the species that have already been processed
			# 		df2 = pandas.read_csv(input_folder + puvsprname)
			# 		#get the unique species ids 
			# 		processed_ids = df2.species.unique()
			# else:
			# 	processed_ids = []			
			
			# #set the default value for preprocessed as False
			# output_df['preprocessed'] = False
			
			# #set the preprocessed value to True where the id is in the puvspr file
			# output_df.loc[output_df.index.isin(processed_ids),['preprocessed']] = True
			
			#add the index as a column
			output_df['oid'] = output_df.index
			#if the scenario is imported from the desktop version of Marxan then add default values for those properties that dont exist, e.g. description, feature_class_name, creation_date, alias
			if (pandas.isnull(output_df.iloc[0]['feature_class_name'])): #test for a feature_class_name value which wont exist if it is a marxan desktop database
				log("Scenario is imported from Marxan Desktop - adding default values")
				output_df['tmp'] = 'Unique identifer: '
				output_df['alias'] = output_df['tmp'].str.cat((output_df['oid']).apply(str)) # 'Unique identifer: 4702435'
				output_df['feature_class_name'] = output_df['oid']
				output_df['description'] = "No description"
				output_df = output_df[["description", "feature_class_name", "creation_date", "alias", "prop", "spf", "oid"]]
			
			if (web_call):
				#rename the columns that are sent back to the client as the names of various properties are different in Marxan compared to the web client
				output_df = output_df.rename(index=str, columns={'prop': 'target_value', 'oid':'id'})    
			
				#get the target as an integer - Marxan has it as a percentage, i.e. convert 0.17 -> 17
				output_df['target_value'] = (output_df['target_value'] * 100).astype(int)
		
		except (DatabaseError, psycopg2.InternalError, psycopg2.IntegrityError) as e: #postgis error
			raise MarxanServicesError("Error getting interest features for scenario: " + e.message)
		
		finally:
			conn.close()

	except Exception: #general error if the input_folder doesnt exist
		raise 

	return output_df #return a pandas dataframe	
	
#converts a data frame with duplicate values into a normalised array
def normaliseDataFrame(df, columnToNormaliseBy, puidColumnName):
	#get the groups from the data
	groups = df.groupby(by = columnToNormaliseBy).groups
	
	#build the response, e.g. a normal data frame with repeated values in the columnToNormaliseBy -> [["VI", [7, 8, 9]], ["IV", [0, 1, 2, 3, 4]], ["V", [5, 6]]]
	response = [[g, df[puidColumnName][groups[g]].values.tolist()] for g in groups if g not in [0]]
	return response

#gets the intersection between the passed grid and the countries protected areas (with iucn categories)
def _getPAIntersections(input_folder):
	
	#see if the intersections file already exists
	if (os.path.exists(input_folder + PROTECTED_AREA_INTERSECTIONS_FILENAME)):
		df = pandas.read_csv(input_folder + PROTECTED_AREA_INTERSECTIONS_FILENAME)
		return normaliseDataFrame(df, "iucn_cat", "puid")

	else:
		return None

##############################################################################################################################################################################################################################################
#################  MapBox routines
##############################################################################################################################################################################################################################################

#uploads a tileset to mapbox using the filename of the file (filename) to upload and the name of the resulting tileset (_name)
def uploadTileset(filename, _name):
	log("Uploading to MapBox: " + filename + " " + _name)
	#create an instance of the upload service
	service = Uploader(access_token=MAPBOX_ACCESS_TOKEN)	
	with open(filename, 'rb') as src:
		upload_resp = service.upload(src, _name)
		upload_id = upload_resp.json()['id']
		return upload_id
		
#uploads a feature class with the passed feature class name to MapBox as a tileset using the MapBox Uploads API
class uploadTilesetToMapBox():
	def GET(self):
		try:
			log("uploadTilesetToMapBox",1)
			#error checking
			params = getQueryStringParams(web.ctx.query[1:])
			response = {}
			if "FEATURE_CLASS_NAME" not in params.keys():
				raise MarxanServicesError("No feature_class_name specified") 
			if "MAPBOX_LAYER_NAME" not in params.keys():
				raise MarxanServicesError("No mapbox_layer_name specified") 

			#get the feature class name
			feature_class_name = params["FEATURE_CLASS_NAME"]
			
			#get the mapbox layer name
			mapbox_layer_name = params["MAPBOX_LAYER_NAME"]
			
			#create the file to upload to MapBox - now using shapefiles as kml files only import the name and description properties into a mapbox tileset
			log("Uploading " + feature_class_name + " to MapBox")
			outputFile = MARXAN_FOLDER + feature_class_name + '.shp'
			cmd = '/home/ubuntu/anaconda2/bin/ogr2ogr -f "ESRI Shapefile" ' + outputFile + ' "PG:host=localhost dbname=biopama user=jrc password=thargal88" -sql "select * from Marxan.' + feature_class_name + '" -nln ' + mapbox_layer_name + ' -s_srs EPSG:3410 -t_srs EPSG:3857'
			os.system(cmd)

			#zip the shapefile to upload to Mapbox
			lstFilenames = glob.glob(MARXAN_FOLDER + feature_class_name + '.*')
			zipfilename = MARXAN_FOLDER + feature_class_name + ".zip"
			log("Zipping the shapefile '" + zipfilename + "'")
			createZipfile(lstFilenames, MARXAN_FOLDER, feature_class_name + ".zip")
			
			#upload to mapbox
			uploadId = uploadTileset(zipfilename, feature_class_name)
			#set the response for uploading to mapbox
			response.update({'info': "Tileset '" + feature_class_name + "' uploading",'uploadid': uploadId})

			#delete the temporary shapefile file and zip file
			log("Deleting zip file: " + zipfilename)
			deleteZippedShapefile(MARXAN_FOLDER, zipfilename, feature_class_name)
			
		except Exception as inst: #handles all errors TODO: Modify all other error handlers to use this approach
			response.update({'error': str(inst)})

		finally:
			return getResponse(params, response)
			

##############################################################################################################################################################################################################################################
#################  End of MapBox routines
##############################################################################################################################################################################################################################################


#list users for the marxan server
	#https://db-server-blishten.c9users.io/marxan/webAPI2.py/listUsers?callback=__jp2
class listUsers():
	def GET(self):
		try:
			log("listUsers",1)
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
			log("resendPassword",1)
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
			log("Validating user",1)
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
			log("createUser",1)
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
			log("see if the user already exists")
			if user in users:
				raise MarxanServicesError("User '" + user + "' already exists")
				
			#create the folders for the PNG scenario and copy the input.dat file
			log("create the folders for the PNG scenario and copy the input.dat file")
			createEmptyScenario(input_folder, output_folder,scenario_folder,"Sample case study for Papua New Guinea marine areas developed by The Nature Conservancy and the University of Queensland. For more information visit: http://www.environment.gov.au/marine/publications/national-marine-conservation-assessment-png")

			#copy the default user data
			copyfile(MARXAN_FOLDER + 'user.dat', user_folder + 'user.dat')

			#copy the sample scenario files into the input folder
			copyfile(MARXAN_INPUT_FOLDER + 'bound_png.dat', input_folder + 'bound_png.dat')
			copyfile(MARXAN_INPUT_FOLDER + 'pu_png.dat', input_folder + 'pu_png.dat')
			copyfile(MARXAN_INPUT_FOLDER + 'puvspr_png.dat', input_folder + 'puvspr_png.dat')
			copyfile(MARXAN_INPUT_FOLDER + 'spec_png.dat', input_folder + 'spec_png.dat')

			#update the input.dat file with information on the input files
			updateParameters(scenario_folder + "input.dat", {'PUNAME': 'pu_png.dat','SPECNAME': 'spec_png.dat','PUVSPRNAME': 'puvspr_png.dat','BOUNDNAME': 'bound_png.dat','PLANNING_UNIT_NAME': SAMPLE_TILESET_ID_PNG})

			#create another scenario for the marxan default data 
			log("create another scenario for the marxan default data")
			data["scenario"] = "Marxan default"
			user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)

			#create the folders for the PNG scenario and copy the input.dat file
			createEmptyScenario(input_folder, output_folder,scenario_folder,"Sample case study using the Marxan sample data")
			
			#copy the sample scenario files into the input folder
			copyfile(MARXAN_INPUT_FOLDER + 'bound_orig.dat', input_folder + 'bound.dat')
			copyfile(MARXAN_INPUT_FOLDER + 'pu_orig.dat', input_folder + 'pu.dat')
			copyfile(MARXAN_INPUT_FOLDER + 'puvspr_orig.dat', input_folder + 'puvspr.dat')
			copyfile(MARXAN_INPUT_FOLDER + 'spec_orig.dat', input_folder + 'spec.dat')
			
			#update the input.dat file with information on the input files
			updateParameters(scenario_folder + "input.dat", {'PUNAME': 'pu.dat','SPECNAME': 'spec.dat','PUVSPRNAME': 'puvspr.dat','BOUNDNAME': 'bound.dat','PLANNING_UNIT_NAME': SAMPLE_TILESET_ID})

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
			log("getUser",1)
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
			log("updateUser",1)
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
			log("listScenarios",1)
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			scenarios = getScenarios(params["USER"])
			response.update({'scenarios':scenarios})

		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse(params, response)
		  
#loads all of the data for the scenario and returns the files and the run parameters as separate arrays
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/pollResults?user=andrew&scenario=Tonga%20marine%20new&numreps=10&checkForExistingRun=true&callback=__jp13
class getScenario():
	def GET(self):
		try:
			log("getScenario",1)
			#get a connection to the database
			conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
			
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			checkScenarioExists(scenario_folder)                

			#open the input.dat file to get all of the scenario files, parameters and metadata
			files, runParams, metadata, renderer = getInputParameters(scenario_folder + "input.dat")
			
			#get the interest features for this scenario 
			features = json.loads(_getInterestFeaturesForScenario(scenario_folder,input_folder, True).to_json(orient='records'))
			
			#get all the interest features - these will be returned even for marxan desktop databases which have no records in the metadata_interest_features table
			df = pandas.read_sql_query("SELECT oid::integer as id, creation_date, feature_class_name, alias, _area area, description FROM marxan.metadata_interest_features order by alias;", con=conn)
			allfeatures = json.loads(df.to_json(orient='records'))

			#get the feature preprocessing state
			if (os.path.exists(input_folder + FEATURE_PREPROCESSING_FILENAME)):
				preprocessing = json.loads(pandas.read_csv(input_folder + FEATURE_PREPROCESSING_FILENAME).to_json(orient='values')) 
			else:
				preprocessing = []
			
			#get the planning unit data
			df = pandas.read_csv(input_folder + "pu.dat")
			pu_data = normaliseDataFrame(df, "status", "id")
			
			#get the protected area intersections
			protected_area_intersections = _getPAIntersections(input_folder)
			
			#set the response
			response.update({'scenario': params['SCENARIO'],'metadata': metadata, 'files': files, 'runParameters': runParams, 'renderer': renderer, 'features': features, 'allFeatures': allfeatures, 'feature_preprocessing': preprocessing, 'planning_units': pu_data, 'protected_area_intersections': protected_area_intersections})
			
			#set the users last scenario so it will load on login
			updateParameters(user_folder + "user.dat", {'LASTSCENARIO': params['SCENARIO']})

		except (DatabaseError, MarxanServicesError) as e:
			response.update({'error': repr(e)})

		finally:
			conn.close()
			return getResponse(params, response)

#creates a new scenario in the users folder - currently used when importing an existing marxan project
	#https://db-server-blishten.c9users.io/marxan/webAPI2.py/createScenario?user=andrew&scenario=test2&description=Groovy%20description&callback=__jp2
class createScenario():
	def GET(self):
		try:
			log("createScenario",1)
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
		
#clones the scenario
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/cloneScenario?user=andrew&scenario=Tonga%20marine&callback=__jp2
class cloneScenario():
	def GET(self):
		try:
			log("cloneScenario",1)
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			
			#get the new scenario folder
			new_scenario_folder = scenario_folder
			#recursively check that the folder does not exist until we get a new folder that doesnt exist
			while (os.path.exists(new_scenario_folder)):
			    new_scenario_folder = new_scenario_folder[:-1] + "_copy/"
			
			#copy the scenario
			shutil.copytree(scenario_folder, new_scenario_folder)
			
			#update the description and create date
			updateParameters(new_scenario_folder + "input.dat", {'DESCRIPTION': "Copy of " + params['SCENARIO'] ,  'CREATEDATE': datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")})
			
			#set the response
			response.update({'info': "Scenario '" + new_scenario_folder[:-1].split("/")[-1] + "' created", 'name': new_scenario_folder[:-1].split("/")[-1]})

		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse(params, response)
		
#deletes the named scenario in the users folder
	#https://db-server-blishten.c9users.io/marxan/webAPI2.py/deleteScenario?user=andrew&scenario=test2&callback=__jp2
class deleteScenario():
	def GET(self):
		try:
			log("deleteScenario",1)
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
			log("renameScenario",1)
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
			log("renameDescription",1)
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
			log("updateRunParams",1)
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
			log("runMarxan",1)
			#initialise the request objectIs
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
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/pollResults?user=andrew&scenario=Marxan%20default%20scenario&numreps=10&checkForExistingRun=true&callback=__jp16
class pollResults:
	def GET(self):
		try:
			log("pollResults",1)
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
				log("Marxan request finished - compiling results")
				
				#read the log from the log file
				logresults = readFile(output_folder + "output_log.dat")
				
				#clean the log file
				logresults = cleanLog(logresults)
				
				#read the data from the output_mvbest.txt file
				mvbest = json.loads(pandas.read_csv(output_folder + "output_mvbest.txt").to_json(orient='values')) 

				#read the data from the output_sum.txt file
				sum = json.loads(pandas.read_csv(output_folder + "output_sum.txt").to_json(orient='values')) 
				
				#read the data from the output_ssoln.txt file
				df = pandas.read_csv(output_folder + "output_ssoln.txt")
				ssoln = normaliseDataFrame(df, "number", "planning_unit")

				#get the info message to return
				if params["CHECKFOREXISTINGRUN"] == "true":
					info = "Results loaded"
				else:
					info = "Run succeeded"
				
				#add the other items to the response
				response.update({'info':info, 'log': logresults, 'mvbest': mvbest, 'sum':sum, 'ssoln': ssoln})
		
			else:
				#return the number of runs completed
				response.update({'info': str(runsCompleted) + " runs completed", 'runsCompleted': runsCompleted})
			
		except (MarxanServicesError) as e:
			response.update({'error': e.message})

			
		finally:
			return getResponse(params, response)        

#for loading each individual solutions data
	#https://db-server-blishten.c9users.io/marxan/webAPI2.py/loadSolution?user=andrew&scenario=Sample%20scenaio&solution=1&callback=__jp2
class loadSolution:
	def GET(self):
		try:
			log("loadSolution",1)
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			if "SOLUTION" not in params.keys():
				raise MarxanServicesError("No solution parameter")
				
			#get the content from the solution - this will be 'output_r00001.txt'
			solutionFile = output_folder + "output_r" + "%05d" % (int(params["SOLUTION"]),)  + ".txt"
			try:
				df = pandas.read_csv(solutionFile)
				solution = normaliseDataFrame(df, "solution", "planning_unit")

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
			log("postFile",1)
			#there will be 5 variables in the data: 
			# parameter     = the type of marxan file being uploaded (SPECNAME, PUNAME, PUVSPRNAME, BOUNDNAME, BLOCKDEFNAME)
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

#saves an uploaded file to the input folder 
class postFileWithFolder:
	def POST(self):
		try:
			log("postFileWithFolder",1)
			#there will be 2 variables in the data: 
			# user			= the user who is uploading the file
			# scenario		= the name of the scenario
			# filename      = the filename of the uploaded file including a folder path
			# value         = the content of the file
			data = web.input()
			response = {}

			log("Input filename: " + data['filename'])
			
			#get the appropriate folders
			user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
			
			#get the path to the file
			destFile = scenario_folder + data['filename']
			
			log("Output filename: " + destFile)
			
			#write the data						
			writeFile(destFile, data['value'])

			#write the response
			response = {'info': "File '" + data.filename + "' uploaded", 'file': data.filename}
			
		except (MarxanServicesError) as e:
			response = {'error': e.message}

		except Exception as inst: #handles all errors TODO: Modify all other error handlers to use this approach
			response.update({'error': str(inst)})

		finally:
			return getResponse({}, response)

#uploads a shapefile to the input folder for the user
class postShapefile:
	def POST(self):
		try:
			log("postShapefile",1)
			#there will be 4 variables in the data: 
			# value         = the content of the file
			# filename      = the filename of the uploaded file
			# description   = a simple metadata description
			# name          = the text to display in UIs
			data = web.input()
			response = {}

			#write the file to the marxan folder
			writeFile(MARXAN_FOLDER + data.filename, data.value)
			
			#write the response
			response = {'info': "File '" + data.filename + "' uploaded", 'file': data.filename}
			
		except (MarxanServicesError) as e:
			response = {'error': e.message}

		finally:
			return getResponse({}, response)

#imports a shapefile that already exists on the server into postgis and optionally dissolves it (if it is an interest feature)
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/importShapefile?filename=png_provinces.zip&name=png_provinces&description=wibble&dissolve=true&type=interest_feature&callback=__jp2
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/importShapefile?filename=pu_sample.zip&name=pu_test&description=wibble&dissolve=false&type=planning_unit&callback=__jp2
class importShapefile:
	def GET(self):
		try:
			log("importShapefile",1)
			#get the query string parameters
			params = getQueryStringParams(web.ctx.query[1:])
			response = {}
	
			#error checking
			if "FILENAME" not in params.keys():
				raise MarxanServicesError("No shapefile filename parameter")
			if "NAME" not in params.keys():
				raise MarxanServicesError("No name value")
			if "DESCRIPTION" not in params.keys():
				raise MarxanServicesError("No description value")                                   
			if "DISSOLVE" not in params.keys():
				raise MarxanServicesError("No dissolve value")
			if "TYPE" not in params.keys(): #either planning_unit or interest_feature - this parameter determines which metadata table is updated
				raise MarxanServicesError("No type value")
			
			#unzip the shapefile
			filename = params['FILENAME']
			if not os.path.exists(MARXAN_FOLDER + filename):
				raise MarxanServicesError("The zip file '" + filename + "' does not exist")

			log("Unzipping the " + filename + " file")
			zip_ref = zipfile.ZipFile(MARXAN_FOLDER + filename, 'r')
			filenames = zip_ref.namelist()
			rootfilename = filenames[0][:-4]
			zip_ref.extractall(MARXAN_FOLDER)
			zip_ref.close()
			
			# connect to postgis
			try:
				#connect to the db
				conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
				cur = conn.cursor()
				
				#import the shapefile
				shapefile = rootfilename + '.shp'
				log("Importing the " + shapefile + " shapefile into PostGIS")
				
				#drop the undissolved feature class if it already exists
				cur.execute("DROP TABLE IF EXISTS marxan.undissolved;")	
				
				#the ogc_fid field that is produced is an autonumbering oid
				if params['DISSOLVE']=='true':
					#if we want to dissolve the shapefile, then produce a tmp feature class called undissolved in the marxan schema in the global equal area projection 3410
					cmd = '/home/ubuntu/anaconda2/bin/ogr2ogr -f "PostgreSQL" PG:"host=localhost user=jrc dbname=biopama password=thargal88" /home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/' + shapefile + ' -nlt GEOMETRY -lco SCHEMA=marxan -nln undissolved -t_srs EPSG:3410'
				else:
					cmd = '/home/ubuntu/anaconda2/bin/ogr2ogr -f "PostgreSQL" PG:"host=localhost user=jrc dbname=biopama password=thargal88" /home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/' + shapefile + ' -nlt GEOMETRY -lco SCHEMA=marxan'
					
				#run the import
				log("Running command: " + cmd)
				status, output = commands.getstatusoutput(cmd) 
				
				#check for errors
				if (output != ''):
					raise MarxanServicesError("Error importing shapefile: " + output)
				
				#delete the zip file and the shapefile
				log("Deleting the zipfile")
				os.remove(MARXAN_FOLDER + filename)	
				files = glob.glob(MARXAN_FOLDER + rootfilename + '.*')
				if len(files)>0:
					[os.remove(f) for f in files]       
			
	
				#if we want to dissolve the shapefile then do so now by querying the temporary feature class and outputting a new table with a single column called geometry in EPSG:3410
				if params['DISSOLVE']=='true':
					#create the feature class
					cur.execute("SELECT ST_Union(wkb_geometry) geometry INTO marxan." + rootfilename + " FROM marxan.undissolved;")	
					#create an index
					cur.execute("CREATE INDEX " + rootfilename + "_gix ON marxan." + rootfilename + " USING GIST (geometry);")
					#update the stats
					# cur.execute("VACUUM ANALYZE marxan." + rootfilename + ";") //implemented differently in psycopg2
					cur.execute("DROP TABLE IF EXISTS marxan.undissolved;")	

				#populate the metadata information for the planning units feature class
				if (params['TYPE'] == 'interest_feature'):
					log("insert a record in the metadata_interest_features table")
					# cur.execute("INSERT INTO marxan.metadata_interest_features(feature_class_name,alias,description,creation_date) values ('" + rootfilename + "','" + params['NAME'] + "','" + params['DESCRIPTION'] + "',now());")
					cur.execute("INSERT INTO marxan.metadata_interest_features SELECT '" + rootfilename + "','" + params['NAME'] + "','" + params['DESCRIPTION'] + "',now(), sub._area FROM (SELECT ST_Area(geometry) _area FROM marxan." + rootfilename + ") AS sub;")
				else:
					log("insert a record in the metadata_planning_units table")
					cur.execute("INSERT INTO marxan.metadata_planning_units(feature_class_name,alias,description,creation_date) values ('" + rootfilename + "','" + params['NAME'] + "','" + params['DESCRIPTION'] + "',now());")

			except (psycopg2.InternalError, psycopg2.IntegrityError, psycopg2.ProgrammingError) as e: #postgis error
				raise MarxanServicesError("Error importing shapefile: " + e.message)
				
			finally:
				cur.close()
				conn.commit()
				conn.close()
			
			#write the response
			response = {'info': "File '" + shapefile + "' imported", 'file': shapefile}
			
		except (MarxanServicesError) as e:
			response = {'error': e.message}

		finally:
			return getResponse(params, response)
		
#updates a parameter in the input.dat file directly, e.g. for updating the PLANNING_UNIT_NAME after the user sets their source spatial data
	#https://db-server-blishten.c9users.io/marxan/webAPI2.py/updateParameter?user=andrew&scenario=Sample%20scenario&parameter=DESCRIPTION&value=wibble&callback=__jp2
class updateParameter:
	def GET(self):
		try:
			log("updateParameter",1)
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

#gets the planning unit grids 
#https://db-server-blishten.c9users.io/marxan/webAPI.py/getPlanningUnitGrids
class getPlanningUnitGrids():
	def GET(self):
		try:
			log("getPlanningUnitGrids",1)			
			#initialise the request objects
			response = {}
			params = params = getQueryStringParams(web.ctx.query[1:])
			
			conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
			#get the planning unit grids
			query = "SELECT feature_class_name ,alias ,description ,creation_date::text ,country_id ,aoi_id,domain,_area,ST_AsText(envelope) FROM marxan.metadata_planning_units order by 1;"
			
			#get the intersection results
			data = pandas.read_sql_query(query, con=conn).to_dict(orient="records")
			response.update({'info':'Planning unit grids retrieved','planning_unit_grids':data})
		
		except (DatabaseError, psycopg2.InternalError, psycopg2.IntegrityError) as e: #postgis error
			raise MarxanServicesError("Error creating puvspr.dat file: " + e.message + ". Error type: " + str(sys.exc_info()[0]))
		
		finally:
			conn.close() 
			return getResponse(params, response)

# updates the data in the pu.dat file by setting all of the items in the puidsToExclude list to have a status of 1
class updatePlanningUnitStatuses:
	def POST(self):
		try:
			log("updatePlanningUnitStatuses",1)	
			data = web.input()
			response={}
			status1_ids =[]
			status2_ids =[]
			status3_ids=[]
			
			#get the various folders
			user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)

			# get the status ids as lists
			if "status1" in data.keys():
				status1_ids = data["status1"].strip().split(",")
			if "status2" in data.keys():
				status2_ids = data["status2"].strip().split(",")
			if "status3" in data.keys():
				status3_ids = data["status3"].strip().split(",")
				
			updatePuValues(input_folder + "pu.dat", status1_ids, status2_ids, status3_ids)
			
			#set the response
			response.update({'info': "pu.dat file updated"})
			
		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		except Exception as inst: #handles all errors TODO: Modify all other error handlers to use this approach
			response.update({'error': str(inst)})

		finally:
			return getResponse({}, response)

#https://db-server-blishten.c9users.io/marxan/webAPI.py/preprocessFeature?user=andrew&scenario=Tonga%20marine&planning_grid_name=pu_ton_marine_hexagons_50&feature_class_name=intersesting_habitat&id=63408405
class preprocessFeature:
	def GET(self):
		try:
			log("preprocessFeature",1)		
			
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			for key in ["PLANNING_GRID_NAME", "FEATURE_CLASS_NAME", "ID"]:
				if key not in params.keys():
					raise MarxanServicesError("No " + key.lower() + " parameter")
			
			#get the feature that needs to be processed
			log("Features to process: " + params['FEATURE_CLASS_NAME'])

			#get the species_id
			speciesId = int(params['ID'])
	
			#TODO: the name of the puvspr.dat file is hardcoded here - need to read it from the input.dat file			
			#get the interest features that already have records in the puvspr.dat file or an empty dataframe if the file does not exist
			if (os.path.exists(input_folder + "puvspr.dat")):
				existingData = pandas.read_csv(input_folder + "puvspr.dat")
				#make sure there are not existing records for this feature - otherwise we will get duplicates
				existingData = existingData[~existingData.species.isin([speciesId])]
				
			else:
				# no file so create an empty data frame to hold the data for the puvspr.dat file
				d = {'amount':pandas.Series([], dtype='float64'),'species':pandas.Series([], dtype='int64'),'pu':pandas.Series([], dtype='int64')}
				existingData = pandas.DataFrame(data=d)
				existingData = existingData[['species', 'pu', 'amount']] #reorder the columns

			#do the intersection
			oldVersion = getInputParameter(scenario_folder + 'input.dat',"OLDVERSION")
			#see whether we are using an old version of marxan - in this case we cant do an intersection on spatial data, but the intersection will have already been done with the results already in the puvspr.dat file
			if oldVersion == 'False':
				
				try:
					#do the intersection	
					conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
					#intersect the feature with the planning units
					log("Intersecting feature '" + params['FEATURE_CLASS_NAME'] + "' with '" + params['PLANNING_GRID_NAME'] + "'");
					query = "select * from marxan.get_pu_areas_for_interest_feature('" + params['PLANNING_GRID_NAME'] + "','" + params['FEATURE_CLASS_NAME'] + "');"
					log(query)
					
					#get the intersection results
					intersectionData = pandas.read_sql_query(query, con=conn)  

					#append them to the existing data
					if not intersectionData.empty:
						existingData = existingData.append(intersectionData)

					#write the results to the puvspr.dat file
					existingData.to_csv(input_folder + "puvspr.dat",index = False)
					
				except (DatabaseError, psycopg2.InternalError, psycopg2.IntegrityError) as e: #postgis error
					raise MarxanServicesError("Error creating puvspr.dat file: " + e.message + ". Error type: " + str(sys.exc_info()[0]))
				
				finally:
					conn.close() 
			
			#get the count of intersecting planning units
			pu_count = existingData[existingData.species.isin([speciesId])].agg({'pu' : ['count']})['pu'].iloc[0]
			
			#get the total area of the feature across all planning units
			pu_area = existingData[existingData.species.isin([speciesId])].agg({'amount': ['sum']})['amount'].iloc[0]
			
			#write the pu_area and pu_count to the preprocessing.dat file 
			row = pandas.DataFrame.from_dict({'id':speciesId, 'pu_area': [pu_area], 'pu_count': [pu_count]}).astype({'id': 'int', 'pu_area':'float', 'pu_count':'int'})
			_writeToDatFile(input_folder + FEATURE_PREPROCESSING_FILENAME, row)

			#update the input.dat file
			updateParameters(scenario_folder + "input.dat", {'PUVSPRNAME': 'puvspr.dat'})
			#set the response
			response.update({'info': "Feature " + params['FEATURE_CLASS_NAME'] + " preprocessed", "feature_class_name": params['FEATURE_CLASS_NAME'], "pu_area" : str(pu_area),"pu_count" : str(pu_count), "id":str(speciesId)})
			
		except Exception as e: #handles all errors TODO: Modify all other error handlers to use this approach
			response.update({'error': repr(e)})

		finally:
			return getResponse(params, response)

#creates a new scenario in the users folder using input from the marxan web wizard
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/createScenarioFromWizard?user=asd&scenario=test&description=whatever&planning_grid_name=pu_asm_terrestrial_hexagons_10
class createScenarioFromWizard():
	def POST(self):
		try:
			log("createScenarioFromWizard",1)			
			#get the data from the POST request
			data = web.input()
			response={}

			#error checking
			for key in ["user", "scenario", "description", "planning_grid_name","interest_features","target_values","spf_values"]:
				if key not in data.keys():
					raise MarxanServicesError("No " + key + " parameter")

			#get the various folders
			user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
						
			#check the scenario doesnt already exist
			log("Creating new scenario " + data["scenario"] + " in folder " + scenario_folder)
			if (os.path.exists(scenario_folder)):
				raise MarxanServicesError("Scenario '" + data["scenario"] + "' already exists") 

			#create the folders for the scenario and copy the input.dat file
			createEmptyScenario(input_folder, output_folder, scenario_folder, data['description'])
			log("Empty scenario created")
			
			#write the planning_grid_name into the input.dat file
			log("planning_grid_name will be " + data['planning_grid_name'])
			updateParameters(scenario_folder + "input.dat", {'PLANNING_UNIT_NAME': data['planning_grid_name']})
			
			# create the pu.dat file
			_createPUdatafile(scenario_folder, input_folder, data["planning_grid_name"])

			# update the spec.dat file
			_updateSPECdatafile(scenario_folder, input_folder, data["interest_features"], data["target_values"], data['spf_values'])

			# #set the response
			response.update({'info': "Scenario '" + data["scenario"] + "' created", 'name': data["scenario"]})

		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse({}, response)
	
#creates/updates the spec.dat file with the passed parameters
class updateSpecFile():
	def POST(self):
		try:
			log("updateSpecFile",1)			
			#get the data from the POST request
			data = web.input()
			response={}

			#error checking
			for key in ["user", "scenario", "interest_features","target_values","spf_values"]:
				if key not in data.keys():
					raise MarxanServicesError("No " + key + " parameter")

			#get the various folders
			user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
			
			# update the spec.dat file
			_updateSPECdatafile(scenario_folder, input_folder, data["interest_features"], data["target_values"], data['spf_values'])

			# #set the response
			response.update({'info': "spec.dat file updated"})

		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse({}, response)
	
#deletes the interest feature dataset from postgis and removes the record in the metadata_interest_features table
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/deleteInterestFeature?interest_feature_name=png_provinces
class deleteInterestFeature:
	def GET(self):
		try:
			#get the query string parameters
			params = getQueryStringParams(web.ctx.query[1:])
			response = {}
	
			#error checking
			if "INTEREST_FEATURE_NAME" not in params.keys():
				raise MarxanServicesError("No interest_feature_name parameter")
			
			log("deleteInterestFeature: " + params['INTEREST_FEATURE_NAME'],1)			

			#drop the record in the metadata_interest_features table
			try:
				#connect to the db
				conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
				cur = conn.cursor()
	
				#populate the metadata information for the planning units feature class
				query = "DELETE FROM marxan.metadata_interest_features WHERE feature_class_name = '" + params['INTEREST_FEATURE_NAME'] + "';"
				cur.execute(query)
				log("Metadata record deleted for '" + params['INTEREST_FEATURE_NAME'] + "'")
				cur.execute("DROP TABLE IF EXISTS marxan." + params['INTEREST_FEATURE_NAME'] + ";")
				log(params['INTEREST_FEATURE_NAME'] + " table dropped")
				
			except (psycopg2.InternalError, psycopg2.IntegrityError) as e: #postgis error
				raise MarxanServicesError("Error creating planning units: " + e.message)
				
			finally:
				cur.close()
				conn.commit()
				conn.close()
			
				#write the response
				response = {'info': "Interest feature '" + params['INTEREST_FEATURE_NAME'] + "' deleted"}
			
		except (MarxanServicesError) as e:
			response = {'error': e.message}
	
		finally:
			return getResponse(params, response)

#does the intersection between the passed grid and the countries protected areas (with iucn categories)
#https://db-server-blishten.c9users.io/marxan/webAPI.py/getPAIntersections?user=andrew&scenario=Tonga%20marine%20new&planning_grid_name=pu_ton_marine_hexagons_50
class getPAIntersections():
	def GET(self):
		log("getPAIntersections",1)			
		#initialise the request objects
		user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])

		#error checking
		for key in ["USER", "SCENARIO", "PLANNING_GRID_NAME"]:
			if key not in params.keys():
				raise MarxanServicesError("No " + key + " parameter")

		#get a connection to the database
		try:
			conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
			
			#get all the puids that intersect protected areas in this country
			# query = "SELECT DISTINCT iucn_cat, grid.puid FROM (SELECT iucn_cat, geom FROM marxan.wdpa WHERE iucn_cat = ANY (ARRAY['Ib','II','Ia','V','III','IV','VI'])) AS wdpa, marxan." + params['PLANNING_GRID_NAME'] + " grid WHERE ST_Intersects(wdpa.geom, ST_Transform(grid.geometry, 4326)) ORDER BY 1,2;"
			query = "SELECT DISTINCT iucn_cat, grid.puid FROM (SELECT iucn_cat, geom FROM marxan.wdpa) AS wdpa, marxan." + params['PLANNING_GRID_NAME'] + " grid WHERE ST_Intersects(wdpa.geom, ST_Transform(grid.geometry, 4326)) ORDER BY 1,2;"
			df = pandas.read_sql_query(query, con=conn)
			#normalise the data, e.g. to [["VI", [7, 8, 9]], ["IV", [0, 1, 2, 3, 4]], ["V", [5, 6]]]
			puids = normaliseDataFrame(df, "iucn_cat", "puid")
			
			#write the response
			response = {'info': puids}
			
			#write the data to file
			df.to_csv(input_folder + PROTECTED_AREA_INTERSECTIONS_FILENAME, index =False)
			
		except (DatabaseError, MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			conn.close()
			return getResponse(params, response)

app = web.application(urls, locals())  
logging.basicConfig(filename='/home/ubuntu/lib/apache2/log/marxan.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

if __name__ == "__main__":
	app.run()