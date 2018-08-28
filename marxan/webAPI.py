#!/home/ubuntu/anaconda2/bin/python
#the above line forces the CGI script to use the Anaconda Python interpreter
import sys, os, web, subprocess, urllib, pandas, json, glob, shutil, re, datetime, logging, CustomExceptionClasses, shapefile, math, psycopg2, zipfile, commands, numpy
import geopandas as gpd
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
  "/deleteScenario", "deleteScenario",
  "/renameScenario", "renameScenario",
  "/renameDescription", "renameDescription",
  "/updateRunParams","updateRunParams",
  "/runMarxan", "runMarxan", 
  "/pollResults","pollResults",
  "/loadSolution", "loadSolution", 
  "/postFile","postFile",
  "/postShapefile","postShapefile",
  "/importShapefile","importShapefile",
  "/updateParameter","updateParameter",
  "/createPlanningUnitsGrid","createPlanningUnitsGrid", #python implementation
  "/createPlanningUnits","createPlanningUnits", #postgis implementation
  "/uploadTilesetToMapBox","uploadTilesetToMapBox",
  "/createPUdatafile","createPUdatafile",
  "/getInterestFeaturesForScenario","getInterestFeaturesForScenario",
  "/deleteInterestFeature","deleteInterestFeature",
  "/createPUVSPRdatafile","createPUVSPRdatafile",
  "/createSpecFile","createSpecFile"
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
		elif k in ['DESCRIPTION','CREATEDATE','PLANNING_UNIT_NAME','OLDVERSION']: # metadata section of the input.dat file
			key, value = getKeyValue(s, k)
			metadataDict.update({key: value})
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

def createShapefileWithResults():
	log("createShapefileWithResults")
	#get the planning units as a GeoDataFrame
	planning_units = gpd.read_file(MARXAN_FOLDER + "pulayer1km.shp")
	#get the summed solutions as a DataFrame
	summed_solution = pandas.read_csv(MARXAN_OUTPUT_FOLDER + "output_ssoln.txt")
	#join these datasets together 
	summed_solution_shapes = planning_units.merge(summed_solution,left_on="PUID",right_on="planning_unit")
	#write the results to a shapefile
	summed_solution_shapes.to_file(MARXAN_OUTPUT_FOLDER + "results.shp")

def deleteAllFiles(folder):
	log("deleteAllFiles")
	files = glob.glob(folder + "*")
	for f in files:
		os.remove(f)

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
	log("initialisePostRequest")
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
		log("user_folder: " + user_folder)
		log("scenario_folder: " + scenario_folder)
		log("input_folder: " + input_folder)
		log("output_folder: " + output_folder)
		
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
	log("RESPONSE: " + responseJson[:100], 2)
	#get the callback parameter for jsonp calls
	if "CALLBACK" in params.keys():
		return params["CALLBACK"] + "(" + responseJson + ")"
	else:
		return responseJson
	
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
			#create a dict to save the data
			scenarios.append({'name':scenario,'description':desc,'createdate': createDate})
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

#reads in the text file and transforms the data so that each row has: <number of solutions>, <puid array>
def getVectorTileOptimisedOutput(csvFile, columnName):
	log("getVectorTileOptimisedOutput for csvFile '" + csvFile + "' and columnName '" + columnName + "'")
	df= pandas.read_csv(csvFile).pivot(index=columnName,columns='planning_unit',values='planning_unit') #pivots the data
	transposed = df[df.columns].apply(lambda x: ','.join(x.dropna().astype(int).astype(str)),axis=1) #joins the multiple columns to produce a comma-separated string of PUIDs with the number
	arr = [[i,[int(n) for n in j.split(",")]] for (i,j) in transposed.items()][1:] #convert to an array of arrays and skip the first item as this one is all of the planning units which do not occur in any solution and dont need to be mapped
	return json.loads(json.dumps(arr))

