import pandas, json, re
#gets the position of the end of the line which may be different in windows/unix generated files
def writeFile(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()
    
def getEndOfLine(text):
    try:
        p = text.index("\r\n") 
    except (ValueError):
        p = text.index("\n") 
    return p

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
        returnDict.update({ key:  value})
                        
    return returnDict  
def getInputParameters(filename):
    #instantiate the return arrays
    paramsArray = []
    filesDict = {}
    metadataDict = {}
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
                        
    return filesDict, paramsArray, metadataDict

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

# print getInputParameters("/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/andrew/Sample scenario/input.dat")
updateParameters("/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/andrew/user.dat", {"NAME":"Wibble", "scenario":"Sample scenario"})