def CreateGrid(pu_folder, _type, area, xleft, ybottom, xright, ytop):
	log("CreateGrid: " + pu_folder + " " + _type + " " + str(area) + " " + str(xleft) + " " + str(ybottom) + " " + str(xright) + " " + str(ytop))
	#error checks
	if area <0:
		raise MarxanServicesError("Area value is invalid")
	if (xleft >= xright):
		raise MarxanServicesError("Invalid extent width: " + unicode(xleft) + " - " + unicode(xright))
	if (ybottom >= ytop):
		raise MarxanServicesError("Invalid extent height: " + unicode(ybottom) + " - " + unicode(ytop))

	#create the output shapefile
	w = shapefile.Writer(pu_folder + PLANNING_UNIT_GRID_NAME)
	w.field('grid_id', 'C')
		
	#calculate the spacing between the grids to give you the required area
	if (_type == 'hexagon'):
		sideLength = math.sqrt((2*area)/(3*math.sqrt(3)))
		xspacing = sideLength + (sideLength * 0.5) # the cos(60) = 0.5
		yspacing = xspacing / 0.866025
		# To preserve symmetry, hspacing is fixed relative to vspacing
		xvertexlo = 0.288675134594813 * yspacing
		xvertexhi = 0.577350269189626 * yspacing
		xspacing = xvertexlo + xvertexhi
	else:
		sideLength = math.sqrt(area)
		xspacing = sideLength
		yspacing = xspacing / 0.866025

	#get the number of rows/columns
	rows = int(math.ceil((ytop - ybottom) / yspacing))
	columns = int(math.ceil((xright - xleft) / xspacing))
	
	log("SIDELENGTH: " + str(sideLength))
	log("ROWS: " + str(rows))
	log("COLUMNS: " + str(columns))
	log("XSPACING: " + str(xspacing))
	log("YSPACING: " + str(yspacing))
	
	#initialise the feature counter
	feature_count = 0
	
	#THE FOLLOWING CODE COMES LARGELY FROM MICHAEL MINN'S MMQGIS PLUGIN - http://michaelminn.com/linux/mmqgis/
	for column in range(0, int(math.floor(float(xright - xleft) / xspacing))):
		
		if (_type == 'hexagon'):
			x1 = xleft + (column * xspacing)    # far left
			x2 = x1 + (xvertexhi - xvertexlo)    # left
			x3 = xleft + ((column + 1) * xspacing)    # right
			x4 = x3 + (xvertexhi - xvertexlo)    # far right
		else:
			x1 = xleft + (column * xspacing)    # left
			x2 = xleft + ((column + 1) * xspacing)    # right
			
		for row in range(0, int(math.floor(float(ytop - ybottom) / yspacing))):

			if (_type == 'hexagon'):
				if (column % 2) == 0:
					y1 = ybottom + (((row * 2) + 0) * (yspacing / 2))    # hi
					y2 = ybottom + (((row * 2) + 1) * (yspacing / 2))    # mid
					y3 = ybottom + (((row * 2) + 2) * (yspacing / 2))    # lo
				else:
					y1 = ybottom + (((row * 2) + 1) * (yspacing / 2))    # hi
					y2 = ybottom + (((row * 2) + 2) * (yspacing / 2))    # mid
					y3 = ybottom + (((row * 2) + 3) * (yspacing / 2))    #lo
				
				#create the coordinates of the hexagon
				coordinates = [[x1, y2], [x2, y1], [x3, y1], [x4, y2], [x3, y3], [x2, y3], [x1, y2]]
			
			else: #regular grid
				y1 = ybottom + (row * yspacing)    
				y2 = ybottom + ((row + 1) * yspacing)     
				
				#create the coordinates of the grid
				coordinates = [[x1,y1],[x1,y2],[x2,y2],[x2,y1],[x1,y1]]
			
			#create a polygon with the coordinates
			w.poly([coordinates])

			#set the feature id
			w.record(feature_count)
			
			#increment the counter
			feature_count = feature_count + 1

	w.close()    

	log(str(feature_count) + " grid features created")
	
	# Write the prj file as it doesn't get produced because of a bug
	file = open(pu_folder + PLANNING_UNIT_GRID_NAME + ".prj","w") 
	file.write('PROJCS["NSIDC EASE-Grid Global",GEOGCS["Unspecified datum based upon the International 1924 Authalic Sphere",DATUM["Not_specified_based_on_International_1924_Authalic_Sphere",SPHEROID["International 1924 Authalic Sphere",6371228,0,AUTHORITY["EPSG","7057"]],AUTHORITY["EPSG","6053"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4053"]],UNIT["metre",1,AUTHORITY["EPSG","9001"]],PROJECTION["Cylindrical_Equal_Area"],PARAMETER["standard_parallel_1",30],PARAMETER["central_meridian",0],PARAMETER["false_easting",0],PARAMETER["false_northing",0],AUTHORITY["EPSG","3410"],AXIS["X",EAST],AXIS["Y",NORTH]]')
	file.close()
	
	#return the grid as a geopandas dataset
	return gpd.read_file(pu_folder + PLANNING_UNIT_GRID_NAME + ".shp")

##############################################################################################################################################################################################################################################
#################  MapBox routines
##############################################################################################################################################################################################################################################

#uploads a tileset to mapbox using the filename of the file (filename) to upload and the name of the resulting tileset (_name)
def uploadTileset(filename, _name):
	log("Uploading to MapBox: " + filename + " " + name)
	#create an instance of the upload service
	service = Uploader(access_token=MAPBOX_ACCESS_TOKEN)	
	with open(filename, 'rb') as src:
		upload_resp = service.upload(src, _name)
		upload_id = upload_resp.json()['id']
		return upload_id
		
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

#creates the spec.dat file using the passed paramters - used in the web API and internally in the createScenarioFromWizard function
def _createSPECdatafile(scenario_folder, input_folder, interest_features, target_values, spf_values):
	#create the spec.dat file
	try:
		log("Creating spec.dat file in folder '" + input_folder + "' using interest features")
		ids = interest_features.split(",")
		props = target_values.split(",") 
		spfs = spf_values.split(",") 

		#open the file writer
		file = open(input_folder  + "spec.dat","w") 
		file.write('id,prop,spf\n')
		
		#write the spec data to file
		for i in range(len(ids)):
			file.write(ids[i] + "," + str(float(props[i])/100) + "," + spfs[i] + "\n")
		file.close()
		log("spec.dat file created")
			
	except (MarxanServicesError) as e: 
		response.update({'error': e.message})
		
	finally:
		#update the input.dat file
		updateParameters(scenario_folder + "input.dat", {'SPECNAME': 'spec.dat'})

def _getInterestFeaturesForScenario(scenario_folder,input_folder, web_call):
	#set web_call to True if the results will be transformed for a webclient, e.g. in spec.dat the targetValue is called 'prop'
	try:
		log("_getInterestFeaturesForScenario: " + input_folder)
		#get the location of the spec.dat file for the scenario
		specname = getInputParameter(scenario_folder + 'input.dat',"SPECNAME")
			
		#get the values from the spec.dat file  for the scenario
		df = pandas.read_csv(input_folder + specname)
		
		try:
			#connect to the db
			conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
			
			#get the values from the marxan.metadata_interest_features table
			df2 = pandas.read_sql_query('select oid,* from marxan.metadata_interest_features',con=conn)   
			
			#join the dataframes using the id field as the key from the spec.dat file and the oid as the key from the metadata_interest_features table
			output_df = df.set_index("id").join(df2.set_index("oid"))
			
			#add the index as a column
			output_df['oid']=output_df.index
	
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
			    output_df = output_df.rename(index=str, columns={'prop': 'targetValue', 'oid':'id'})    
			
			    #get the target as an integer - Marxan has it as a percentage, i.e. convert 0.17 -> 17
			    output_df['targetValue'] = (output_df['targetValue'] * 100).astype(int)
		    
		except (psycopg2.InternalError, psycopg2.IntegrityError) as e: #postgis error
			raise MarxanServicesError("Error getting interest features for scenario: " + e.message)
		
		finally:
			conn.close()

	except Exception: #general error if the input_folder doesnt exist
		raise 

	return output_df #return a pandas dataframe	
	
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
			
		except (MarxanServicesError) as e: 
			response.update({'error': e.message})

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
	#https://db-server-blishten.c9users.io/marxan/webAPI2.py/getScenario?user=andrew&scenario=Sample%20scenario&callback=__jp2
class getScenario():
	def GET(self):
		try:
			log("getScenario",1)
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			checkScenarioExists(scenario_folder)                

			#open the input.dat file to get all of the scenario files, parameters and metadata
			files, runParams, metadata, renderer = getInputParameters(scenario_folder + "input.dat")
			
			#get the interest features for this scenario 
			features = json.loads(_getInterestFeaturesForScenario(scenario_folder,input_folder, True).to_json(orient='records'))
			
			#get all the interest features - these will be returned even for marxan desktop databases which have no records in the metadata_interest_features table
			conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
			df = pandas.read_sql_query("SELECT oid::integer as id, creation_date, feature_class_name, alias, description FROM marxan.metadata_interest_features;", con=conn)
			allfeatures = json.loads(df.to_json(orient='records'))

			#set the response
			response.update({'scenario': params['SCENARIO'],'metadata': metadata, 'files': files, 'runParameters': runParams, 'renderer': renderer, 'features': features, 'allFeatures': allfeatures})
			
			#set the users last scenario so it will load on login
			updateParameters(user_folder + "user.dat", {'LASTSCENARIO': params['SCENARIO']})

		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		except Exception as inst: 
			response.update({'error': str(inst)})

		finally:
			conn.close()
			return getResponse(params, response)

#creates a new scenario in the users folder
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
	#https://db-server-blishten.c9users.io/marxan/webAPI2.py/pollResults?user=asd2&scenario=Marxan%20default%20scenario&numreps=10&returnall=false&callback=__jp2
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
				log("Marxan request finished")
				
				#read the log from the log file
				logresults = readFile(output_folder + "output_log.dat")
				
				#read the data from the text file
				sum = pandas.read_csv(output_folder + "output_sum.txt").to_json(orient='values') 
				
				#get the summed solution as a json string
				ssoln = getVectorTileOptimisedOutput(output_folder + "output_ssoln.txt", "number")

				#get the info message to return
				if params["CHECKFOREXISTINGRUN"] == "true":
					info = "Results loaded"
				else:
					info = "Run succeeded"
				
				#add the other items to the response
				response.update({'info':info, 'log': logresults, 'sum':json.loads(sum),'ssoln': ssoln})
		
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
			log("loadSolution",1)
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

			#write the file to the marxan folder
			writeFile(MARXAN_FOLDER + data.filename, data.value)
			
			#write the response
			response = {'info': "File '" + data.filename + "' uploaded", 'file': data.filename}
			
		except (MarxanServicesError) as e:
			response = {'error': e.message}

		finally:
			return getResponse({}, response)

#imports a shapefile that already exists on the server into postgis and optionally dissolves it (if it is an interest feature)
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/importShapefile?filename=png_provinces.zip&name=png_provinces&description=wibble&dissolve=true&callback=__jp2
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
			
			#import the shapefile
			shapefile = rootfilename + '.shp'
			log("Importing the " + shapefile + " shapefile into PostGIS")
			#the ogc_fid field that is produced is an autonumbering oid
			if params['DISSOLVE']=='true':
				#if we want to dissolve the shapefile, then produce a tmp feature class called undissolved in the marxan schema in the global equal area projection 3410
				cmd = '/home/ubuntu/anaconda2/bin/ogr2ogr -f "PostgreSQL" PG:"host=localhost user=jrc dbname=biopama password=thargal88" /home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/' + shapefile + ' -nlt GEOMETRY -lco SCHEMA=marxan -nln undissolved -t_srs EPSG:3410'
				log("Imported into marxan.undissolved")
			else:
				cmd = '/home/ubuntu/anaconda2/bin/ogr2ogr -f "PostgreSQL" PG:"host=localhost user=jrc dbname=biopama password=thargal88" /home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/' + shapefile + ' -nlt GEOMETRY -lco SCHEMA=marxan'
				log("Imported into marxan." + rootfilename)
				
			#run the import
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
			
			#insert a record in the metadata_interest_features table
			try:
				log("insert a record in the metadata_interest_features table")
				#connect to the db
				conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
				cur = conn.cursor()
	
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
				cur.execute("INSERT INTO marxan.metadata_interest_features(feature_class_name,alias,description,creation_date) values ('" + rootfilename + "','" + params['NAME'] + "','" + params['DESCRIPTION'] + "',now());")
				
			except (psycopg2.InternalError, psycopg2.IntegrityError, psycopg2.ProgrammingError) as e: #postgis error
				raise MarxanServicesError("Error importing shapefile: " + e.message)
				
			finally:
				cur.close()
				conn.commit()
				conn.close()
			
			#write the response
			response = {'info': "File '" + shapefile + "' imported"}
			
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

#creates a hexagon grid on the server to use for partitioning the area of interest into hexagons - this is a Python implementation - NO LONGER USED
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/createPlanningUnitsGrid?user=asd&aoi=PNG&domain=terrestrial&type=hexagon&area=50000000&name=test_hexagon
class createPlanningUnitsGrid:
	def GET(self):
		try:
			log("createPlanningUnitsGrid",1)
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			if "USER" not in params.keys():
				raise MarxanServicesError("No user parameter")
			if "AOI" not in params.keys(): #either a 3-letter country code or a user-defined area which is the name of a shapefile in the __shapefiles/aois folder
				raise MarxanServicesError("No area of interest parameter")
			if "DOMAIN" not in params.keys(): #either marine or terrestrial
				raise MarxanServicesError("No domain parameter")
			if "TYPE" not in params.keys(): #hexagon or square
				raise MarxanServicesError("No type parameter") 
			if "AREA" not in params.keys(): #the area of each polygon in m2
				raise MarxanServicesError("No area parameter")
			if "NAME" not in params.keys():
				raise MarxanServicesError("No name parameter")

			#initialise the logging
			log("USER: " + params["USER"])
			log("AOI: " + params["AOI"])
			log("DOMAIN: " + params["DOMAIN"])
			log("TYPE: " + params["TYPE"])
			log("AREA: " + params["AREA"])
			log("NAME: " + params["NAME"])

			#set the output folder where the planning unit shapefile will be created
			pu_folder = user_folder + "__shapefiles" + os.sep + "planning units" + os.sep
			
			#get the aoi shapefile - this will either be a feature in the GAUL/EEZ shapefile for a country with the 3 letter country code or a user-defined area which is the name of a shapefile in the __shapefiles/aois folder
			if params["DOMAIN"] == "terrestrial":
				domain = "gaul_2015_simplified"
			else:
				domain = "marine_simplified_5km"
				
			#open the world shapfile for marine or terrestrial - these folders no longer exist
			world = gpd.read_file(MARXAN_FOLDER + "input_shapefiles" + os.sep + domain + ".shp")
			
			#select the feature with the 3 letter country code
			try:
				aoi = world.loc[world[ISO3_FIELD_NAME]==params["AOI"]] 
				
			except (KeyError) as e:
				raise MarxanServicesError ("Required field '" + ISO3_FIELD_NAME + "' not found in " + domain + " dataset")
			
			#the 3 letter country code doesnt exist
			if aoi.empty:
				
				#try opening the aoi as a named shapefile in the users __shapefiles folder
				try:
					aoi = gpd.read_file(user_folder + "__shapefiles" + os.sep + "aois" + os.sep + params["AOI"] + ".shp")
					
				#if that doesnt exist then throw an error
				except (IOError) as e:
					raise MarxanServicesError ("User-defined area " + params["AOI"] + " not found")
				
			#reproject and get the bounds
			bounds = aoi['geometry'].to_crs(epsg=3410).bounds.iloc[0] #iloc gets the first bounds
			log("AOI FEATURES: " + str(aoi.shape[0]))
			log("BOUNDS: " + str(bounds.minx) + " " + str(bounds.miny) + " " + str(bounds.maxx) + " " + str(bounds.maxy))
			
			#check the planning unit does not already exist
			filename = params["NAME"]
			if os.path.exists(pu_folder + filename + ".shp"):
				raise MarxanServicesError("The planning unit '" + filename + "' already exists")
				
			#create the grid - by default this will have the filename grid.shp
			grid = CreateGrid(pu_folder, params["TYPE"], float(params["AREA"]), bounds.minx, bounds.miny, bounds.maxx, bounds.maxy)

			#spatially join the grid with the aoi to get the output shapefile
			output = gpd.sjoin(aoi.to_crs(epsg=3410), grid, how="right", op='intersects')
			
			#select only those features that intersect with the aoi
			results = output.loc[output[ISO3_FIELD_NAME]==params["AOI"]]
			log("OUTPUT FEATURES: " + str(results.shape[0]))

			#write the output to file
			results.to_file(pu_folder + filename + ".shp")
			log("Features written to '" + pu_folder + filename + ".shp" + "'")

			#return the response
			response.update({'info': "Grid created to '" + pu_folder + filename + ".shp" + "'"})
			
		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		except:
			response.update({'error': str(sys.exc_info()[1])})

		finally:
			#remove the temporary grid files
			files = glob.glob(pu_folder + PLANNING_UNIT_GRID_NAME + '.*')
			if len(files)>0:
				[os.remove(f) for f in files]            
				
			return getResponse(params, response)

#creates a hexagon grid on the server to use for partitioning the area of interest into hexagons - this is a PostGIS implementation - NO LONGER USED
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/createPlanningUnits?user=asd&aoi=PNG&domain=terrestrial&type=hexagon&area=50
class createPlanningUnits:
	def GET(self):
		try:
			log("createPlanningUnits",1)
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			if "USER" not in params.keys():
				raise MarxanServicesError("No user parameter")
			if "AOI" not in params.keys(): #either a 3-letter country code in which case the aoi will be taken from the country boundary or a user-defined area which is the name of a feature class in the PostGIS database marxan.aoi_<user>_<featureclassname>
				raise MarxanServicesError("No area of interest parameter")
			if "DOMAIN" not in params.keys(): #either marine or terrestrial
				raise MarxanServicesError("No domain parameter")
			if "TYPE" not in params.keys(): #hexagon or square
				raise MarxanServicesError("No type parameter") 
			if "AREA" not in params.keys(): #the area of each polygon in m2
				raise MarxanServicesError("No area parameter")

			#initialise the logging
			logging.basicConfig(filename='/home/ubuntu/lib/apache2/log/marxan.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
			logging.info("=============================================================================================")
			logging.info("USER: " + params["USER"])
			logging.info("AOI: " + params["AOI"])
			logging.info("DOMAIN: " + params["DOMAIN"])
			logging.info("TYPE: " + params["TYPE"])
			logging.info("AREA: " + params["AREA"])
			
			try:
				#connect to the db
				conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
				cur = conn.cursor()

				#run the query to produce the planning units feature class
				cur.execute("SELECT marxan.hexagons(" + params['AREA'] + ",'" + params['AOI'] + "','" + params["DOMAIN"] + "');")
				
				#get the name of the feature class
				feature_class_name = cur.fetchone()[0]
				
				#set the response for creating the feature class
				response.update({'postgis': "Planning unit '" + feature_class_name + "' created"})
				logging.info("Planning unit '" + feature_class_name + "' created")
				
				# #populate the metadata information for the planning units feature class
				# alias = params["AOI"] + " " + params["AREA"] + "Km2 " + params["TYPE"] + "s created"
				# cur.execute("INSERT INTO marxan.metadata_planning_units(feature_class_name, alias, description, creation_date, country_id, aoi_id, domain, _area) values ('" + feature_class_name + "','" + alias + "','Bla bla bla',now(),1,null,'" + params["TYPE"] + "'," + params["AREA"] + ");")
				# logging.info("Metadata record created")
				
			except (psycopg2.InternalError) as e: #postgis error
				raise MarxanServicesError("Error creating planning units: " + e.message)
				
			finally:
				cur.close()
				conn.commit()
				conn.close()
			
			#create the file to upload to MapBox
			logging.info("Exporting to KML")
			outputFile = '/home/ubuntu/workspace/' + feature_class_name + '.kml'
			cmd = '/home/ubuntu/anaconda2/bin/ogr2ogr -f kml ' + outputFile + ' "PG:host=localhost dbname=biopama user=jrc password=thargal88" -sql "select * from Marxan.' + feature_class_name + '" -nln hexagons -s_srs EPSG:3410 -t_srs EPSG:3857'
			os.system(cmd)
			
			#upload to mapbox
			uploadId = uploadTileset(outputFile, feature_class_name)
			#set the response for uploading to mapbox
			response.update({'mapbox': "Tileset '" + feature_class_name + "' uploading",'uploadid': uploadId})
						
		except (MarxanServicesError) as e:
			response.update({'error': e.message})
		
		except (errors.HTTPError) as e: #mapbox error
			logging.info("mapbox error")
			response.update({'error': "Unable to upload to MapBox: " + e.message})
			
		except:
			response.update({'error': str(sys.exc_info()[1])})

		finally:
			return getResponse(params, response)

#creates the marxan planning unit data file, pu.dat in the folder for the given user and scenario using the planning_grid_name which corresponds to a feature class in the postgis database
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/createPUdatafile?user=asd&scenario=test&planning_grid_name=pu_asm_terrestrial_hexagons_10
class createPUdatafile:
	def GET(self):
		try:
			log("createPUdatafile",1)			
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			if "PLANNING_GRID_NAME" not in params.keys():
				raise MarxanServicesError("No planning grid")
			
			#create the pu.dat file
			_createPUdatafile(input_folder, params["PLANNING_GRID_NAME"])
				
			#set the response
			response.update({'info': "pu.dat file created"})
			
		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse(params, response)

#creates the marxan planning unit versus species file in the folder for the given user and scenario using the planning_grid_name which corresponds to a feature class in the postgis database and the array of interest feature ids which are in the spec.dat file
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/createPUVSPRdatafile?user=asd&scenario=test&planning_grid_name=pu_asm_terrestrial_hexagons_10
class createPUVSPRdatafile:
	def GET(self):
		try:
			log("createPUVSPRdatafile",1)			
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])
			if "PLANNING_GRID_NAME" not in params.keys():
				raise MarxanServicesError("No planning grid")
			
			#first, get the interest feature ids and names from the pu.dat file
			features = _getInterestFeaturesForScenario(scenario_folder,input_folder, False)
			feature_ids = features.index.tolist() #as a python list
			
			#get the interest features that already have records in the puvspr.dat file or an empty dataframe if the file does not exist
			if (os.path.exists(input_folder + "puvspr.dat")):
				log("Getting features already processed in " + input_folder + "puvspr.dat")
				df = pandas.read_csv(input_folder + "puvspr.dat", sep='\t')
			else:
				# no file so create an empty data frame to hold the data for the puvspr.dat file
				d = {'amount':pandas.Series([], dtype='float64'),'species':pandas.Series([], dtype='int64'),'pu':pandas.Series([], dtype='int64')}
				df = pandas.DataFrame(data=d)
				df = df[['species', 'pu', 'amount']] #reorder the columns
				
			#get the unique interest features that have already been processed
			feature_ids_already_processed = df.species.unique() #as a numpy.ndarray
			log("Feature ids already processed: " + ','.join([str(s) for s in feature_ids_already_processed]))
			
			#get the features that need to be processed
			feature_ids_to_process = list(set(feature_ids) - set(feature_ids_already_processed))
			log("Features ids to process: " + ','.join([str(s) for s in feature_ids_to_process]))
			
			#get the column index of the oid field in the interest features
			oid_index = features.columns.values.tolist().index('oid')
			
			#get the column index of the feature_class_name field in the interest features
			feature_class_name_index = features.columns.values.tolist().index('feature_class_name')

			#filter the filters by the oid field
			features_to_process = [f[feature_class_name_index] for f in features.values.tolist() if f[oid_index] in feature_ids_to_process]
			log("Features to process: " + ','.join(features_to_process))
			
			#iterate through the interest features and do the intersection
			try:
				conn = psycopg2.connect("dbname='biopama' host='localhost' user='jrc' password='thargal88'")
				for feature in features_to_process:
					#intersect the features with the planning units
					log("Intersecting '" + feature + "' with '" + params['PLANNING_GRID_NAME'] + "'");
					query = "select * from marxan.get_pu_areas_for_interest_feature('" + params['PLANNING_GRID_NAME'] + "','" + feature + "');"
					log(query)
					df2 = pandas.read_sql_query(query,con=conn)   
					log(str(len(df2.index)) + " intersecting planning units")
					df = df.append(df2)
				
				#write the results to the puvspr.dat file
				df.to_csv(input_folder + "puvspr.dat", sep='\t',index =False)
				
			except (psycopg2.InternalError, psycopg2.IntegrityError, DatabaseError) as e: #postgis error
				raise MarxanServicesError("Error creating puvspr.dat file: " + e.message + ". Error type: " + str(sys.exc_info()[0]))
			
			finally:
				conn.close() 

			#update the input.dat file
			updateParameters(scenario_folder + "input.dat", {'PUVSPRNAME': 'puvspr.dat'})
			
			#set the response
			response.update({'info': "puvspr.dat file created"})
			
		except Exception as inst: #handles all errors TODO: Modify all other error handlers to use this approach
			response.update({'error': str(inst)})

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

			# create the spec.dat file
			_createSPECdatafile(scenario_folder, input_folder, data["interest_features"], data["target_values"], data['spf_values'])

			# #set the response
			response.update({'info': "Scenario '" + data["scenario"] + "' created", 'name': data["scenario"]})

		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse({}, response)
	
#creates/updates the spec.dat file with the passed parameters
class createSpecFile():
	def POST(self):
		try:
			log("createScenarioFromWizard",1)			
			#get the data from the POST request
			data = web.input()
			response={}

			#error checking
			for key in ["user", "scenario", "interest_features","target_values","spf_values"]:
				if key not in data.keys():
					raise MarxanServicesError("No " + key + " parameter")

			#get the various folders
			user_folder, scenario_folder, input_folder, output_folder = initialisePostRequest(data)
						
			# create the spec.dat file
			_createSPECdatafile(scenario_folder, input_folder, data["interest_features"], data["target_values"], data['spf_values'])

			# #set the response
			response.update({'info': "spec.dat file updated"})

		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse({}, response)
	
#gets the data for the interest features for the passed scenario
	#https://db-server-blishten.c9users.io/marxan/webAPI.py/getInterestFeaturesForScenario?user=asd&scenario=test
class getInterestFeaturesForScenario:
	def GET(self):
		try:
			log("getInterestFeaturesForScenario",1)			
			#initialise the request objects
			user_folder, scenario_folder, input_folder, output_folder, response, params = initialiseGetRequest(web.ctx.query[1:])

			#get the interest features as a pandas dataframe			
			output_df = _getInterestFeaturesForScenario(scenario_folder,input_folder, True)

			#convert to a dict ready to convert to json and return a value
			_json = output_df.to_dict(orient="records")

			#write the response
			response = {'info': _json}
			
		except (MarxanServicesError) as e:
			response.update({'error': e.message})

		finally:
			return getResponse(params, response)

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

app = web.application(urls, locals())  
logging.basicConfig(filename='/home/ubuntu/lib/apache2/log/marxan.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

if __name__ == "__main__":
	app.run()